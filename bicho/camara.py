"""
Cámara del bicho: cámara CSI (ov5647) en el puerto de cámara de la Pi.

    camara.prender()   empieza a mandar una imagen por segundo a la web (solo si hay público)
    camara.apagar()    deja de mandar y suelta la cámara
    camara.foto()      saca una sola foto (sirve con la cámara prendida o apagada)
    camara.estado()    texto con lo que está pasando

    camara.analizar(nombre, fn)       otro módulo (p. ej. gesto.py) pide recibir cada cuadro: fn(jpeg: bytes)
    camara.dejar_de_analizar(nombre)  deja de recibirlos
    camara.analizando(nombre)         True si sigue registrado

Todo lo lento (abrir la cámara, capturar) corre en un único hilo daemon que parte recién cuando
llega un comando; al importar no se abre nada. Primero se intenta con picamera2 (la cámara queda
abierta, cada cuadro sale barato) y si no resulta, con rpicam-still (un proceso por foto).
La última imagen queda guardada en RUTA. Con BICHO_SIMULAR=1 no se toca hardware.

Mientras haya un analizador registrado la cámara captura aunque nadie mire la web (2 cuadros por
segundo), pero a la web solo se manda una imagen por segundo, y solo si la cámara está prendida
y hay público.
"""
from __future__ import annotations

import base64
import io
import os
import subprocess
import threading
import time

import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"
RUTA = os.environ.get("BICHO_CAMARA_RUTA", "/tmp/bicho_camara.jpg")
ANCHO, ALTO = 640, 480
PERIODO = 1.0  # segundos entre imágenes para la web
PERIODO_ANALISIS = 0.5  # segundos entre cuadros cuando alguien analiza
MAX_BYTES = 300_000

_lock = threading.Lock()
_despertar = threading.Event()
_una = threading.Event()  # hay una foto suelta pedida
_hilo: threading.Thread | None = None
_continuo = False
_analizadores: dict = {}  # nombre -> fn(jpeg)
_backend: str | None = None
_sin_picamera2 = False
_calidad = 80
_error: str | None = None
_ultimo_t = 0.0  # time.time() de la última imagen
_ultimo_emit = 0.0  # time.monotonic() de la última imagen mandada a la web
_ultimo_bytes = 0
_cuadros = 0


def _log(lvl: str, msg: str) -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "camara: " + msg})


# ── Formas de capturar ───────────────────────────────────────────────────────

class _Picamera2:
    nombre = "picamera2"

    def __init__(self) -> None:
        from picamera2 import Picamera2  # import lento: solo dentro del hilo

        self.c = Picamera2()
        try:
            cfg = self.c.create_preview_configuration(
                main={"size": (ANCHO, ALTO), "format": "RGB888"},
                buffer_count=2,
                controls={"FrameRate": 5.0},  # pocos cuadros: menos CPU
            )
            self.c.configure(cfg)
            self.c.start()
            time.sleep(1.5)  # que se acomoden exposición y balance de blancos
        except Exception:
            self.cerrar()
            raise

    def capturar(self) -> bytes:
        self.c.options["quality"] = _calidad
        buf = io.BytesIO()
        self.c.capture_file(buf, format="jpeg")
        return buf.getvalue()

    def cerrar(self) -> None:
        for f in ("stop", "close"):
            try:
                getattr(self.c, f)()
            except Exception:
                pass


