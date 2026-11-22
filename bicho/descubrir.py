"""
Descubrir (comando "descubrir"): el bicho averigua solo qué canales del PCA9685 mueven sus motores.

Mueve un canal (o un motor, o todos) con potencia mínima y poco rato, usando la misma maquinaria
segura de motores.py (rampa, tope de 30 %, se apaga solo), y MIDE qué pasó:

  - los dos sensores de flujo óptico (flujo.py y flujo2.py): desplazamiento neto (dx, dy) de cada
    uno mientras duró la prueba, comparado con lo que marcan estando quieto;
  - la cámara: un cuadro antes y otro después, y cuánto se corrió la imagen (y si se agrandó o
    achicó, que es lo que dice si avanzó o retrocedió).

  {"cmd":"descubrir","on":true}             barre los 16 canales, de a uno, subiendo 12 → 20 → 30 %
                                            solo en los que no se movieron ("canales":[0,1], "pot",
                                            "seg", "camara":false, "modo":"canales"|"triples"|"auto")
  {"cmd":"descubrir","canal":3}             una prueba medida de un canal
  {"cmd":"descubrir","motor":2,"sentido":-1} una prueba medida de un motor del mapa de motores
  {"cmd":"descubrir","todos":true}          todos los motores del mapa a la vez (aunque el mapa no
                                            esté confirmado: es la prueba para confirmarlo; 20 % máx.)
  {"cmd":"descubrir","grupo":[1,2]}         solo esos motores
  {"cmd":"descubrir"}                       cómo va  ·  "resultado":true la tabla completa
  {"cmd":"descubrir","on":false}            corta todo y apaga los motores

No decide el mapa por sí solo: entrega la evidencia; el mapa se deja con el comando motores.
Los resultados quedan en la nota "motores-descubrir". Todo corre en un hilo daemon; nada se abre
al importar; con BICHO_SIMULAR=1 no se toca hardware.
"""
from __future__ import annotations

import base64
import io
import math
import os
import threading
import time

import camara
import flujo
import flujo2
import herramientas
import motores
import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

NOTA = "motores-descubrir"
NIVELES = (12.0, 20.0, 30.0)  # % de potencia: se sube solo en lo que no se movió
POT_TODOS = 20.0  # tope al mover varios motores con el mapa sin confirmar
_W, _H, _R = 160, 120, 12  # tamaño al que se comparan los cuadros y radio de búsqueda (px)

AYUDA = (
    '{"cmd":"descubrir"}  cómo va el descubrimiento de motores  ·  "on":true barre los 16 canales del PCA9685 de'
    ' a uno (12 → 20 → 30 % solo en los que no se movieron) midiendo con los dos sensores de flujo y la cámara'
    ' ("canales":[0,1], "pot", "seg", "camara":false, "modo":"canales"|"triples"|"auto")  ·  "canal":3 prueba'
    ' medida de un canal  ·  "motor":2,"sentido":-1 de un motor del mapa  ·  "todos":true todos los del mapa a la'
    ' vez (máx. 20 %, sirve para confirmar si avanza)  ·  "grupo":[1,2] solo esos  ·  "resultado":true tabla'
    ' completa  ·  "on":false corta y apaga los motores. Deja lo medido en la nota motores-descubrir; el mapa'
    ' se fija con el comando motores'
)

_lock = threading.Lock()
_parar = threading.Event()
_hilo: threading.Thread | None = None
_fase = ""
_resultados: list[dict] = []
_base: dict | None = None
_avisos: list[str] = []
_cuadro: tuple[float, bytes] = (0.0, b"")
_cuadro_ev = threading.Event()


def _num(v, defecto: float, lo: float, hi: float) -> float:
    if isinstance(v, bool):
        return defecto
    try:
        x = float(v)
    except (TypeError, ValueError):
        return defecto
    if x != x:
        return defecto
    return max(lo, min(x, hi))


def _log(msg: str, lvl: str = "info") -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "descubrir: " + msg})


# ── cámara ────────────────────────────────────────────────────────────────────


def _al_cuadro(jpg: bytes) -> None:  # corre en el hilo de la cámara: solo guarda
    global _cuadro
    _cuadro = (time.monotonic(), jpg)
    _cuadro_ev.set()


