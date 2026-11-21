"""
Oído del bicho: arreglo de micrófonos ReSpeaker XVF3800 (USB, 4 micrófonos).

Hace dos cosas, cada una en su hilo:
  - le pregunta al chip desde qué ángulo viene la voz (0 a 359°) y si hay alguien hablando;
  - graba el micrófono y corta el audio en frases: desde que alguien empieza a hablar hasta que calla.

sensores.py publica estado() (ángulo y voz en vivo) y bichod.py recoge las frases con frases()
y las manda al relé, que las transcribe. Sin el ReSpeaker conectado, este módulo no hace nada.

Necesita `python3-usb` (apt) y permiso sobre el USB: ver bicho/README.md.
"""
from __future__ import annotations

import collections
import math
import os
import queue
import shutil
import struct
import subprocess
import threading
import time

VID, PID = 0x2886, 0x001A
# Parámetros del firmware XVF3800 (resid, cmd), los mismos de xvf_host.py de Seeed.
DOA_VALUE = (20, 18)  # 2 x uint16: ángulo 0..359 y 1 si hay voz

FRECUENCIA = 16000  # Hz, mono, 16 bits
TROZO = 0.1  # segundos por trozo de audio
PREVIO = 0.4  # audio que se guarda de antes de que empiece la voz
SILENCIO = 0.9  # silencio que da la frase por terminada
MINIMO = 0.5  # una frase más corta se descarta (golpes, clics)
MAXIMO = 15.0  # una frase más larga se corta

disponible = False  # True si el ReSpeaker respondió
_angulo: int | None = None
_voz = False
_cola: "queue.Queue[dict]" = queue.Queue(maxsize=8)
_partido = False


def estado() -> dict | None:
    """Para los sensores: {"angulo": 0..359, "voz": bool}, o None si no hay ReSpeaker."""
    if not disponible or _angulo is None:
        return None
    return {"angulo": _angulo, "voz": _voz}


def frases() -> list[dict]:
    """Frases terminadas desde la última llamada: {"angulo", "dur", "fmt", "audio": bytes}."""
    out = []
    while True:
        try:
            out.append(_cola.get_nowait())
        except queue.Empty:
            return out


# ── Ángulo: se le pregunta al chip por USB ─────────────────────────────────────


def _hilo_angulo() -> None:
    global disponible, _angulo, _voz
    import usb.core
    import usb.util

    pedir = usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    dev = None
    while True:
        try:
            if dev is None:
                dev = usb.core.find(idVendor=VID, idProduct=PID)
                if dev is None:
                    disponible = False
                    time.sleep(3)
                    continue
            r = dev.ctrl_transfer(pedir, 0, 0x80 | DOA_VALUE[1], DOA_VALUE[0], 5, 500)
            if r[0] == 0:  # 0 = listo; cualquier otro valor: el chip pide reintentar
                _angulo, voz = struct.unpack("<2H", r.tobytes()[1:5])
                _voz = bool(voz)
                disponible = True
            time.sleep(0.05)
        except Exception:  # desconectado o sin permiso: se vuelve a buscar
            dev = None
            disponible = False
            _voz = False
            time.sleep(2)


# ── Frases: se graba con arecord y se corta según la voz ───────────────────────


def _media_angulos(grados: list[int]) -> int | None:
    """Promedio circular: entre 350° y 10° el promedio es 0°, no 180°."""
    if not grados:
        return None
    x = sum(math.cos(math.radians(g)) for g in grados)
    y = sum(math.sin(math.radians(g)) for g in grados)
    return int(round(math.degrees(math.atan2(y, x)))) % 360


def _comprimir(pcm: bytes) -> tuple[str, bytes]:
    """Opus si hay ffmpeg (pesa 10 veces menos por el relé); si no, WAV."""
    if shutil.which("ffmpeg"):
        try:
            r = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(FRECUENCIA), "-ac", "1", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "pipe:1"],
                input=pcm,
                capture_output=True,
                timeout=20,
            )
            if r.returncode == 0 and r.stdout:
                return "ogg", r.stdout
        except (OSError, subprocess.SubprocessError):
            pass
    n = len(pcm)
    cabeza = b"RIFF" + struct.pack("<I", 36 + n) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, FRECUENCIA, FRECUENCIA * 2, 2, 16) + b"data" + struct.pack("<I", n)
    return "wav", cabeza + pcm


def _hilo_frases() -> None:
    bytes_trozo = int(FRECUENCIA * TROZO) * 2
    while True:
        if not disponible:
            time.sleep(2)
            continue
        try:
            rec = subprocess.Popen(
                ["arecord", "-q", "-D", os.environ.get("BICHO_MIC", "plughw:Array"), "-f", "S16_LE", "-r", str(FRECUENCIA), "-c", "1", "-t", "raw"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            time.sleep(10)
            continue
        previo: collections.deque[bytes] = collections.deque(maxlen=int(PREVIO / TROZO))
        frase: list[bytes] = []
        angulos: list[int] = []
        callado = 0.0
        try:
            while True:
                trozo = rec.stdout.read(bytes_trozo) if rec.stdout else b""
                if len(trozo) < bytes_trozo:
                    break  # arecord murió (micrófono desconectado)
                if not frase:
                    if _voz:
                        frase = [*previo, trozo]
                        angulos = [_angulo] if _angulo is not None else []
                        callado = 0.0
                    else:
                        previo.append(trozo)
                    continue
                frase.append(trozo)
                if _voz:
                    callado = 0.0
                    if _angulo is not None:
                        angulos.append(_angulo)
                else:
                    callado += TROZO
                dur = len(frase) * TROZO
                if callado >= SILENCIO or dur >= MAXIMO:
                    hablado = dur - callado - PREVIO
                    if hablado >= MINIMO:
                        fmt, audio = _comprimir(b"".join(frase))
                        try:
                            _cola.put_nowait({"angulo": _media_angulos(angulos), "dur": round(dur - callado, 1), "fmt": fmt, "audio": audio})
                        except queue.Full:
                            pass  # nadie las está recogiendo: se bota la más nueva
                    frase, angulos = [], []
                    previo.clear()
        finally:
            rec.kill()
        time.sleep(2)


def partir() -> None:
    """Lo llama bichod al arrancar. No hace nada en simulación o sin pyusb."""
    global _partido
    if _partido or os.environ.get("BICHO_SIMULAR") == "1":
        return
    try:
        import usb.core  # noqa: F401
    except ImportError:
        return
    _partido = True
    threading.Thread(target=_hilo_angulo, daemon=True, name="oido-angulo").start()
    threading.Thread(target=_hilo_frases, daemon=True, name="oido-frases").start()
