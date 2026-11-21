"""
Speaker del bicho: probar el parlante con pitidos y elegir por qué salida de audio sale el sonido.

    speaker.estado()            salida elegida, salidas que existen y cómo salió la última prueba
    speaker.elegir("audifonos") cambia la salida (alias, nombre de tarjeta o nombre ALSA) y la recuerda
    speaker.probar()            dos pitidos por la salida elegida (o un tono: probar(tono=440, seg=1))
    speaker.probar_todas()      recorre todas las salidas: 1 pitido en la primera, 2 en la segunda, ...
                                (sirve para saber, contando pitidos, dónde quedó enchufado el parlante)
    speaker.parar()             corta lo que esté sonando

Salidas que tiene este Pi (aplay -l): Headphones (jack de 3,5 mm del Pi), Array (la salida de audio
del ReSpeaker XVF3800, por USB) y vc4hdmi (HDMI). La lista se lee de /proc/asound (sin abrir nada).

La salida elegida es la MISMA que usa el sonido del gesto (gesto.parlante): hay una sola verdad.
Se guarda en <casa del bicho>/speaker.json para que sobreviva a reinicios y versiones nuevas.

El sonido se genera aquí (numpy) y se toca con aplay (WAV por stdin, con timeout) en un hilo daemon
que parte con el comando. Nada corre al importar salvo leer ese archivito (y ni eso en simulación).
El bicho no puede oírse: "aplay terminó bien" significa que ALSA aceptó el audio, no que alguien lo oyó.
"vol" solo cambia la amplitud del tono generado. El volumen del mezclador de ALSA es aparte: volumen()
lo sube y lo saca del silencio, y mezclador() lo muestra (ver la sección "Volumen del mezclador").
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import gesto
import herramientas
import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"
SR = 22050

_DEV_RE = re.compile(r"^[A-Za-z0-9:_,=.-]{1,40}$")
_ALIAS = {
    "audifonos": "plughw:Headphones", "audífonos": "plughw:Headphones", "jack": "plughw:Headphones",
    "headphones": "plughw:Headphones", "pi": "plughw:Headphones",
    "respeaker": "plughw:Array", "array": "plughw:Array", "microfono": "plughw:Array",
    "micrófono": "plughw:Array", "usb": "plughw:Array",
    "hdmi": "plughw:vc4hdmi",
}
_QUE_ES = {
    "Headphones": "jack de 3,5 mm del Pi",
    "Array": "salida de audio del ReSpeaker",
    "vc4hdmi": "HDMI",
}

_ocupado = threading.Lock()
_parar = threading.Event()
_proc: subprocess.Popen | None = None
_ultimo = "todavía no he probado el speaker"
_volumen: int | None = None  # volumen de ALSA guardado (0-100), o None si nunca se fijó


def _log(lvl: str, msg: str) -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "speaker: " + msg})


def _num(v, defecto: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = defecto
    if x != x:
        x = defecto
    return max(lo, min(x, hi))


# ── Qué salidas hay y cuál está elegida ──────────────────────────────────────

def salidas() -> list[str]:
    """Tarjetas de ALSA que pueden reproducir, por su id (por ejemplo Headphones, Array). Solo lee /proc."""
    if SIMULAR:
        return []
    try:
        ids = {}
        for linea in Path("/proc/asound/cards").read_text().splitlines():
            m = re.match(r"^\s*(\d+)\s+\[(\S+)\s*\]", linea)
            if m:
                ids[int(m.group(1))] = m.group(2)
        out = []
        for linea in Path("/proc/asound/pcm").read_text().splitlines():
            m = re.match(r"^(\d+)-\d+:", linea)
            if m and "playback" in linea:
                nombre = ids.get(int(m.group(1)))
                if nombre and nombre not in out:
                    out.append(nombre)
        return out
    except (OSError, ValueError):
        return []


def actual() -> str:
    return gesto._parlante


def _describir(dev: str) -> str:
    tarjeta = dev.split(":", 1)[-1].split(",")[0]
    que = _QUE_ES.get(tarjeta)
    return f"{dev} ({que})" if que else dev


def _archivo() -> Path:
    return herramientas._casa() / "speaker.json"


def _guardar(dev: str) -> bool:
    try:
        f = _archivo()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(".speaker.tmp")
        datos = {"salida": dev}
        if _volumen is not None:
            datos["volumen"] = _volumen
        tmp.write_text(json.dumps(datos), encoding="utf-8")
        os.replace(tmp, f)
        return True
    except OSError:
        return False


def _cargar() -> None:
    """Recupera la salida guardada (archivo chico; no abre ningún dispositivo). Nunca lanza."""
    global _volumen
    try:
        datos = json.loads(_archivo().read_text(encoding="utf-8"))
        dev = datos.get("salida")
        if isinstance(dev, str) and _DEV_RE.match(dev):
            gesto.parlante(dev)
        v = datos.get("volumen")
        if isinstance(v, (int, float)) and 0 <= v <= 100:
            _volumen = int(v)
            # Al arrancar, vuelve a poner el volumen guardado (alsactl store pide sudo y no se usa).
            threading.Thread(target=_reponer_volumen, args=(3.0,), name="speaker-vol", daemon=True).start()
    except Exception:
        pass


def elegir(v) -> str:
    txt = str(v or "").strip()
    dev = _ALIAS.get(txt.lower())
    hay = salidas()
    if dev is None:
        if txt in hay:
            dev = "plughw:" + txt
        elif _DEV_RE.match(txt) and (":" in txt or txt == "default"):
            dev = txt
        else:
            return ('speaker: no conozco esa salida. Usa "audifonos", "respeaker", "hdmi", el nombre de una '
                    "tarjeta (" + (", ".join(hay) or "no veo ninguna") + ") o un nombre ALSA como plughw:Headphones")
    gesto.parlante(dev)
    guardado = "" if SIMULAR else (" y lo dejé guardado" if _guardar(dev) else " (no pude guardarlo: dura hasta que me reinicie)")
    aviso = ""
    tarjeta = dev.split(":", 1)[-1].split(",")[0]
    if not SIMULAR and ":" in dev and tarjeta not in hay and not tarjeta.isdigit():
        aviso = f" — ojo: no veo una tarjeta {tarjeta} (hay: {', '.join(hay) or 'ninguna'})"
    return f"speaker: ahora el sonido sale por {_describir(dev)}{guardado}{aviso}"


# ── Volumen del mezclador (ALSA) ─────────────────────────────────────────────
# Cada tarjeta tiene su propio volumen en ALSA, aparte de la amplitud del tono. El ReSpeaker XVF3800 trae
# el suyo (en alsamixer se llama PCM-1, o sea el control 'PCM',1) y puede venir bajo o en silencio: aplay
# termina bien y no se oye nada. La wiki de Seeed dice subirlo al 100 %. volumen() sube TODOS los controles
# de reproducción de la tarjeta y los saca del silencio; queda guardado en speaker.json y se vuelve a poner
# al arrancar y antes de cada prueba (si se desenchufa el ReSpeaker, ALSA lo olvida).

_TARJETA_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")
_VOL = {"pvolume", "pvolume-joined", "volume", "volume-joined"}
_SW = {"pswitch", "pswitch-joined", "switch", "switch-joined"}


def _tarjeta(dev: str | None = None) -> str:
    t = (dev or actual()).split(":", 1)[-1].split(",")[0]
    return t[5:] if t.startswith("CARD=") else t


def _amixer(args: list) -> tuple[int, str]:
    try:
        r = subprocess.run(["amixer", *args], capture_output=True, text=True, timeout=5)
    except FileNotFoundError:
        return 127, "no está amixer (paquete alsa-utils)"
    except subprocess.TimeoutExpired:
        return 124, "amixer no contestó en 5 s"
    return r.returncode, (r.stdout + r.stderr)


def _controles(tarjeta: str) -> list[tuple[str, set, str]]:
    """[(id "Nombre,índice", capacidades, texto de sget)] de los controles simples de la tarjeta."""
    rc, out = _amixer(["-c", tarjeta, "scontents"])
    if rc != 0:
        raise RuntimeError(out.strip()[-160:] or f"amixer devolvió {rc}")
    res = []
    for bloque in re.split(r"(?m)^(?=Simple mixer control )", out):
        m = re.match(r"Simple mixer control '(.*)',(\d+)", bloque)
        if not m:
            continue
        mc = re.search(r"Capabilities:\s*(.*)", bloque)
        caps = set(mc.group(1).split()) if mc else set()
        res.append((f"{m.group(1)},{m.group(2)}", caps, bloque))
    return res


def _resumen_control(cid: str, caps: set, texto: str) -> str | None:
    """'PCM,1: 50% sonando' para controles de reproducción; None si es solo de captura."""
    if not (caps & (_VOL | _SW)):
        return None
    pct, sw = [], []
    for linea in texto.splitlines():
        if "Playback" not in linea or "[" not in linea or "Limits" in linea:
            continue
        linea = linea.split("Capture")[0]
        pct += re.findall(r"\[(\d+)%\]", linea)
        sw += re.findall(r"\[(on|off)\]", linea)
    partes = []
    if pct:
        partes.append("/".join(dict.fromkeys(p + "%" for p in pct)))
    if sw:
        partes.append("EN SILENCIO" if "off" in sw else "sonando")
    return f"{cid}: " + (" ".join(partes) or "?")


def mezclador(tarjeta=None) -> str:
    if SIMULAR:
        return "speaker: mezclador simulado (sin hardware)"
    t = str(tarjeta or _tarjeta())
    if not _TARJETA_RE.match(t):
        return "speaker: nombre de tarjeta raro: " + t[:40]
    try:
        ctl = _controles(t)
    except RuntimeError as e:
        return f"speaker: no pude leer el mezclador de {t}: {e}"
    lineas = [r for r in (_resumen_control(*c) for c in ctl) if r]
    guardado = f" · volumen guardado {_volumen}%" if _volumen is not None else ""
    if not lineas:
        return f"speaker: la tarjeta {t} no tiene controles de reproducción en ALSA{guardado}"
    return f"speaker: mezclador de {t}: " + " · ".join(lineas) + guardado


def _fijar(t: str, pct: int) -> list[str]:
    hechos = []
    for cid, caps, _texto in _controles(t):
        args = []
        if caps & _VOL:
            args.append(f"{pct}%")
        if caps & _SW:
            args.append("unmute" if pct > 0 else "mute")
        if not args:
            continue
        rc, out = _amixer(["-c", t, "-q", "sset", cid, *args])
        hechos.append(cid if rc == 0 else f"{cid} (falló: {out.strip()[-80:]})")
    return hechos


def volumen(v, tarjeta=None) -> str:
    """Sube (o baja) todos los controles de reproducción de la tarjeta a v % y los saca del silencio."""
    global _volumen
    if SIMULAR:
        return "speaker: volumen simulado (sin hardware)"
    pct = int(_num(v, 100, 0, 100))
    t = str(tarjeta or _tarjeta())
    if not _TARJETA_RE.match(t):
        return "speaker: nombre de tarjeta raro: " + t[:40]
    try:
        hechos = _fijar(t, pct)
    except RuntimeError as e:
        return f"speaker: no pude cambiar el volumen de {t}: {e}"
    if not hechos:
        return f"speaker: la tarjeta {t} no tiene controles de reproducción que subir"
    _volumen = pct
    guardado = " (guardado)" if _guardar(actual()) else " (no pude guardarlo)"
    return f"speaker: volumen de {t} al {pct}% en {', '.join(hechos)}{guardado} → " + mezclador(t).removeprefix("speaker: ")


_t_volumen = 0.0


def _reponer_volumen(espera: float = 0.0, dev: str | None = None) -> None:
    """Vuelve a poner el volumen guardado en la tarjeta (al arrancar y antes de tocar, a lo más cada 30 s,
    para no atrasar cada sonido con amixer). Nunca lanza."""
    global _t_volumen
    if _volumen is None or SIMULAR:
        return
    if not espera and time.monotonic() - _t_volumen < 30:
        return
    _t_volumen = time.monotonic()
    try:
        if espera:
            time.sleep(espera)
        t = _tarjeta(dev)
        if _TARJETA_RE.match(t):
            _fijar(t, _volumen)
    except Exception:
        pass


# ── Sonido ───────────────────────────────────────────────────────────────────

def _wav(patron: list, vol: float) -> bytes:
    """patron: lista de (frecuencia en Hz, segundos); frecuencia 0 = silencio. WAV mono de 16 bits."""
    import io
    import wave

    import numpy as np

    partes = []
    for f, dur in patron:
        n = max(1, int(SR * dur))
        if f <= 0:
            partes.append(np.zeros(n))
            continue
        t = np.arange(n) / SR
        env = np.minimum(1.0, np.minimum(t / 0.01, (dur - t) / 0.02)).clip(0.0, 1.0)
        partes.append(np.sin(2 * np.pi * f * t) * env)
    partes.append(np.zeros(int(SR * 0.15)))  # colita de silencio para que no se corte el final
    x = np.concatenate(partes) * (0.9 * vol / 100.0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _tocar_en(dev: str, data: bytes, dura: float) -> tuple[bool, str]:
    global _proc
    _reponer_volumen(0.0, dev)
    p = subprocess.Popen(["aplay", "-q", "-D", dev, "-"], stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _proc = p
    try:
        try:
            _, err = p.communicate(data, timeout=dura + 6)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            return False, f"aplay no terminó en {dura + 6:.0f} s"
    finally:
        _proc = None
    if _parar.is_set():
        return False, "cortado"
    if p.returncode == 0:
        return True, "aplay terminó bien"
    lineas = (err or b"").decode("utf-8", "replace").strip().splitlines()
    return False, (lineas[-1][:120] if lineas else f"aplay devolvió {p.returncode}")


def _trabajo(lista: list, vol: float, callado: bool = False) -> None:
    """lista: [(dispositivo, patron)] o [(dispositivo, wav_bytes, segundos)]. Corre en su hilo y suelta
    _ocupado al terminar. callado: no anota ni avisa el resultado si salió bien (sonidos de expresar)."""
    global _ultimo
    try:
        res = []
        todo_bien = True
        for i, item in enumerate(lista):
            dev, patron = item[0], item[1]
            if _parar.is_set():
                break
            if i and _parar.wait(0.6):
                break
            try:
                if isinstance(patron, (bytes, bytearray)):
                    ok, msg = _tocar_en(dev, bytes(patron), float(item[2]))
                else:
                    ok, msg = _tocar_en(dev, _wav(patron, vol), sum(d for _, d in patron))
            except Exception as e:
                ok, msg = False, f"{type(e).__name__}: {e}"[:120]
            todo_bien = todo_bien and ok
            res.append(f"{dev}: {'OK, ' if ok else 'FALLÓ, '}{msg}")
        if _parar.is_set():
            res.append("lo cortaron")
        if callado and todo_bien:
            return
        _ultimo = f"última prueba ({time.strftime('%H:%M:%S')}): " + (" | ".join(res) or "nada")
        _log("info" if todo_bien else "warn", _ultimo)
    except Exception as e:
        _ultimo = f"la prueba falló: {type(e).__name__}: {e}"[:200]
        _log("error", _ultimo)
    finally:
        _ocupado.release()


def _lanzar(lista: list, vol: float, callado: bool = False) -> bool:
    if not _ocupado.acquire(blocking=False):
        return False
    _parar.clear()
    try:
        threading.Thread(target=_trabajo, args=(lista, vol, callado), name="speaker", daemon=True).start()
    except Exception:
        _ocupado.release()
        raise
    return True


def tocar_wav(data: bytes, segundos: float) -> bool:
    """Toca un WAV ya hecho por la salida elegida, sin bloquear. False si ya estaba sonando algo."""
    if SIMULAR:
        return True
    return _lanzar([(actual(), data, segundos)], 100, callado=True)


def sonando() -> bool:
    return _ocupado.locked()


def probar(tono=None, seg=None, vol=None) -> str:
    if SIMULAR:
        return "speaker: simulado (sin hardware no suena nada)"
    v = _num(vol, 60, 1, 100)
    if tono is None and seg is None:
        patron = [(660.0, 0.25), (0.0, 0.08), (880.0, 0.35)]
        que = "dos pitidos"
    else:
        f = _num(tono, 440, 50, 8000)
        s = _num(seg, 1.0, 0.1, 5.0)
        patron = [(f, s)]
        que = f"un tono de {f:g} Hz por {s:g} s"
    dev = actual()
    if not _lanzar([(dev, patron)], v):
        return 'speaker: ya está sonando algo (para cortarlo: {"cmd":"speaker","on":false})'
    return f"speaker: tocando {que} por {_describir(dev)}, vol {v:g}%… el resultado sale en la consola y en el estado"


def probar_todas(vol=None) -> str:
    if SIMULAR:
        return "speaker: simulado (sin hardware no suena nada)"
    hay = salidas()
    if not hay:
        return "speaker: no veo ninguna salida de audio en /proc/asound"
    v = _num(vol, 60, 1, 100)
    lista, guia = [], []
    for i, nombre in enumerate(hay):
        patron = []
        for _ in range(i + 1):
            patron += [(880.0, 0.22), (0.0, 0.15)]
        lista.append(("plughw:" + nombre, patron))
        guia.append(f"{i + 1} pitido{'s' if i else ''} = {_describir('plughw:' + nombre)}")
    if not _lanzar(lista, v):
        return 'speaker: ya está sonando algo (para cortarlo: {"cmd":"speaker","on":false})'
    return ("speaker: recorro todas las salidas; cuenta los pitidos que oigas: " + ", ".join(guia)
            + '. Después elige con {"cmd":"speaker","salida":"..."}')


def parar() -> str:
    if not sonando():
        return "speaker: no estaba sonando nada"
    _parar.set()
    p = _proc
    if p is not None:
        try:
            p.kill()
        except Exception:
            pass
    return "speaker: cortado"


def estado() -> str:
    if SIMULAR:
        return "speaker: simulado (sin hardware)"
    hay = salidas()
    p = ["speaker: salida elegida " + _describir(actual()),
         "salidas que hay: " + (", ".join(_describir("plughw:" + n) for n in hay) or "ninguna"),
         "sonando ahora" if sonando() else "en silencio",
         (f"volumen ALSA guardado {_volumen}%" if _volumen is not None
          else 'volumen ALSA sin fijar (míralo con "mezclador":true, súbelo con "volumen":100)'),
         _ultimo,
         'prueba con "probar":true, o "todas":true para descubrir dónde está enchufado']
    return " · ".join(p)


if not SIMULAR:
    _cargar()
