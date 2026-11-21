"""
Luz del oído: los 12 LEDs del ReSpeaker XVF3800 apuntan hacia donde llega la voz.

Dos modos:
  - "chip":  se le pide al firmware su efecto DOA (LED_EFFECT = 4): el propio chip prende el LED de la
             dirección de la voz. No gasta nada de CPU y la orientación la conoce el chip.
  - "suave": el bicho dibuja el anillo LED por LED (LED_EFFECT = 5 + LED_RING_COLOR): un punto de luz
             que se desliza hacia el ángulo de la voz (oido.estado()), brilla mientras hablan y queda
             tenue donde escuchó lo último. Si el firmware no acepta el anillo, cae solo a "chip".

Nada corre al importar. Al prender parte un hilo daemon; al apagar, el hilo restaura los LEDs y termina.
Los parámetros (resid, cmd) son los de xvf_host.py de Seeed, igual que DOA_VALUE en oido.py.
Con BICHO_SIMULAR=1 no se toca el USB.
"""
from __future__ import annotations

import json
import os
import struct
import threading
import time
from pathlib import Path

import oido

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

RESID = 20  # servicio GPO/LED del XVF3800
LED_EFFECT = 12  # uint8: 0 apagado, 1 respira, 2 arcoíris, 3 un color, 4 DOA, 5 anillo
LED_BRIGHTNESS = 13  # uint8
LED_DOA_COLOR = 17  # 2 x uint32: color de fondo y color de la dirección (0xRRGGBB)
LED_RING_COLOR = 19  # 12 x uint32
N_LEDS = 12
EF_DOA, EF_ANILLO = 4, 5
T_USB = 300  # ms por transferencia

MODOS = ("chip", "suave")
_COLORES = {
    "verde": 0x00FF40, "azul": 0x0040FF, "rojo": 0xFF0000, "blanco": 0xFFFFFF, "amarillo": 0xFFC000,
    "celeste": 0x00C0FF, "morado": 0xA000FF, "naranjo": 0xFF6000, "rosado": 0xFF2080,
}
REPOSO = 0.2  # brillo del punto cuando nadie habla (modo suave)

# Configuración (se guarda en la casa del bicho, fuera de las versiones)
_cfg = {"modo": "chip", "color": 0x00FF40, "fondo": 0x000008, "brillo": None, "offset": 0.0, "sentido": 1}
_cfg_cargada = False

_lock = threading.Lock()  # prender / apagar
_usb = threading.RLock()  # un solo uso del USB a la vez desde este módulo
_dev = None
_hilo: threading.Thread | None = None
_parar: threading.Event | None = None
_listo: threading.Event | None = None
_pendiente = False  # cambió la configuración: volver a preparar el chip
_sim_on = False

_modo_real: str | None = None
_nota = ""
_error = ""
_pos: float | None = None  # hacia dónde apunta la luz (modo suave)
_prueba: tuple[float, float] | None = None  # (ángulo, hasta cuándo)


# ── configuración ─────────────────────────────────────────────────────────────


def _archivo_cfg() -> Path:
    if os.environ.get("BICHO_HOME"):
        casa = Path(os.environ["BICHO_HOME"])
    else:
        opt = Path("/opt/bicho")
        casa = opt if opt.exists() and os.access(opt, os.W_OK) else Path.home() / ".bicho"
    return casa / "oido_luz.json"


