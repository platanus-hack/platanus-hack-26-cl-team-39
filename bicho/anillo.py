"""
Anillo: control total de los 12 LEDs del ReSpeaker XVF3800 (comando anillo).

    {"cmd":"anillo"}                                   estado: qué muestra y cómo va
    {"cmd":"anillo","estado":"piensa"}                 la luz de un estado del idioma del bicho (lenguaje.json),
                                                       con el mismo patrón que dibuja el simulador de bicho·dev
    {"cmd":"anillo","estados":true}                    lista de estados y su patrón
    {"cmd":"anillo","patron":"gira","color":"#5ac8fa","periodo":1.1,"intensidad":0.8}
                                                       un patrón suelto: fijo, respira, gira, parpadea, destello,
                                                       llena, corre, arcoiris, faro, lado, apagando, sectores
    {"cmd":"anillo","leds":["ff0000","00ff00",...]}    un color por LED (hasta 12; los que falten, apagados)
    {"cmd":"anillo","led":3,"color":"rojo"}            cambia un LED (0-11) y deja los demás como estaban
    {"cmd":"anillo","efecto":"arcoiris"}               un efecto del propio chip: apagado, respira, arcoiris, fijo,
                                                       doa (con "color" y "velocidad")
    {"cmd":"anillo","brillo":0-255}                    brillo general del chip
    "seg":N                                            cuánto dura (sin "seg", queda hasta otra orden). Al terminar
                                                       vuelve a seguir la voz si la luz del oído estaba prendida.
    {"cmd":"anillo","on":false}                        apaga el anillo  ·  "leer":true lee el chip

"lado" apunta hacia un ángulo ("lado":grados, en el mismo marco que el oído); sin "lado" mira hacia donde
viene la voz, en vivo. Para ubicar cada LED usa el "offset" y el "sentido" de la luz del oído (comando oido).

Cómo funciona: se pone el chip en LED_EFFECT = 5 (anillo) y un hilo daemon escribe LED_RING_COLOR (12 x uint32
0xRRGGBB) unas 20 veces por segundo, solo cuando el cuadro cambia (y cada 5 s por si reenchufan el ReSpeaker).
LED por LED necesita el firmware 2.0.7 o más nuevo del ReSpeaker (ahí llegaron LED_EFFECT = 5 y LED_RING_COLOR).
Con uno anterior (este bicho venía con el 2.0.6) el anillo se emula con lo que el chip sí acepta: los patrones
parejos (fijo, respira, parpadea, destello, apagando) salen exactos cambiando el color del efecto "fijo" (3)
20 veces por segundo; arcoiris usa el efecto 2 del chip; lado usa el efecto de dirección de la voz (4); gira,
faro y llena se aproximan con respira, corre con el arcoíris del chip y sectores con parpadea. "leds" con
colores distintos no se puede: muestra el primer color y lo avisa.

Si la luz del oído (oido_luz.py) está prendida, se apaga mientras el anillo muestra algo: los dos pelearían por
los mismos LEDs. Nada corre al importar. Con BICHO_SIMULAR=1 no se toca el USB.
"""
from __future__ import annotations

import json
import math
import os
import struct
import threading
import time
from pathlib import Path

import oido
import oido_luz
import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

N = 12
RESID = 20
LED_EFFECT, LED_BRIGHTNESS, LED_SPEED, LED_COLOR, LED_DOA_COLOR, LED_RING_COLOR = 12, 13, 15, 16, 17, 19
EF_ANILLO = 5
EFECTOS = {"apagado": 0, "off": 0, "respira": 1, "arcoiris": 2, "arcoíris": 2, "fijo": 3, "doa": 4, "voz": 4}
PATRONES = ("fijo", "respira", "gira", "parpadea", "destello", "llena", "corre", "arcoiris", "faro", "lado",
            "apagando", "sectores")
_CORRE = (0xFF2D55, 0xFFCC00, 0x34C759, 0x5AC8FA)
T_USB = 300

