"""
Gesto del bicho: reconoce (aproximadamente) el dedo del medio frente a la cámara y se enoja:
parpadea la luz roja (GPIO 22, luces.py) unos segundos y además toca un sonido.

    gesto.prender()        empieza a mirar (usa los cuadros de camara.py, 2 por segundo)
    gesto.apagar()         deja de mirar y suelta la cámara si nadie más la usa
    gesto.estado()         qué está pasando y por qué descartó lo último que vio
    gesto.probar_enojo()   parpadea la luz roja una vez, como si hubiera visto el gesto
    gesto.probar_sonido()  toca el sonido una vez, para probar el parlante
    gesto.ver()            durante 20 s manda a Vista (imagen "gesto", una por segundo) la máscara de piel

Cómo reconoce: no hay OpenCV ni redes neuronales en este Pi, así que es una regla geométrica con
numpy + PIL sobre el cuadro achicado a 320x240:
  1. marca los píxeles con color de piel (YCbCr);
  2. busca una "punta": una franja delgada y vertical de piel sin nada encima (el dedo, hacia arriba);
  3. la sigue hacia abajo hasta que se ensancha de golpe (el puño);
  4. exige que el dedo sea largo, que el puño mida entre 2,5 y 7 dedos de ancho, que el dedo salga
     del CENTRO del puño (el índice y el pulgar salen de un costado) y que no haya otros dedos arriba.
Debe verse en 2 cuadros seguidos (~1 s). Reacciona una vez por cada vez que aparece el gesto.
Es una aproximación: funciona mejor con la mano a un lado de la cara, el dedo hacia arriba y un
fondo que no sea color piel. No distingue perfecto el dedo del medio de otro dedo solo.

Calibración del color (medido con "ver" en la sala donde vive el bicho): la pared crema da
Cb≈118, Cr≈136 y la piel Cr≈150 o más; por eso se pide Cr≥141 y Cr−Cb≥22, que deja fuera la pared.

La respuesta principal es la luz roja (todavía no hay parlante conectado): parpadeo rápido de
ENOJO_SEG segundos, sin bloquear (lo hace gpiozero en su propio hilo) y termina apagada.
El sonido se mantiene: es un WAV que se genera aquí mismo y se toca con aplay por la salida de
audífonos del Pi (plughw:Headphones; se cambia con BICHO_PARLANTE o con gesto.parlante()).
Nada corre al importar.
"""
from __future__ import annotations

import base64
import io
import os
import re
import subprocess
import threading
import time

import camara
import luces
import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"
WAV = os.environ.get("BICHO_GESTO_WAV", "/tmp/bicho_gesto.wav")
AW, AH = 320, 240  # tamaño al que se analiza
WMIN, WMAX = 4, 44  # ancho del dedo en píxeles (de 320)
LMIN = 12  # largo mínimo del dedo
NECESARIOS = 2  # cuadros seguidos con el gesto para darlo por visto
VER_SEG = 20.0  # cuánto dura el modo "ver"
# Color de piel en YCbCr
Y_MIN, CB_MIN, CB_MAX, CR_MIN, CR_MAX = 50, 77, 130, 141, 185
CR_CB_MIN = 22  # Cr − Cb mínimo: separa la piel de paredes crema

# Enojo: parpadeo rápido de la luz roja
ENOJO_COLOR = "rojo"
ENOJO_SEG = 3.0  # cuánto dura el parpadeo
ENOJO_PERIODO = 0.25  # segundos por parpadeo (rápido = enojado)

_PARLANTE_RE = re.compile(r"^[A-Za-z0-9:_,=.-]{1,40}$")
_parlante = os.environ.get("BICHO_PARLANTE", "plughw:Headphones")

_seguidos = 0
_ausentes = 0
_armado = True
_dedo = False
_veces = 0
_cuadros = 0
_diag = ""
_color = ""
_error: str | None = None
_ms = 0.0
_ver_hasta = 0.0  # time.monotonic() hasta el que se manda la máscara
_ver_ultima = 0.0
_sonando = threading.Lock()
_sonido_txt = "todavía no he tocado el sonido"
_enojo_hasta = 0.0  # time.monotonic() hasta el que parpadea la roja por enojo
_enojo_txt = "todavía no me he enojado"