class _RpicamStill:
    nombre = "rpicam-still"

    def capturar(self) -> bytes:
        tmp = RUTA + ".rpicam.jpg"
        r = subprocess.run(
            ["rpicam-still", "-n", "-t", "800", "--width", str(ANCHO), "--height", str(ALTO),
             "-q", str(_calidad), "-o", tmp],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20,
        )
        if r.returncode != 0:
            lineas = r.stderr.decode("utf-8", "replace").strip().splitlines()
            raise RuntimeError("rpicam-still falló: " + (lineas[-1] if lineas else f"código {r.returncode}"))
        try:
            with open(tmp, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def cerrar(self) -> None:
        pass


def _abrir():
    global _backend, _sin_picamera2
    if not _sin_picamera2:
        try:
            cam = _Picamera2()
            _backend = cam.nombre
            return cam
        except (ImportError, TypeError, AttributeError) as e:
            # no está o su API no es la que espero: no insistir más
            _sin_picamera2 = True
            _log("warn", f"picamera2 no sirve aquí ({type(e).__name__}: {e}); uso rpicam-still")
        except Exception as e:
            _log("warn", f"picamera2 no pudo abrir la cámara ({type(e).__name__}: {e}); pruebo rpicam-still")
    cam = _RpicamStill()
    _backend = cam.nombre
    return cam


def _cerrar(cam) -> None:
    if cam is not None:
        try:
            cam.cerrar()
        except Exception:
            pass
    return None


# ── Hilo de captura ──────────────────────────────────────────────────────────

def _esperar(seg: float) -> None:
    _despertar.wait(seg)
    _despertar.clear()


def _publicar(jpg: bytes, suelta: bool) -> None:
    global _ultimo_t, _ultimo_emit, _ultimo_bytes, _cuadros, _calidad
    if len(jpg) > MAX_BYTES:
        _calidad = max(30, _calidad - 15)
        _log("warn", f"imagen de {len(jpg) // 1024} KB, muy pesada: bajo la calidad a {_calidad} y no la mando")
        return
    _ultimo_t = time.time()
    _ultimo_bytes = len(jpg)
    _cuadros += 1
    ahora = time.monotonic()
    toca = _continuo and salida.hay_publico() and ahora - _ultimo_emit >= PERIODO - 0.15
    if not (suelta or toca):
        return  # cuadro solo para analizar: ni disco ni red
    try:
        tmp = RUTA + ".tmp"
        with open(tmp, "wb") as f:
            f.write(jpg)
        os.replace(tmp, RUTA)
    except OSError as e:
        _log("warn", f"no pude guardar {RUTA}: {e}")
    _ultimo_emit = ahora
    salida.emitir({"t": "imagen", "nombre": "camara", "fmt": "jpeg",
                   "b64": base64.b64encode(jpg).decode("ascii")})
    if suelta:
        _log("info", f"foto guardada en {RUTA} ({ANCHO}x{ALTO}, {len(jpg) / 1024:.0f} KB, {_backend})")


def _bucle() -> None:
    global _hilo, _continuo, _error
    cam = None
    fallos = 0
    try:
        while True:
            quiere = _una.is_set() or (_continuo and salida.hay_publico()) or bool(_analizadores)
            if not quiere:
                cam = _cerrar(cam)  # nadie mira: suelto la cámara
                with _lock:
                    if not _continuo and not _una.is_set() and not _analizadores:
                        _hilo = None
                        return
                _esperar(0.5)
                continue
            t0 = time.monotonic()
            try:
                if cam is None:
                    cam = _abrir()
                jpg = cam.capturar()
                if not jpg.startswith(b"\xff\xd8"):
                    raise RuntimeError("la cámara no entregó un JPEG")
            except Exception as e:
                cam = _cerrar(cam)
                fallos += 1
                _error = f"{type(e).__name__}: {e}"[:200]
                _una.clear()
                _log("error", f"falló la captura ({_error})")
                if fallos >= 3 and (_continuo or _analizadores):
                    _continuo = False
                    _analizadores.clear()
                    _log("error", "tres fallas seguidas, apago la cámara (y lo que la estaba usando)")
                elif _continuo or _analizadores:
                    _esperar(3.0)
                continue
            fallos = 0
            _error = None
            suelta = _una.is_set()
            _una.clear()
            _publicar(jpg, suelta)
            for fn in list(_analizadores.values()):
                try:
                    fn(jpg)
                except Exception:
                    pass  # cada analizador reporta sus propios errores
            if _analizadores:
                periodo = 2.0 if _backend == "rpicam-still" else PERIODO_ANALISIS
            else:
                periodo = PERIODO
            _esperar(max(0.05, periodo - (time.monotonic() - t0)))
    except Exception as e:  # no debería pasar; que no quede un hilo fantasma
        _error = f"{type(e).__name__}: {e}"[:200]
    finally:
        _cerrar(cam)
        with _lock:
            if _hilo is threading.current_thread():
                _hilo = None
                _continuo = False
                _analizadores.clear()


def _asegurar_hilo() -> None:
    """Llamar con _lock tomado."""
    global _hilo
    if _hilo is None or not _hilo.is_alive():
        _hilo = threading.Thread(target=_bucle, name="camara", daemon=True)
        _hilo.start()
    _despertar.set()


# ── Para otros módulos que quieren mirar los cuadros (gesto.py) ──────────────

def analizar(nombre: str, fn) -> None:
    """fn(jpeg: bytes) se llama en el hilo de la cámara con cada cuadro: tiene que ser rápida."""
    global _error
    if SIMULAR:
        return
    with _lock:
        _analizadores[nombre] = fn
        _error = None
        _asegurar_hilo()


def dejar_de_analizar(nombre: str) -> None:
    _analizadores.pop(nombre, None)
    _despertar.set()


def analizando(nombre: str) -> bool:
    return nombre in _analizadores


def ultimo_error() -> str | None:
    return _error


# ── Lo que usa comandos.py ───────────────────────────────────────────────────

def activa() -> bool:
    return _continuo


def prender() -> str:
    global _continuo, _error
    if SIMULAR:
        _continuo = True
        return "cámara prendida (simulada, sin hardware)"
    with _lock:
        ya = _continuo
        _continuo = True
        _error = None
        _asegurar_hilo()
    extra = "" if salida.hay_publico() else " (parte cuando alguien mire la web)"
    if ya:
        return "la cámara ya estaba prendida" + extra
    return f"cámara prendida: una imagen de {ANCHO}x{ALTO} por segundo en Vista{extra}"


def apagar() -> str:
    global _continuo
    _continuo = False
    _despertar.set()
    if _analizadores:
        return "cámara apagada para la web (sigue mirando para: " + ", ".join(_analizadores) + ")"
    return "cámara apagada"


def foto() -> str:
    if SIMULAR:
        return "foto simulada (sin hardware)"
    if _continuo and salida.hay_publico() and time.time() - _ultimo_t < 3:
        return f"foto en {RUTA} ({ANCHO}x{ALTO}, {_ultimo_bytes / 1024:.0f} KB, {_backend}); ya se ve en Vista"
    with _lock:
        _una.set()
        _asegurar_hilo()
    return f"sacando foto… en unos segundos aparece en Vista y queda en {RUTA}"


def estado() -> str:
    p = ["cámara " + ("prendida" if _continuo else "apagada")]
    if SIMULAR:
        p.append("simulada")
    if _backend:
        p.append("vía " + _backend)
    if _analizadores:
        p.append("analizando para: " + ", ".join(_analizadores))
    if _ultimo_t:
        p.append(f"última imagen hace {time.time() - _ultimo_t:.0f} s, {_ultimo_bytes / 1024:.0f} KB, en {RUTA}")
        p.append(f"{_cuadros} imágenes en total")
    elif not SIMULAR:
        p.append("todavía sin imágenes")
    if _continuo and not SIMULAR and not salida.hay_publico():
        p.append("en pausa para la web porque nadie mira")
    if _error:
        p.append("último error: " + _error)
    return " · ".join(p)