_lock = threading.Lock()
_usb = threading.RLock()
_dev = None
_hilo: threading.Thread | None = None
_parar: threading.Event | None = None
_plan: dict | None = None
_leds: list[int] = [0] * N  # último cuadro LED por LED (para "led")
_volver_oido = False  # al terminar un plan con "seg", volver a prender la luz del oído
_error = ""
_ultimo = ""  # resultado del último efecto del chip
_sim = "apagado"
_lenguaje: dict | None = None
_version: tuple | None = None  # firmware del ReSpeaker (se lee al abrir el USB)
_nota = ""  # cómo se está mostrando de verdad (por ejemplo, emulado)
_SIN_ANILLO = {"gira": "respira", "faro": "respira", "llena": "respira", "sectores": "parpadea"}


def _log(lvl: str, msg: str) -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "anillo: " + msg})


# ── colores y números ────────────────────────────────────────────────────────


def _color(v) -> int | None:
    if isinstance(v, str) and v.strip().lower() in ("apagado", "negro", "off", "nada"):
        return 0
    return oido_luz._a_color(v)


def _num(v, defecto: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return defecto
    if x != x or x in (float("inf"), float("-inf")):
        return defecto
    return max(lo, min(x, hi))


def _rgb(c: int) -> tuple[float, float, float]:
    return ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255


def _entero(rgb, k: float) -> int:
    r, g, b = (max(0, min(255, int(x * k * 255 + 0.5))) for x in rgb)
    return (r << 16) | (g << 8) | b


def _hsl(h: float, s: float, l: float) -> tuple[float, float, float]:
    a = s * min(l, 1 - l)

    def f(n: float) -> float:
        k = (n + h * 12) % 12
        return l - a * max(-1.0, min(k - 3, min(9 - k, 1.0)))

    return f(0), f(8), f(4)


# ── patrones (los mismos de web/src/sim/luces.ts, para 12 LEDs) ─────────────


def _angulo_led(i: int) -> float:
    """Ángulo de cada LED en el marco del oído (grados), con el offset y sentido de la luz del oído."""
    oido_luz._cargar_cfg()
    return (oido_luz._cfg["offset"] + oido_luz._cfg["sentido"] * i * 360.0 / N) % 360


def cuadro(patron: str, color: int, t: float, periodo: float = 1.0, brillo: float = 1.0,
           lado: float | None = None) -> list[int]:
    c = _rgb(color)
    b = brillo
    P = max(0.05, periodo)
    out = []
    for i in range(N):
        ang = i / N * 2 * math.pi
        k = 0.0
        col = c
        if patron == "fijo":
            k = b
        elif patron == "respira":
            k = b * (0.18 + 0.82 * (0.5 - 0.5 * math.cos(2 * math.pi * t / P)))
        elif patron == "gira":
            cabeza = (t / P * N) % N
            d = (cabeza - i + N) % N
            cola = 9 * N / 24
            k = b * ((1 - d / cola) ** 2 if d < cola else 0.04)
        elif patron == "parpadea":
            k = b if t % P < P / 2 else 0.04
        elif patron == "destello":
            k = b * (0.3 + 0.7 * math.exp(-t * 2.5))
        elif patron == "llena":
            x = (t % P) / P * N
            f = math.floor(x)
            k = b * (1 if i < f else (x % 1 if i == f else 0.05))
        elif patron == "corre":
            paso = math.floor(t / P * N)
            col = _rgb(_CORRE[((i + paso) % N) // 3 % len(_CORRE)])
            k = b * (1 if (i + paso) % 3 == 0 else 0.35)
        elif patron == "arcoiris":
            col = _hsl((i / N + t / P) % 1, 1, 0.5)
            k = b
        elif patron == "faro":
            k = b * (0.06 + max(0.0, math.cos(ang - 2 * math.pi * t / P)) ** 10)
        elif patron == "lado":
            hacia = lado if lado is not None else 0.0
            d = math.cos(math.radians(_angulo_led(i) - hacia))
            k = b * (0.08 + max(0.0, d) ** 3)
        elif patron == "apagando":
            k = b * max(0.0, 1 - t / P)
        elif patron == "sectores":
            s = i // (N // 6)
            r = math.sin((s + 1) * 12.9898 + math.floor(t / P) * 78.233) * 43758.5453
            k = b * (1 if r - math.floor(r) > 0.45 else 0.05)
        out.append(_entero(col, k))
    return out


def _lenguaje_json() -> dict:
    global _lenguaje
    if _lenguaje is None:
        _lenguaje = json.loads(Path(__file__).with_name("lenguaje.json").read_text(encoding="utf-8"))
    return _lenguaje


def _luz_de(estado: str) -> dict | None:
    d = _lenguaje_json()
    for e in [d.get("reposo", {})] + list(d.get("estados", [])):
        if e.get("id") == estado:
            return e.get("luz")
    return None


def lista_estados() -> str:
    d = _lenguaje_json()
    es = [d.get("reposo", {})] + list(d.get("estados", []))
    return "anillo: estados → " + ", ".join(f"{e['id']} ({(e.get('luz') or {}).get('patron', '?')})" for e in es if e.get("id"))


# ── USB ───────────────────────────────────────────────────────────────────────


def _abrir():
    global _dev
    if _dev is None:
        import usb.core

        d = usb.core.find(idVendor=oido.VID, idProduct=oido.PID)
        if d is None:
            raise RuntimeError("no encuentro el ReSpeaker en el USB")
        _dev = d
    return _dev


def _soltar_usb() -> None:
    global _dev, _version
    with _usb:
        d, _dev, _version = _dev, None, None
        if d is not None:
            try:
                import usb.util

                usb.util.dispose_resources(d)
            except Exception:
                pass


def _escribir(cmd: int, fmt: str, valores: list) -> None:
    import usb.util

    tipo = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    with _usb:
        _abrir().ctrl_transfer(tipo, 0, cmd, RESID, struct.pack(f"<{len(valores)}{fmt}", *valores), T_USB)


def _leer(cmd: int, fmt: str, n: int, resid: int = RESID) -> list:
    import usb.util

    tipo = usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    largo = struct.calcsize("<" + fmt) * n
    with _usb:
        dev = _abrir()
        for _ in range(6):
            r = bytes(dev.ctrl_transfer(tipo, 0, 0x80 | cmd, resid, largo + 1, T_USB))
            if len(r) >= largo + 1 and r[0] == 0:
                return list(struct.unpack(f"<{n}{fmt}", r[1 : 1 + largo]))
            time.sleep(0.01)
    raise RuntimeError(f"el chip no contestó el parámetro {resid}/{cmd}")


def con_anillo() -> bool:
    """True si el firmware del ReSpeaker sabe pintar LED por LED (2.0.7 o más nuevo)."""
    global _version
    if _version is None:
        _version = tuple(_leer(0, "B", 3, 48))
    return _version >= (2, 0, 7)


def version_txt() -> str:
    return ".".join(str(x) for x in _version) if _version else "?"


# ── hilo que dibuja ───────────────────────────────────────────────────────────


def _cuadro_de(plan: dict, t: float) -> list[int]:
    if plan["tipo"] == "leds":
        return list(plan["leds"])
    lado = plan.get("lado")
    if plan["patron"] == "lado" and lado is None:
        o = oido.estado()
        lado = float(o["angulo"]) if o else None
    return cuadro(plan["patron"], plan["color"], t, plan["periodo"], plan["intensidad"], lado)


def _como(plan: dict) -> tuple[str, int, str]:
    """(modo, efecto del chip esperado, patrón que se dibuja). modo: anillo | color | chip."""
    if con_anillo():
        return "anillo", EF_ANILLO, plan.get("patron", "")
    if plan["tipo"] == "leds":
        return "color", 3, ""
    p = plan["patron"]
    if p in ("arcoiris", "corre"):
        return "chip", 2, p
    if p == "lado" and plan.get("lado") is None:
        return "chip", 4, p
    return "color", 3, _SIN_ANILLO.get(p, p)


def _correr(parar: threading.Event, plan: dict) -> None:
    global _error, _volver_oido, _nota
    terminado = False
    try:
        if oido_luz.activa():  # la luz del oído pelearía por los LEDs
            _volver_oido = True
            oido_luz.apagar()
        if plan.get("brillo") is not None:
            _escribir(LED_BRIGHTNESS, "B", [plan["brillo"]])
        t0 = time.monotonic()
        preparado, ultimo, t_esc, t_rev = False, None, 0.0, 0.0
        modo, efecto, dibujo = "anillo", EF_ANILLO, ""
        while not parar.is_set():
            ahora = time.monotonic()
            if plan.get("hasta") and ahora >= plan["hasta"]:
                terminado = True
                break
            try:
                if not preparado:
                    modo, efecto, dibujo = _como(plan)
                    fw = f"firmware {version_txt()} del ReSpeaker"
                    if modo == "anillo":
                        _nota = ""
                    elif modo == "chip":
                        if efecto == 2:
                            _escribir(LED_BRIGHTNESS, "B", [plan["brillo"] if plan.get("brillo") is not None
                                                            else int(255 * plan.get("intensidad", 1.0))])
                        else:
                            col = plan["color"]
                            _escribir(LED_DOA_COLOR, "I", [_entero(_rgb(col), 0.06), _entero(_rgb(col), plan.get("intensidad", 1.0))])
                        _nota = f"{fw}: sin LED por LED, uso el efecto {'arcoíris' if efecto == 2 else 'de dirección de la voz'} del chip"
                    else:
                        distintos = plan["tipo"] == "leds" and len(set(plan["leds"])) > 1
                        _nota = (f"{fw}: no pinta LED por LED (hace falta 2.0.7 o más nuevo); muestro el primer color en todo el anillo"
                                 if distintos else f"{fw}: sin LED por LED, emulo {dibujo or 'el color'} con el color de todo el anillo"
                                 + (f" (en vez de {plan['patron']})" if dibujo and dibujo != plan.get("patron") else ""))
                    _escribir(LED_EFFECT, "B", [efecto])
                    preparado, ultimo, t_rev = True, None, ahora
                    _error = ""
                if modo == "anillo":
                    c = _cuadro_de(plan, ahora - t0)
                    if c != ultimo or ahora - t_esc > 5:
                        _escribir(LED_RING_COLOR, "I", c)
                        _leds[:] = c
                        ultimo, t_esc = c, ahora
                elif modo == "color":
                    if plan["tipo"] == "leds":
                        col = next((x for x in plan["leds"] if x), 0)
                    else:
                        col = cuadro(dibujo, plan["color"], ahora - t0, plan["periodo"], plan["intensidad"])[0]
                    if col != ultimo or ahora - t_esc > 5:
                        _escribir(LED_COLOR, "I", [col])
                        _leds[:] = [col] * N
                        ultimo, t_esc = col, ahora
                if ahora - t_rev > 5:
                    t_rev = ahora
                    if _leer(LED_EFFECT, "B", 1)[0] != efecto:
                        preparado = False
                parar.wait(0.05 if modo != "chip" else 0.25)
            except Exception as e:  # desenchufado o el chip no quiso: se reintenta
                _error = f"{type(e).__name__}: {e}"
                preparado = False
                _soltar_usb()
                parar.wait(2)
    except Exception as e:
        _error = f"{type(e).__name__}: {e}"
    finally:
        if terminado:  # se cumplió "seg": apagar y, si seguía la voz antes, volver a eso
            try:
                _escribir(LED_EFFECT, "B", [0])
            except Exception:
                pass
            if _volver_oido and parar is _parar:
                _volver_oido = False
                try:
                    oido_luz.prender()
                except Exception:
                    pass
        elif plan.get("apagar"):
            try:
                _escribir(LED_EFFECT, "B", [0])
            except Exception:
                pass


def _detener(join: float = 0.3) -> None:
    global _hilo, _parar, _plan
    h, p = _hilo, _parar
    _hilo, _parar, _plan = None, None, None
    if p is not None:
        p.set()
    if h is not None and h.is_alive():
        h.join(join)


def _lanzar(plan: dict) -> None:
    global _hilo, _parar, _plan, _error
    with _lock:
        _detener()
        _error = ""
        _parar = threading.Event()
        _plan = plan
        _hilo = threading.Thread(target=_correr, args=(_parar, plan), daemon=True, name="anillo")
        _hilo.start()


def _una_vez(fn, que: str) -> None:
    """Escrituras sueltas al chip (efectos) en un hilo, para no bloquear. El resultado sale en la consola."""
    def tarea() -> None:
        global _ultimo, _volver_oido
        try:
            if oido_luz.activa():
                _volver_oido = False  # un efecto del chip reemplaza a la luz del oído
                oido_luz.apagar()
            _ultimo = fn()
            _log("info", _ultimo)
        except Exception as e:
            _ultimo = f"{que} falló: {type(e).__name__}: {e}"
            _log("error", _ultimo)

    threading.Thread(target=tarea, daemon=True, name="anillo-efecto").start()


# ── lo que usa comandos.py ────────────────────────────────────────────────────


def soltar() -> None:
    """Deja de dibujar sin apagar (lo usa el comando oido antes de prender la luz del oído)."""
    global _volver_oido
    _volver_oido = False
    with _lock:
        _detener()


def activa() -> bool:
    h = _hilo
    return bool(h is not None and h.is_alive())


def estado() -> str:
    if SIMULAR:
        return f"anillo: simulado ({_sim})"
    p = _plan
    if p is None or not activa():
        txt = "anillo: no estoy dibujando nada" + (f" · último efecto: {_ultimo}" if _ultimo else "")
    elif p["tipo"] == "leds":
        txt = "anillo: LED por LED → " + " ".join(f"{x:06x}" for x in p["leds"])
    else:
        quien = f"estado {p['estado']} · " if p.get("estado") else ""
        txt = (f"anillo: {quien}patrón {p['patron']}, color {p['color']:06x}, periodo {p['periodo']:g} s,"
               f" intensidad {p['intensidad']:g}")
        if p["patron"] == "lado":
            txt += f", mira a {p['lado']:g}°" if p.get("lado") is not None else ", mira hacia la voz"
    if p is not None and p.get("hasta") and activa():
        txt += f" · quedan {max(0.0, p['hasta'] - time.monotonic()):.0f} s"
    if _nota and activa():
        txt += f" · {_nota}"
    if _error:
        txt += f" · problema: {_error} (sigo intentando)"
    if oido_luz.activa():
        txt += " · la luz del oído está prendida (sigue la voz)"
    return txt


def apagar() -> str:
    global _volver_oido, _sim
    if SIMULAR:
        _sim = "apagado"
        return "anillo: apagado (simulado)"
    _volver_oido = False
    with _lock:
        _detener()
    _una_vez(lambda: (_escribir(LED_EFFECT, "B", [0]), "LEDs apagados")[1], "apagar")
    return "anillo: apagando los LEDs"


def _hasta(c: dict) -> float | None:
    if "seg" not in c:
        return None
    return time.monotonic() + _num(c.get("seg"), 5, 0.2, 3600)


def _brillo(c: dict) -> int | None:
    if "brillo" not in c:
        return None
    return int(_num(c.get("brillo"), 255, 0, 255))


def mostrar_patron(c: dict, estado_id: str | None = None) -> str:
    global _sim
    base = {}
    if estado_id:
        base = _luz_de(estado_id) or {}
        if not base:
            return f'anillo: no conozco el estado "{estado_id}" (lista: {{"cmd":"anillo","estados":true}})'
    patron = str(c.get("patron") or base.get("patron") or "fijo").strip().lower()
    if patron == "arcoíris":
        patron = "arcoiris"
    if patron not in PATRONES:
        return "anillo: patrones que sé: " + ", ".join(PATRONES)
    col = _color(c["color"]) if "color" in c else _color(base.get("color", "#ffffff"))
    if col is None:
        return 'anillo: color raro; usa "RRGGBB", "#RRGGBB" o un nombre (' + ", ".join(oido_luz._COLORES) + ")"
    plan = {
        "tipo": "patron", "estado": estado_id, "patron": patron, "color": col,
        "periodo": _num(c.get("periodo", base.get("periodo", 1.0)), 1.0, 0.05, 60),
        "intensidad": _num(c.get("intensidad", base.get("brillo", 1.0)), 1.0, 0.0, 1.0),
        "lado": _num(c["lado"], 0, -720, 720) % 360 if "lado" in c else None,
        "hasta": _hasta(c), "brillo": _brillo(c),
    }
    if SIMULAR:
        _sim = f"patrón {patron}"
        return f"anillo: {patron} (simulado)"
    _lanzar(plan)
    return estado()


def mostrar_leds(c: dict) -> str:
    global _sim
    if "leds" in c:
        lista = c.get("leds")
        if isinstance(lista, str):
            lista = [x for x in lista.replace(",", " ").split() if x]
        if not isinstance(lista, list) or not lista or len(lista) > N:
            return f"anillo: leds es una lista de 1 a {N} colores"
        cols = [_color(x) for x in lista]
        if any(x is None for x in cols):
            return "anillo: hay un color raro en leds"
        leds = cols * N if len(cols) == 1 else cols + [0] * (N - len(cols))
        leds = leds[:N]
    else:
        try:
            i = int(c.get("led"))
        except (TypeError, ValueError):
            return f"anillo: led es un número de 0 a {N - 1}"
        if not 0 <= i < N:
            return f"anillo: led es un número de 0 a {N - 1}"
        col = _color(c.get("color", "blanco"))
        if col is None:
            return "anillo: color raro"
        p = _plan
        leds = list(p["leds"]) if p is not None and p["tipo"] == "leds" and activa() else [0] * N
        leds[i] = col
    if SIMULAR:
        _sim = "LED por LED"
        return "anillo: LED por LED (simulado)"
    _lanzar({"tipo": "leds", "leds": leds, "hasta": _hasta(c), "brillo": _brillo(c)})
    return "anillo: LED por LED → " + " ".join(f"{x:06x}" for x in leds)


def efecto_chip(c: dict) -> str:
    global _sim
    nombre = str(c.get("efecto")).strip().lower()
    if nombre not in EFECTOS:
        return "anillo: efectos del chip: apagado, respira, arcoiris, fijo, doa"
    ef = EFECTOS[nombre]
    col = _color(c["color"]) if "color" in c else None
    if "color" in c and col is None:
        return "anillo: color raro"
    vel = int(_num(c.get("velocidad"), 0, 0, 255)) if "velocidad" in c else None
    bri = _brillo(c)
    if SIMULAR:
        _sim = f"efecto {nombre}"
        return f"anillo: efecto {nombre} (simulado)"
    with _lock:
        _detener()

    def fn() -> str:
        if bri is not None:
            _escribir(LED_BRIGHTNESS, "B", [bri])
        if col is not None and ef in (1, 3):
            _escribir(LED_COLOR, "I", [col])
        if col is not None and ef == 4:
            _escribir(LED_DOA_COLOR, "I", [0x000008, col])
        if vel is not None:
            _escribir(LED_SPEED, "B", [vel])
        _escribir(LED_EFFECT, "B", [ef])
        time.sleep(0.02)
        quedo = _leer(LED_EFFECT, "B", 1)[0]
        extra = (f", color {col:06x}" if col is not None else "") + (f", velocidad {vel}" if vel is not None else "")
        return f"efecto del chip {nombre}{extra}" + ("" if quedo == ef else f" (pero el chip quedó en {quedo})")

    _una_vez(fn, f"efecto {nombre}")
    return f"anillo: pidiendo al chip el efecto {nombre}… (el resultado sale en la consola)"


def solo_brillo(c: dict) -> str:
    b = _brillo(c)
    if SIMULAR:
        return f"anillo: brillo {b} (simulado)"
    _una_vez(lambda: (_escribir(LED_BRIGHTNESS, "B", [b]), f"brillo del chip en {b}")[1], "brillo")
    return f"anillo: brillo del chip a {b}"


def manejar(c: dict) -> str:
    if c.get("estados") or c.get("lista"):
        return lista_estados()
    if ("on" in c and not c.get("on")) or c.get("apagar"):
        return apagar()
    if "efecto" in c:
        return efecto_chip(c)
    if "leds" in c or "led" in c:
        return mostrar_leds(c)
    if "estado" in c:
        return mostrar_patron(c, str(c.get("estado")).strip())
    if "patron" in c or "color" in c:
        return mostrar_patron(c)
    if "brillo" in c:
        return solo_brillo(c)
    if c.get("leer"):
        return oido_luz.leer_chip()
    return estado()