def _log(lvl: str, msg: str) -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "gesto: " + msg})


# ── Luz roja enojada ─────────────────────────────────────────────────────────

def _enojarse() -> bool:
    """Parpadea la luz roja ENOJO_SEG segundos sin bloquear. Nunca lanza. True si partió."""
    global _enojo_hasta, _enojo_txt
    try:
        n = max(1, int(round(ENOJO_SEG / ENOJO_PERIODO)))
        luces.parpadear(ENOJO_COLOR, n, ENOJO_PERIODO)
        _enojo_hasta = time.monotonic() + n * ENOJO_PERIODO
        _enojo_txt = (f"último enojo: luz roja parpadeando {ENOJO_SEG:g} s a las "
                      f"{time.strftime('%H:%M:%S')} ({luces.donde(ENOJO_COLOR)})")
        return True
    except Exception as e:
        _enojo_txt = f"la luz roja falló: {type(e).__name__}: {e}"[:200]
        _log("error", _enojo_txt)
        return False


def _calmarse() -> None:
    """Si la roja está parpadeando por enojo, la apaga (no toca una roja prendida por otro comando)."""
    global _enojo_hasta
    if time.monotonic() < _enojo_hasta:
        try:
            luces.apagar(ENOJO_COLOR)
        except Exception:
            pass
    _enojo_hasta = 0.0


# ── Sonido ───────────────────────────────────────────────────────────────────

def _hacer_wav() -> None:
    """Tres notas que bajan (un "wah wah waaah"), 22050 Hz mono 16 bits."""
    import wave

    import numpy as np

    sr = 22050
    partes = []
    for f, dur in ((392.0, 0.16), (311.0, 0.16), (233.0, 0.45)):
        t = np.arange(int(sr * dur)) / sr
        o = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.25 * np.sin(6 * np.pi * f * t)
        env = np.minimum(1.0, np.minimum(t / 0.01, (dur - t) / 0.04))
        partes.append(o * env)
        partes.append(np.zeros(int(sr * 0.03)))
    x = np.concatenate(partes)
    x = x / float(np.abs(x).max()) * 0.7
    pcm = (x * 32767).astype("<i2").tobytes()
    tmp = WAV + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    os.replace(tmp, WAV)


def _tocar() -> None:
    global _sonido_txt
    try:
        if not os.path.isfile(WAV):
            _hacer_wav()
        errores = []
        for dev in dict.fromkeys((_parlante, "default")):
            try:
                r = subprocess.run(["aplay", "-q", "-D", dev, WAV], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, timeout=8)
            except subprocess.TimeoutExpired:
                errores.append(f"{dev}: aplay no terminó en 8 s")
                continue
            if r.returncode == 0:
                _sonido_txt = f"último sonido: tocado por {dev} a las {time.strftime('%H:%M:%S')}"
                _log("info", f"sonido tocado por {dev}")
                return
            lineas = r.stderr.decode("utf-8", "replace").strip().splitlines()
            errores.append(f"{dev}: " + (lineas[-1][:120] if lineas else f"código {r.returncode}"))
        _sonido_txt = "el sonido falló: " + " | ".join(errores)
        _log("error", _sonido_txt)
    except Exception as e:
        _sonido_txt = f"el sonido falló: {type(e).__name__}: {e}"[:200]
        _log("error", _sonido_txt)
    finally:
        _sonando.release()


def _sonar() -> bool:
    """Toca el sonido en un hilo aparte. False si ya estaba sonando."""
    if not _sonando.acquire(blocking=False):
        return False
    try:
        threading.Thread(target=_tocar, name="gesto-sonido", daemon=True).start()
    except Exception:
        _sonando.release()
        raise
    return True


# ── Visión ───────────────────────────────────────────────────────────────────