def _pedir_cuadro(desde: float, espera: float = 6.0) -> bytes | None:
    """El primer cuadro que llegue después de `desde` (monotonic). None si no llega."""
    fin = time.monotonic() + espera
    while True:
        t, j = _cuadro
        if j and t > desde:
            return j
        resto = fin - time.monotonic()
        if resto <= 0 or not camara.analizando("descubrir"):
            return None
        _cuadro_ev.clear()
        _cuadro_ev.wait(min(0.3, resto))


def _gris(jpg: bytes):
    import numpy as np
    from PIL import Image

    im = Image.open(io.BytesIO(jpg))
    im.draft("L", (_W, _H))
    im = im.convert("L").resize((_W, _H))
    return np.asarray(im, dtype=np.int16)


def _zoom(A, B) -> tuple[float, float, float]:
    """Escala que mejor explica el paso de A a B (>1: todo se agrandó = avanzó). (escala, dif, dif sin zoom)."""
    import numpy as np
    from PIL import Image

    ia = Image.fromarray(A.astype("uint8"))
    ib = Image.fromarray(B.astype("uint8"))

    def agrandar(im, s: float):
        w, h = _W / s, _H / s
        caja = ((_W - w) / 2, (_H - h) / 2, (_W + w) / 2, (_H + h) / 2)
        return np.asarray(im.resize((_W, _H), Image.BILINEAR, box=caja), dtype=np.int16)

    m = (slice(_H // 5, _H - _H // 5), slice(_W // 5, _W - _W // 5))
    res = {1.0: float(np.abs(A[m] - B[m]).mean())}
    for s in (1.03, 1.06, 1.1, 1.15, 1.22):
        res[s] = float(np.abs(agrandar(ia, s)[m] - B[m]).mean())  # A agrandada se parece a B: avanzó
        res[round(1 / s, 3)] = float(np.abs(agrandar(ib, s)[m] - A[m]).mean())  # al revés: retrocedió
    mejor = min(res, key=res.get)
    return mejor, res[mejor], res[1.0]


def _comparar(a_jpg: bytes, b_jpg: bytes, con_zoom: bool) -> dict:
    """Cuánto se corrió la imagen entre dos cuadros (px a 160x120) y cuánto cambió."""
    import numpy as np

    A = _gris(a_jpg)
    B = _gris(b_jpg)
    R = _R
    nucleo = B[R:_H - R, R:_W - R]
    v0 = float(np.abs(A[R:_H - R, R:_W - R] - nucleo).mean())
    mejor = (v0, 0, 0)
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            v = float(np.abs(A[R + dy:_H - R + dy, R + dx:_W - R + dx] - nucleo).mean())
            if v < mejor[0]:
                mejor = (v, dx, dy)
    v, dx, dy = mejor
    if v > 0.9 * v0:  # la mejora es poca: no hay corrimiento claro
        v, dx, dy = v0, 0, 0
    out = {"corr": (-dx, -dy), "dif": round(v0, 1), "dif_min": round(v, 1), "tope": max(abs(dx), abs(dy)) >= R}
    if con_zoom:
        s, d, d1 = _zoom(A, B)
        out["zoom"] = (s, round(d, 1), round(d1, 1))
    return out


def _compuesta(a_jpg: bytes, b_jpg: bytes) -> bytes | None:
    """Antes (izquierda) y después (derecha) en una sola imagen de 640x240."""
    try:
        from PIL import Image

        lienzo = Image.new("RGB", (640, 240))
        for i, j in enumerate((a_jpg, b_jpg)):
            im = Image.open(io.BytesIO(j))
            im.draft("RGB", (320, 240))
            lienzo.paste(im.convert("RGB").resize((320, 240)), (320 * i, 0))
        buf = io.BytesIO()
        lienzo.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        return None


# ── flujo ─────────────────────────────────────────────────────────────────────


def _flujos_on() -> list[str]:
    prendidos = []
    for nombre, mod in (("flujo", flujo), ("flujo2", flujo2)):
        if mod.activa():
            continue
        try:
            mod.prender()
            prendidos.append(nombre)
        except Exception as e:
            _avisos.append(f"{nombre} no parte ({type(e).__name__}: {e})"[:160])
    return prendidos


def _acums() -> tuple[int, int, int, int]:
    return (flujo._acum[0], flujo._acum[1], flujo2._acum[0], flujo2._acum[1])


# ── una prueba medida ─────────────────────────────────────────────────────────


def _medir(plan, pot: float, seg: float, desc: str, cam: bool, antes: bytes | None, con_zoom: bool = False):
    """Mueve (o no, si plan es None) y mide. Devuelve (resultado, cuadro de después)."""
    r: dict = {"desc": desc, "pot": pot, "seg": seg}
    if cam and antes is None:
        antes = _pedir_cuadro(time.monotonic() - 0.2, 3.0)
    a = prev = _acums()
    camino = [0, 0]
    sq: list[list[int]] = [[], []]
    t0 = time.monotonic()
    if plan is not None:
        no = motores._lanzar(plan, pot, seg, "descubrir " + desc)
        if no:
            r["error"] = no
            return r, antes
    fin = None  # cuándo terminar de medir (un rato después de que pare el motor)
    while True:
        time.sleep(0.05)
        ahora = _acums()
        camino[0] += abs(ahora[0] - prev[0]) + abs(ahora[1] - prev[1])
        camino[1] += abs(ahora[2] - prev[2]) + abs(ahora[3] - prev[3])
        prev = ahora
        for i, mod in enumerate((flujo, flujo2)):
            q = mod._ultimo.get("squal") if mod._ultimo else None
            if q is not None:
                sq[i].append(q)
        t = time.monotonic()
        if _parar.is_set() and plan is not None and motores.activa():
            motores.parar()
            r["cortado"] = True
        if fin is None:
            if plan is None:
                fin = t0 + seg
            elif not motores.activa():
                fin = t + 0.4  # lo que siga rodando por inercia
            elif t - t0 > seg + 2.5:  # no debería pasar: motores.py se apaga solo
                motores.parar()
                fin = t + 0.4
        elif t >= fin:
            break
    r["n1"] = (prev[0] - a[0], prev[1] - a[1])
    r["n2"] = (prev[2] - a[2], prev[3] - a[3])
    r["camino"] = tuple(camino)
    r["squal"] = tuple(round(sum(x) / len(x)) if x else -1 for x in sq)
    r["vivo"] = (flujo.activa(), flujo2.activa())
    despues = antes
    if cam:
        despues = _pedir_cuadro(time.monotonic() + 0.2, 6.0)
        if antes is not None and despues is not None:
            try:
                r["cam"] = _comparar(antes, despues, con_zoom)
            except Exception as e:
                r["cam_error"] = f"{type(e).__name__}: {e}"[:120]
    return r, despues


def _juzgar(r: dict) -> None:
    """Pone el veredicto comparando con lo que se midió estando quieto."""
    if "n1" not in r:
        return
    base = _base or {}
    bm = base.get("m", 0.0)
    m = max(math.hypot(*r["n1"]), math.hypot(*r["n2"]))
    r["m"] = round(m, 1)
    if m >= max(10.0, 4 * bm + 4):
        r["flujo"] = "claro"
    elif m >= max(4.0, 2 * bm + 2):
        r["flujo"] = "debil"
    else:
        r["flujo"] = "nada"
    c = r.get("cam")
    r["camv"] = "sin"
    if c:
        s = math.hypot(*c["corr"])
        ruido = base.get("corr", 0.0)
        r["camv"] = "fuerte" if s >= max(3.0, 2 * ruido + 2) else ("leve" if s >= max(2.0, ruido + 1) else "quieta")
    r["movio"] = r["flujo"] == "claro" or r["camv"] == "fuerte"


def _linea(r: dict) -> str:
    if r.get("error"):
        return f"{r['desc']}: {r['error']}"
    p = [f"{r['desc']}@{r['pot']:g}%:" if r["pot"] else f"{r['desc']}:"]
    for i, k in enumerate(("n1", "n2")):
        if r["vivo"][i]:
            p.append(f"F{i + 1}({r[k][0]:+d},{r[k][1]:+d})")
        else:
            p.append(f"F{i + 1} sin sensor")
    p.append(f"camino {r['camino'][0]}/{r['camino'][1]} cal {r['squal'][0]}/{r['squal'][1]}")
    c = r.get("cam")
    if c:
        p.append(f"cam({c['corr'][0]:+d},{c['corr'][1]:+d}){'≥' if c['tope'] else ''} dif {c['dif']:g}")
        if "zoom" in c:
            s, d, d1 = c["zoom"]
            p.append(f"zoom {s:g} (dif {d:g} vs {d1:g})")
    elif r.get("cam_error"):
        p.append("cam falló: " + r["cam_error"])
    else:
        p.append("sin cámara")
    if "flujo" in r and r["pot"]:
        fl = {"claro": "FLUJO CLARO", "debil": "flujo débil", "nada": "sin flujo"}[r["flujo"]]
        cv = {"fuerte": "CÁMARA SE CORRIÓ", "leve": "cámara se corrió poco", "quieta": "cámara quieta", "sin": ""}[r["camv"]]
        p.append("→ " + fl + (", " + cv if cv else ""))
    if r.get("cortado"):
        p.append("(cortado)")
    return " ".join(p)


def _anotar(r: dict, antes: bytes | None, despues: bytes | None, mostrar: bool) -> None:
    _juzgar(r)
    with _lock:
        _resultados.append(r)
        del _resultados[:-150]
    _log(_linea(r))
    if antes and despues and (mostrar or (r.get("movio") and salida.hay_publico())):
        jpg = _compuesta(antes, despues)
        if jpg and len(jpg) < 300_000:
            salida.emitir({"t": "imagen", "nombre": "descubrir", "fmt": "jpeg",
                           "b64": base64.b64encode(jpg).decode("ascii")})


def _a_nota(texto: str) -> None:
    try:
        sello = time.strftime("%d-%m %H:%M")
        r = herramientas.nota(NOTA, f"[{sello}] {texto}", agregar=True)
        if "no la guardé" in r:  # se llenó: partir de nuevo con lo último
            herramientas.nota(NOTA, f"[{sello}] (nota reiniciada por tamaño) {texto}")
    except Exception:
        pass


# ── sesiones (hilo) ───────────────────────────────────────────────────────────


def _sesion(trabajo, cam: bool) -> None:
    global _fase, _base, _cuadro
    prendidos: list[str] = []
    try:
        _fase = "preparando sensores"
        del _avisos[:]
        prendidos = _flujos_on()
        antes = None
        if cam and not SIMULAR:
            _cuadro = (0.0, b"")
            camara.analizar("descubrir", _al_cuadro)
            antes = _pedir_cuadro(time.monotonic(), 14.0)
            if antes is None:
                _avisos.append("la cámara no entregó imagen: sigo solo con flujo")
                cam = False
        else:
            cam = False
        time.sleep(0.3)
        if _base is None or time.time() - _base.get("t", 0) > 180:
            _fase = "midiendo quieto"
            r, antes = _medir(None, 0.0, 1.0, "quieto", cam, antes)
            b = {"t": time.time(), "m": max(math.hypot(*r["n1"]), math.hypot(*r["n2"])), "linea": ""}
            if r.get("cam"):
                b["corr"] = math.hypot(*r["cam"]["corr"])
                b["dif"] = r["cam"]["dif"]
            b["linea"] = _linea(r)
            _base = b
            _log(b["linea"])
        if not _parar.is_set():
            trabajo(cam, antes)
    except Exception as e:
        _avisos.append(f"falló: {type(e).__name__}: {e}"[:200])
        _log(_avisos[-1], "error")
    finally:
        try:
            if motores.activa():
                motores.parar()
        except Exception:
            pass
        camara.dejar_de_analizar("descubrir")
        for nombre in prendidos:
            try:
                (flujo if nombre == "flujo" else flujo2).apagar()
            except Exception:
                pass
        _fase = ""


def _barrer(items: list[tuple[str, tuple]], niveles, seg: float, cam: bool, antes):
    """Prueba cada (desc, plan) subiendo de nivel solo lo que no se movió. Devuelve (cuántos se movieron, cuadro)."""
    global _fase
    pendientes = list(items)
    movidos = 0
    for pot in niveles:
        siguen = []
        for desc, plan in pendientes:
            if _parar.is_set():
                return movidos, antes
            _fase = f"probando {desc} al {pot:g} %"
            r, despues = _medir(plan, pot, seg, desc, cam, antes)
            _anotar(r, antes, despues, False)
            antes = despues
            if r.get("movio"):
                movidos += 1
            elif not r.get("error"):
                siguen.append((desc, plan))
            _parar.wait(0.25)
        pendientes = siguen
        if not pendientes:
            break
    return movidos, antes


def _trabajo_barrido(canales: list[int], niveles, seg: float, modo: str):
    def trabajo(cam: bool, antes) -> None:
        with _lock:
            del _resultados[:]
        movidos = 0
        if modo in ("canales", "auto"):
            items = [(f"c{ch}", ([ch], [], [])) for ch in canales]
            movidos, antes = _barrer(items, niveles, seg, cam, antes)
        if modo == "triples" or (modo == "auto" and movidos == 0 and not _parar.is_set()):
            items = []
            for p, a, b in motores.PRESETS["adafruit"]:
                items.append((f"pwm{p}+alto{a}+bajo{b}", ([p], [a], [b])))
                items.append((f"pwm{p}+alto{b}+bajo{a}", ([p], [b], [a])))
            _barrer(items, niveles, seg, cam, antes)
        txt = ("barrido CORTADO: " if _parar.is_set() else "barrido: ") + _informe(1500)
        _a_nota(txt)
        _log("barrido " + ("cortado" if _parar.is_set() else "terminado") + '; tabla con {"cmd":"descubrir","resultado":true}')

    return trabajo


def _trabajo_una(plan, pot: float, seg: float, desc: str):
    def trabajo(cam: bool, antes) -> None:
        global _fase
        _fase = f"probando {desc} al {pot:g} %"
        r, despues = _medir(plan, pot, seg, desc, cam, antes, con_zoom=True)
        _anotar(r, antes, despues, True)
        _a_nota(_linea(r))

    return trabajo


# ── informes ──────────────────────────────────────────────────────────────────


def _informe(tope: int = 1800) -> str:
    with _lock:
        rs = list(_resultados)
    if not rs:
        return "todavía no hay pruebas"
    con = [r for r in rs if r.get("movio") or r.get("flujo") == "debil" or r.get("camv") == "leve" or r.get("error")]
    sin: dict[str, float] = {}
    for r in rs:
        if r not in con:
            sin[r["desc"]] = max(sin.get(r["desc"], 0), r["pot"])
    for r in con:
        sin.pop(r["desc"], None)
    p = []
    if _base:
        p.append("base " + _base.get("linea", ""))
    p.append(f"{len(rs)} pruebas, {sum(1 for r in rs if r.get('movio'))} con movimiento claro")
    p.extend(_linea(r) for r in con)
    if sin:
        p.append("sin movimiento: " + ", ".join(f"{d} (hasta {v:g} %)" for d, v in sin.items()))
    if _avisos:
        p.append("avisos: " + "; ".join(_avisos))
    txt = " | ".join(p)
    return txt if len(txt) <= tope else txt[: tope - 12] + " … (cortado)"


def activa() -> bool:
    h = _hilo
    return h is not None and h.is_alive()


def estado() -> str:
    p = ["descubrir: " + (f"trabajando ({_fase or 'partiendo'})" if activa() else "quieto")]
    with _lock:
        ult = _resultados[-3:]
        n = len(_resultados)
    if _base:
        p.append("base " + _base.get("linea", ""))
    if n:
        p.append(f"{n} pruebas; últimas: " + " || ".join(_linea(r) for r in ult))
    else:
        p.append('sin pruebas todavía. Parte con {"cmd":"descubrir","on":true} (el robot se va a mover un poco: que'
                 ' tenga espacio) o prueba un canal con "canal":N')
    if _avisos:
        p.append("avisos: " + "; ".join(_avisos))
    return " | ".join(p)[:1900]


def detener() -> str:
    _parar.set()
    try:
        m = motores.parar()
    except Exception as e:
        m = f"motores: no pude parar ({type(e).__name__}: {e})"
    return ("descubrir: cortado" if activa() else "descubrir: no estaba trabajando") + " · " + m


def _partir(trabajo, cam: bool) -> str | None:
    global _hilo
    with _lock:
        if _hilo is not None and _hilo.is_alive():
            return 'descubrir: ya estoy en una prueba; espera o córtala con {"cmd":"descubrir","on":false}'
        if motores.activa():
            return "descubrir: los motores se están moviendo por otra orden; espera a que paren"
        _parar.clear()
        _hilo = threading.Thread(target=_sesion, args=(trabajo, cam), name="descubrir", daemon=True)
        _hilo.start()
    return None


def manejar(c: dict) -> str:
    if ("on" in c and not c.get("on")) or c.get("parar"):
        return detener()
    if c.get("resultado"):
        return "descubrir: " + _informe()

    cam = c.get("camara") is not False
    sentido = -1 if _num(c.get("sentido"), 1, -1, 1) < 0 else 1
    hacia = "+1" if sentido > 0 else "-1"

    if "canal" in c:
        ch = c.get("canal")
        if isinstance(ch, bool) or not isinstance(ch, int) or not 0 <= ch <= 15:
            return 'descubrir: "canal" va de 0 a 15'
        pot = _num(c.get("pot"), NIVELES[0], 1.0, motores.POT_MAX)
        seg = _num(c.get("seg"), 0.8, 0.2, 2.0)
        no = _partir(_trabajo_una(([ch], [], []), pot, seg, f"c{ch}"), cam)
        return no or f"descubrir: canal {ch} al {pot:g} % por {seg:g} s, midiendo con flujo y cámara; el resultado sale en unos segundos"

    if "motor" in c or c.get("todos") or "grupo" in c:
        cfg = motores._config()
        if not cfg["mapa"]:
            return 'descubrir: todavía no hay mapa en motores; elige uno con {"cmd":"motores","mapa":[[0,1],...]}'
        n = len(cfg["mapa"])
        if "motor" in c:
            cuales = [c.get("motor")]
        elif "grupo" in c:
            cuales = c.get("grupo")
        else:
            cuales = list(range(1, n + 1))
        if (not isinstance(cuales, list) or not cuales
                or any(isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= n for i in cuales)):
            return f"descubrir: los motores van de 1 a {n}"
        cuales = sorted(set(cuales))
        plan = motores._plan([i - 1 for i in cuales], sentido)
        if isinstance(plan, str):
            return "descubrir: " + plan
        varios = len(cuales) > 1
        pot = _num(c.get("pot"), NIVELES[0], 1.0, POT_TODOS if varios else motores.POT_MAX)
        seg = _num(c.get("seg"), 1.0 if varios else 0.8, 0.2, 1.5 if varios else 2.0)
        desc = ("M" + "+".join(str(i) for i in cuales)) + f" sentido {hacia}"
        no = _partir(_trabajo_una(plan, pot, seg, desc), cam)
        return no or f"descubrir: {desc} al {pot:g} % por {seg:g} s, midiendo con flujo y cámara; el resultado sale en unos segundos"

    if c.get("on") or "canales" in c:
        canales = c.get("canales", list(range(16)))
        if (not isinstance(canales, list) or not canales
                or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i <= 15 for i in canales)):
            return 'descubrir: "canales" es una lista de canales de 0 a 15'
        canales = sorted(set(canales))
        modo = str(c.get("modo", "auto")).strip().lower()
        if modo not in ("auto", "canales", "triples"):
            return 'descubrir: "modo" es "auto", "canales" o "triples"'
        niveles = (_num(c.get("pot"), NIVELES[0], 1.0, motores.POT_MAX),) if "pot" in c else NIVELES
        seg = _num(c.get("seg"), 0.8, 0.3, 1.5)
        no = _partir(_trabajo_barrido(canales, niveles, seg, modo), cam)
        return no or (
            f"descubrir: barriendo {len(canales)} canales de a uno ({', '.join(f'{x:g}' for x in niveles)} %, {seg:g} s"
            ' cada uno), midiendo con flujo' + (" y cámara" if cam else "") + '. Voy contando en la consola;'
            ' {"cmd":"descubrir"} dice cómo va y {"cmd":"descubrir","on":false} lo corta'
        )

    return estado()