def _cargar_cfg() -> None:
    global _cfg_cargada
    if _cfg_cargada:
        return
    _cfg_cargada = True
    if SIMULAR:
        return
    try:
        d = json.loads(_archivo_cfg().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(d, dict):
        return
    if d.get("modo") in MODOS:
        _cfg["modo"] = d["modo"]
    for k in ("color", "fondo"):
        if isinstance(d.get(k), int) and 0 <= d[k] <= 0xFFFFFF:
            _cfg[k] = d[k]
    if isinstance(d.get("brillo"), int) and 0 <= d["brillo"] <= 255:
        _cfg["brillo"] = d["brillo"]
    if isinstance(d.get("offset"), (int, float)) and d["offset"] == d["offset"]:
        _cfg["offset"] = float(d["offset"]) % 360
    if d.get("sentido") in (1, -1):
        _cfg["sentido"] = d["sentido"]


def _guardar_cfg() -> None:
    if SIMULAR:
        return
    try:
        f = _archivo_cfg()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(".oido_luz.tmp")
        tmp.write_text(json.dumps(_cfg), encoding="utf-8")
        os.replace(tmp, f)
    except OSError:
        pass


def _a_color(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if 0 <= v <= 0xFFFFFF else None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in _COLORES:
            return _COLORES[s]
        s = s.lstrip("#")
        if len(s) == 6:
            try:
                return int(s, 16)
            except ValueError:
                return None
    return None


def configurar(c: dict) -> list[str]:
    """Aplica modo, color, brillo, offset y sentido si vienen en el comando. Devuelve qué cambió."""
    global _pendiente
    _cargar_cfg()
    dicho = []
    if "modo" in c:
        m = str(c.get("modo")).strip().lower()
        if m in MODOS:
            _cfg["modo"] = m
            dicho.append(f"modo {m}")
        else:
            dicho.append('modo: usa "chip" o "suave"')
    if "color" in c:
        col = _a_color(c.get("color"))
        if col is None:
            dicho.append('color: usa "RRGGBB" o ' + ", ".join(_COLORES))
        else:
            _cfg["color"] = col
            dicho.append(f"color {col:06x}")
    if "brillo" in c:
        try:
            b = int(float(c.get("brillo")))
            _cfg["brillo"] = max(0, min(b, 255))
            dicho.append(f"brillo {_cfg['brillo']}")
        except (TypeError, ValueError, OverflowError):
            dicho.append("brillo: un número de 0 a 255")
    if "offset" in c:
        try:
            o = float(c.get("offset"))
            if o != o or o in (float("inf"), float("-inf")):
                raise ValueError
            _cfg["offset"] = o % 360
            dicho.append(f"offset {_cfg['offset']:g}°")
        except (TypeError, ValueError):
            dicho.append("offset: grados")
    if "sentido" in c:
        s = c.get("sentido")
        if s in (1, -1) and not isinstance(s, bool):
            _cfg["sentido"] = s
            dicho.append(f"sentido {s}")
        else:
            dicho.append("sentido: 1 o -1")
    if dicho:
        _pendiente = True
        _guardar_cfg()
    return dicho


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


def _soltar() -> None:
    global _dev
    with _usb:
        d, _dev = _dev, None
        if d is not None:
            try:
                import usb.util

                usb.util.dispose_resources(d)
            except Exception:
                pass


def _escribir(cmd: int, fmt: str, valores: list[int]) -> None:
    import usb.util

    tipo = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    datos = struct.pack(f"<{len(valores)}{fmt}", *valores)
    with _usb:
        _abrir().ctrl_transfer(tipo, 0, cmd, RESID, datos, T_USB)


def _leer(cmd: int, fmt: str, n: int, resid: int = RESID) -> list[int]:
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


# ── dibujo del anillo (modo suave) ────────────────────────────────────────────


def _escala(color: int, k: float) -> int:
    k = max(0.0, min(k, 1.0))
    r, g, b = (color >> 16) & 255, (color >> 8) & 255, color & 255
    return (int(r * k + 0.5) << 16) | (int(g * k + 0.5) << 8) | int(b * k + 0.5)


def _anillo(pos: float | None, nivel: float) -> list[int]:
    color = _cfg["color"]
    if pos is None:  # todavía no escucha a nadie: todo muy tenue, para que se note que está prendido
        return [_escala(color, 0.03)] * N_LEDS
    out = []
    paso = 360.0 / N_LEDS
    for i in range(N_LEDS):
        a = (_cfg["offset"] + _cfg["sentido"] * i * paso) % 360
        d = abs(((a - pos + 180) % 360) - 180)
        k = max(0.0, 1 - d / 40.0) ** 2 * nivel
        out.append(_escala(color, k))
    return out


# ── hilo ──────────────────────────────────────────────────────────────────────


def _preparar(previo: dict) -> str:
    """Deja el chip en el modo pedido. Devuelve el modo que quedó de verdad."""
    global _nota
    if not previo:  # se anota una vez cómo estaba, para devolverlo al apagar
        previo["efecto"] = _leer(LED_EFFECT, "B", 1)[0]
        try:
            previo["doa"] = _leer(LED_DOA_COLOR, "I", 2)
        except Exception:
            previo["doa"] = None
        try:
            previo["brillo"] = _leer(LED_BRIGHTNESS, "B", 1)[0]
        except Exception:
            previo["brillo"] = None
    if _cfg["brillo"] is not None:
        _escribir(LED_BRIGHTNESS, "B", [_cfg["brillo"]])
        previo["toque_brillo"] = True
    _nota = ""
    if _cfg["modo"] == "suave":
        try:
            _escribir(LED_EFFECT, "B", [EF_ANILLO])
            _escribir(LED_RING_COLOR, "I", _anillo(_pos, REPOSO))
            time.sleep(0.02)
            if _leer(LED_EFFECT, "B", 1)[0] == EF_ANILLO:
                return "suave"
            _nota = "este firmware no aceptó el anillo LED por LED; uso el efecto del chip"
        except RuntimeError as e:
            _nota = f"sin anillo LED por LED ({e}); uso el efecto del chip"
    _escribir(LED_DOA_COLOR, "I", [_cfg["fondo"], _cfg["color"]])
    _escribir(LED_EFFECT, "B", [EF_DOA])
    time.sleep(0.02)
    ef = _leer(LED_EFFECT, "B", 1)[0]
    if ef != EF_DOA:
        raise RuntimeError(f"el chip no aceptó el efecto de dirección (quedó en {ef})")
    return "chip"


def _restaurar(previo: dict) -> None:
    if not previo:
        return
    try:
        if previo.get("doa"):
            _escribir(LED_DOA_COLOR, "I", previo["doa"])
        if previo.get("toque_brillo") and previo.get("brillo") is not None:
            _escribir(LED_BRIGHTNESS, "B", [previo["brillo"]])
        ef = previo.get("efecto")
        # si antes ya seguía la voz (4) o era mi anillo (5), apagar es apagar la luz
        _escribir(LED_EFFECT, "B", [ef if ef in (1, 2, 3) else 0])
    except Exception:
        pass


def _correr(parar: threading.Event, listo: threading.Event) -> None:
    global _modo_real, _error, _pos, _pendiente, _prueba
    previo: dict = {}
    preparado = False
    nivel = REPOSO
    ultimo: list[int] | None = None
    t_escrito = t_revisado = 0.0
    try:
        while not parar.is_set():
            try:
                if not preparado or _pendiente:
                    _pendiente = False
                    _modo_real = _preparar(previo)
                    preparado = True
                    _error = ""
                    ultimo = None
                    t_revisado = time.monotonic()
                    listo.set()
                ahora = time.monotonic()

                if _modo_real == "chip":
                    # el chip hace todo; solo se revisa cada tanto que siga así (por si lo reenchufan)
                    parar.wait(0.25)
                    if ahora - t_revisado > 4:
                        t_revisado = ahora
                        if _leer(LED_EFFECT, "B", 1)[0] != EF_DOA:
                            preparado = False
                    continue

                # modo suave: el punto de luz se desliza hacia el ángulo de la voz
                objetivo = None
                p = _prueba
                if p is not None:
                    if ahora < p[1]:
                        objetivo = p[0]
                    else:
                        _prueba = None
                if objetivo is None:
                    o = oido.estado()
                    if o and o.get("voz"):
                        objetivo = float(o["angulo"])
                if objetivo is not None:
                    if _pos is None:
                        _pos = objetivo % 360
                    else:
                        d = ((objetivo - _pos + 180) % 360) - 180
                        if abs(d) < 2:
                            _pos = objetivo % 360
                        else:
                            paso = max(-45.0, min(d * 0.3, 45.0))
                            if abs(paso) < 2:
                                paso = 2.0 if d > 0 else -2.0
                            _pos = (_pos + paso) % 360
                    nivel = min(1.0, nivel + 0.25)
                else:
                    nivel = max(REPOSO, nivel - 0.04)
                cuadro = _anillo(_pos, nivel)
                if cuadro != ultimo or ahora - t_escrito > 5:
                    _escribir(LED_RING_COLOR, "I", cuadro)
                    ultimo = cuadro
                    t_escrito = ahora
                if ahora - t_revisado > 5:
                    t_revisado = ahora
                    if _leer(LED_EFFECT, "B", 1)[0] != EF_ANILLO:
                        preparado = False
                quieto = objetivo is None and nivel <= REPOSO
                parar.wait(0.1 if quieto else 0.05)
            except Exception as e:  # desenchufado, sin permiso o el chip no quiso: se reintenta
                _error = f"{type(e).__name__}: {e}"
                preparado = False
                _soltar()
                listo.set()
                parar.wait(2)
    finally:
        _restaurar(previo)
        _soltar()
        _modo_real = None
        listo.set()


# ── lo que usa comandos.py / sensores.py ──────────────────────────────────────


def activa() -> bool:
    if SIMULAR:
        return _sim_on
    h = _hilo
    return bool(h is not None and h.is_alive() and _parar is not None and not _parar.is_set())


def estado() -> str:
    _cargar_cfg()
    if SIMULAR:
        return f"luz del oído {'prendida' if _sim_on else 'apagada'} (simulada, modo {_cfg['modo']})"
    if not activa():
        return f"luz del oído apagada (modo {_cfg['modo']}, color {_cfg['color']:06x})"
    if _error:
        return f"luz del oído prendida pero sin el mic: {_error} (sigo intentando)"
    if _modo_real is None:
        return "luz del oído prendiéndose…"
    o = oido.estado()
    oye = f"oído: {o['angulo']}°{' con voz' if o['voz'] else ''}" if o else "oído: sin datos todavía"
    if _modo_real == "chip":
        txt = f"luz del oído prendida, modo chip (el XVF3800 prende el LED de la dirección de la voz), color {_cfg['color']:06x}; {oye}"
    else:
        ap = "sin apuntar todavía" if _pos is None else f"apunta a {_pos:.0f}°"
        txt = f"luz del oído prendida, modo suave ({ap}, offset {_cfg['offset']:g}°, sentido {_cfg['sentido']}), color {_cfg['color']:06x}; {oye}"
    return txt + (f" · {_nota}" if _nota else "")


def prender() -> str:
    global _hilo, _parar, _listo, _sim_on, _error, _pendiente
    _cargar_cfg()
    if SIMULAR:
        _sim_on = True
        return estado()
    with _lock:
        h = _hilo
        if h is not None and h.is_alive():
            if _parar is not None and _parar.is_set():
                h.join(1.0)
                if h.is_alive():
                    return "la luz del oído todavía se está apagando; prueba de nuevo en un momento"
            else:
                return "ya estaba: " + estado()
        try:
            import usb.core  # noqa: F401
        except ImportError:
            return "luz del oído: falta pyusb (python3-usb)"
        _error = ""
        _pendiente = False
        _parar, _listo = threading.Event(), threading.Event()
        _hilo = threading.Thread(target=_correr, args=(_parar, _listo), daemon=True, name="oido-luz")
        _hilo.start()
        listo = _listo
    listo.wait(0.7)
    return estado()


def apagar() -> str:
    global _sim_on, _prueba
    if SIMULAR:
        _sim_on = False
        return estado()
    with _lock:
        h, p = _hilo, _parar
        _prueba = None
        if h is None or not h.is_alive():
            return "la luz del oído ya estaba apagada"
        if p is not None:
            p.set()
    h.join(0.8)
    return "luz del oído apagada" if not h.is_alive() else "apagando la luz del oído…"


def probar(grados) -> str:
    """Apunta la luz a un ángulo durante 4 s (modo suave), para revisar que calce con el oído."""
    global _prueba
    try:
        g = float(grados)
        if g != g or g in (float("inf"), float("-inf")):
            raise ValueError
    except (TypeError, ValueError):
        return 'probar: dime un ángulo, por ejemplo "probar":90'
    if SIMULAR:
        return f"probar {g % 360:g}° (simulado)"
    if not activa():
        return 'probar: primero prende la luz con "on":true'
    if _modo_real != "suave":
        return 'probar solo sirve en modo suave ("modo":"suave"); en modo chip la dirección la pone el XVF3800'
    _prueba = (g % 360, time.monotonic() + 4)
    return f"apunto la luz a {g % 360:g}° por 4 s; si no calza, ajusta \"offset\" (grados) o \"sentido\" (1 o -1)"


def _diagnostico(out: list) -> None:
    partes = []
    for nombre, cmd, fmt, n, resid, hexa in (
        ("versión", 0, "B", 3, 48, False),
        ("efecto", LED_EFFECT, "B", 1, RESID, False),
        ("brillo", LED_BRIGHTNESS, "B", 1, RESID, False),
        ("color DOA (fondo, dirección)", LED_DOA_COLOR, "I", 2, RESID, True),
        ("anillo", LED_RING_COLOR, "I", N_LEDS, RESID, True),
        ("DOA (ángulo, voz)", oido.DOA_VALUE[1], "H", 2, oido.DOA_VALUE[0], False),
    ):
        try:
            v = _leer(cmd, fmt, n, resid)
            partes.append(f"{nombre}: " + (" ".join(f"{x:06x}" for x in v) if hexa else " ".join(str(x) for x in v)))
        except Exception as e:
            partes.append(f"{nombre}: no ({type(e).__name__}: {e})")
    out.append(" | ".join(partes))


def leer_chip() -> str:
    """Lee del chip cómo están los LEDs (solo lectura). No bloquea más de 1,5 s."""
    if SIMULAR:
        return "chip: simulado"
    try:
        import usb.core  # noqa: F401
    except ImportError:
        return "chip: falta pyusb"
    out: list = []
    h = threading.Thread(target=_diagnostico, args=(out,), daemon=True, name="oido-luz-diag")
    h.start()
    h.join(1.5)
    return "chip → " + out[0] if out else "chip: no contestó a tiempo"