def _med(v: list) -> float:
    s = sorted(v)
    return s[len(s) // 2]


def _mascara(jpg: bytes):
    """Devuelve (máscara de piel, imagen YCbCr como arreglo)."""
    import numpy as np
    from PIL import Image

    im = Image.open(io.BytesIO(jpg))
    im.draft("YCbCr", (AW, AH))  # el decodificador JPEG entrega directo a mitad de tamaño: barato
    if im.mode != "YCbCr":
        im = im.convert("YCbCr")
    if im.size[0] > AW:
        im = im.resize((AW, max(1, round(im.size[1] * AW / im.size[0]))))
    a = np.asarray(im)
    y, cb, cr = a[..., 0], a[..., 1], a[..., 2]
    m = (y >= Y_MIN) & (cb >= CB_MIN) & (cb <= CB_MAX) & (cr >= CR_MIN) & (cr <= CR_MAX)
    m &= (cr.astype(np.int16) - cb.astype(np.int16)) >= CR_CB_MIN
    # mayoría 3x3 para limpiar puntos sueltos
    h, w = m.shape
    p = np.pad(m.astype(np.uint8), 1)
    s = np.zeros((h, w), dtype=np.uint8)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            s += p[dy:dy + h, dx:dx + w]
    return s >= 5, a


def _seguir(runs: list, y0: int, r0: tuple, h: int):
    """Desde una punta baja siguiendo la franja hasta que se ensancha. Devuelve (pista, y_base) o None."""
    pista = [r0]
    cur = r0
    y = y0 + 1
    while y < h:
        mejor, ov = None, 0
        for r in runs[y]:
            o = min(r[1], cur[1]) - max(r[0], cur[0])
            if o > ov:
                ov, mejor = o, r
        if mejor is None:
            return None  # se acabó sin puño debajo: mancha suelta
        w = mejor[1] - mejor[0]
        n = len(pista)
        if n >= 4:
            med = _med([b - a for a, b in pista[n // 3:]])
            if w > 1.6 * med + 1:
                return pista, y
        elif w > WMAX:
            return None
        pista.append(mejor)
        cur = mejor
        y += 1
    return None


def _evaluar(y0: int, pista: list, base: int, runs: list, h: int):
    n = len(pista)
    cola = pista[n // 3:]
    wf = _med([b - a for a, b in cola])
    cx = sum((a + b) / 2 for a, b in cola) / len(cola)
    L = base - y0
    info = {"x": cx, "y0": y0, "y1": base, "wf": wf, "L": L}
    if wf < WMIN:
        return False, info, "muy delgado"
    if wf > WMAX:
        return False, info, "muy ancho"
    if L < max(LMIN, 1.8 * wf):
        return False, info, "muy corto para ser un dedo estirado"
    ya = base + int(round(0.5 * wf))
    yb = min(h, base + int(round(2.5 * wf)) + 1)
    if yb - ya < 3:
        return False, info, "no se ve el puño (se sale del cuadro)"
    fa, fb = cx - wf / 2, cx + wf / 2
    x0s, x1s = [], []
    for y in range(ya, yb):
        mejor, ov = None, 0
        for a, b in runs[y]:
            o = min(b, fb) - max(a, fa)
            if o > ov:
                ov, mejor = o, (a, b)
        if mejor:
            x0s.append(mejor[0])
            x1s.append(mejor[1])
    if len(x0s) < 0.8 * (yb - ya):
        return False, info, "sin puño debajo"
    X0, X1 = _med(x0s), _med(x1s)
    W = X1 - X0
    rel = (cx - X0) / W if W else 0.0
    info.update({"X0": X0, "X1": X1, "W": W, "rel": rel, "ya": ya, "yb": yb})
    if W < 2.5 * wf:
        return False, info, "lo de abajo es angosto, no parece puño"
    if W > 7 * wf:
        return False, info, "lo de abajo es muy ancho para ser un puño"
    if not 0.3 <= rel <= 0.7:
        return False, info, "el dedo sale del costado del puño (¿índice o pulgar?)"
    yt = y0 + max(3, int(0.6 * L))
    otros = 0
    for i, y in enumerate(range(y0, yt)):
        mio = pista[i]
        for a, b in runs[y]:
            if (a, b) != mio and b - a >= 3 and X0 - wf <= (a + b) / 2 <= X1 + wf:
                otros += 1
                break
    if otros > 0.25 * (yt - y0):
        return False, info, "hay más dedos (o piel) al lado"
    return True, info, ""


def _detectar(m):
    """Devuelve (info del dedo o None, texto de diagnóstico, info del mejor descartado o None)."""
    import numpy as np

    h, w = m.shape
    piel = 100.0 * float(m.mean())
    d = np.diff(np.pad(m.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    runs = []
    for y in range(h):
        fila = d[y]
        runs.append(list(zip(np.flatnonzero(fila == 1).tolist(), np.flatnonzero(fila == -1).tolist())))
    bueno = None
    casi, casi_por = None, ""
    puntas = 0
    for y in range(2, h - LMIN):
        for r in runs[y]:
            wr = r[1] - r[0]
            if wr < 2 or wr > WMAX:
                continue
            if m[y - 1, max(0, r[0] - 1):r[1] + 1].any():
                continue  # tiene piel encima: no es una punta
            puntas += 1
            if puntas > 400:
                break
            s = _seguir(runs, y, r, h)
            if s is None:
                continue
            pista, base = s
            if base - y < LMIN:
                continue
            ok, info, por = _evaluar(y, pista, base, runs, h)
            if ok:
                if bueno is None or info["L"] > bueno["L"]:
                    bueno = info
            elif casi is None or info["L"] > casi["L"]:
                casi, casi_por = info, por
        if puntas > 400:
            break
    txt = f"piel {piel:.0f}% del cuadro, {puntas} puntas"
    if bueno:
        txt += (f" · DEDO: largo {bueno['L']} px, ancho {bueno['wf']} px, puño {bueno['W']} px, "
                f"posición {bueno['rel']:.2f}")
    elif casi:
        txt += f" · lo más parecido (largo {casi['L']}, ancho {casi['wf']}"
        if "rel" in casi:
            txt += f", puño {casi['W']}, posición {casi['rel']:.2f}"
        txt += f") lo descarté: {casi_por}"
    else:
        txt += " · nada con forma de dedo"
    return bueno, txt, casi


def _emitir_mascara(m, bueno, casi) -> None:
    import numpy as np
    from PIL import Image, ImageDraw

    im = Image.fromarray(m.astype(np.uint8) * 255).convert("RGB")
    dib = ImageDraw.Draw(im)
    for info, color in ((casi, (255, 160, 0)), (bueno, (255, 0, 0))):
        if not info:
            continue
        dib.line([(info["x"], info["y0"]), (info["x"], info["y1"])], fill=color, width=2)
        if "X0" in info:
            dib.rectangle([info["X0"], info["ya"], info["X1"], info["yb"]], outline=(0, 200, 0))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=70)
    salida.emitir({"t": "imagen", "nombre": "gesto", "fmt": "jpeg",
                   "b64": base64.b64encode(buf.getvalue()).decode("ascii")})


def _colores(a, m) -> str:
    """Color medio (Y, Cb, Cr) en una grilla 3x3 del cuadro y de lo marcado como piel: para calibrar."""
    h, w = m.shape
    celdas = []
    for j in range(3):
        for i in range(3):
            c = a[j * h // 3 + h // 12:(j + 1) * h // 3 - h // 12, i * w // 3 + w // 12:(i + 1) * w // 3 - w // 12]
            v = c.reshape(-1, 3).mean(axis=0)
            celdas.append(f"{v[0]:.0f}/{v[1]:.0f}/{v[2]:.0f}")
    txt = "Y/Cb/Cr por zona (3x3, de arriba-izq a abajo-der): " + " ".join(celdas)
    if m.any():
        v = a[m].mean(axis=0)
        txt += f" · media de lo marcado piel: {v[0]:.0f}/{v[1]:.0f}/{v[2]:.0f}"
    return txt


def _analizar(jpg: bytes) -> None:
    """Lo llama el hilo de la cámara con cada cuadro."""
    global _seguidos, _ausentes, _armado, _dedo, _veces, _cuadros, _diag, _error, _ms, _ver_ultima, _color
    t0 = time.monotonic()
    try:
        m, a = _mascara(jpg)
        bueno, txt, casi = _detectar(m)
        _ms = (time.monotonic() - t0) * 1000
        if t0 < _ver_hasta and t0 - _ver_ultima >= 0.9:
            _ver_ultima = t0
            _color = _colores(a, m)
            _emitir_mascara(m, bueno, casi)
    except Exception as e:
        nuevo = f"{type(e).__name__}: {e}"[:200]
        if nuevo != _error:
            _log("error", "no pude analizar el cuadro: " + nuevo)
        _error = nuevo
        return
    _error = None
    _cuadros += 1
    _diag = txt
    if bueno:
        _seguidos += 1
        _ausentes = 0
    else:
        _ausentes += 1
        if _ausentes >= 2:
            _seguidos = 0
            _armado = True
    _dedo = _seguidos >= NECESARIOS
    if _dedo and _armado:
        _armado = False
        _veces += 1
        _enojarse()  # la luz roja es la respuesta principal; no lanza
        try:
            _sonar()
        except Exception as e:  # el sonido es secundario: que no bote el análisis
            _log("error", f"no pude tocar el sonido: {type(e).__name__}: {e}")
        _log("info", f"vi el dedo del medio (van {_veces}): parpadeo la luz roja {ENOJO_SEG:g} s y toco el sonido")


# ── Lo que usan comandos.py y sensores.py ────────────────────────────────────

def activo() -> bool:
    return camara.analizando("gesto")


def datos() -> dict | None:
    if not activo():
        return None
    return {"dedo": _dedo, "veces": _veces, "enojado": time.monotonic() < _enojo_hasta}


def prender() -> str:
    global _seguidos, _ausentes, _armado, _dedo, _error
    if SIMULAR:
        return "gesto: simulado, sin cámara no miro nada"
    if activo():
        return "ya estaba mirando si me muestran el dedo del medio"
    _seguidos = _ausentes = 0
    _armado = True
    _dedo = False
    _error = None
    camara.analizar("gesto", _analizar)
    return ("mirando: si veo el dedo del medio (hacia arriba, puño debajo, ~1 s) me enojo: parpadeo la luz "
            f"roja {ENOJO_SEG:g} s ({luces.donde(ENOJO_COLOR)}) y toco un sonido por {_parlante}. "
            "Reviso 2 cuadros por segundo aunque nadie mire la web")


def apagar() -> str:
    global _dedo, _seguidos, _ver_hasta
    camara.dejar_de_analizar("gesto")
    _dedo = False
    _seguidos = 0
    _ver_hasta = 0.0
    _calmarse()
    return "ya no miro gestos"


def probar_enojo() -> str:
    """Parpadea la roja como si hubiera visto el gesto (también sirve en simulación)."""
    if _enojarse():
        return f"enojado: luz roja parpadeando {ENOJO_SEG:g} s ({luces.donde(ENOJO_COLOR)})"
    return _enojo_txt


def calmar() -> str:
    _calmarse()
    return "calmado: corté el parpadeo de enojo"


def probar_sonido() -> str:
    if SIMULAR:
        return "gesto: sonido simulado (sin hardware)"
    if _sonar():
        return f"tocando el sonido por {_parlante}… (el resultado sale en la consola y en gesto)"
    return "el sonido ya está sonando"


def parlante(dev) -> str:
    global _parlante
    dev = str(dev or "").strip()
    if not _PARLANTE_RE.match(dev):
        return "gesto: el parlante es un nombre de ALSA, por ejemplo plughw:Headphones o plughw:Array"
    _parlante = dev
    return f"gesto: ahora el sonido sale por {dev} (hasta que me reinicie)"


def ver() -> str:
    global _ver_hasta
    if SIMULAR:
        return "gesto: simulado"
    if not activo():
        return 'gesto: primero préndeme con {"cmd":"gesto","on":true}'
    _ver_hasta = time.monotonic() + VER_SEG
    return (f'durante {VER_SEG:.0f} s mando a Vista la imagen "gesto" (una por segundo): '
            "blanco = piel, rojo = dedo, naranjo = casi")


def estado() -> str:
    if SIMULAR:
        return "gesto: simulado (sin hardware)"
    if not activo():
        p = ["gesto apagado"]
        err = camara.ultimo_error()
        if err:
            p.append("la cámara dijo: " + err)
    else:
        p = ["mirando gestos", f"{_cuadros} cuadros revisados ({_ms:.0f} ms cada uno)",
             "dedo del medio a la vista" if _dedo else "sin dedo a la vista"]
        if _diag:
            p.append(_diag)
        if _color and time.monotonic() < _ver_hasta + 60:
            p.append(_color)
    p.append(f"lo he visto {_veces} veces")
    p.append(_enojo_txt)
    p.append(_sonido_txt)
    p.append("parlante " + _parlante)
    if _error:
        p.append("error al analizar: " + _error)
    return " · ".join(p)
