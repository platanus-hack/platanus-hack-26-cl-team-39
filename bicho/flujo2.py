"""
Segundo sensor de flujo óptico ADNS-3080, en el otro chip select del SPI0.

"Pin 26" se toma como el pin FÍSICO 26 del conector, que es el GPIO 7 = SPI0 CE1 y
corresponde a /dev/spidev0.1 (el primer sensor usa el pin físico 24 = GPIO 8 = CE0 =
spidev0.0). El kernel ya maneja ese chip select: aquí no se cambia ninguna configuración
del sistema ni se maneja ningún GPIO a mano. Ojo: el GPIO 26 (pin físico 37) NO es un
chip select del SPI y este módulo no lo toca.

Mismo protocolo que flujo.py (se reutiliza su lectura de registros): modo 3, 500 kHz,
75 µs entre dirección y dato, primera lectura descartada y registro 0x00 == 0x17
obligatorio antes de leer 0x02 (Motion), 0x03 (dx), 0x04 (dy) y 0x05 (SQUAL).

Nada se abre al importar. Con BICHO_SIMULAR=1 no se toca el hardware.
La lectura continua corre en un hilo daemon (prender/apagar).
"""
from __future__ import annotations

import fcntl
import os
import shutil
import struct
import subprocess
import threading

import flujo  # reutiliza _reg, _s8, _texto, _simulada y las constantes del protocolo

SIMULAR = flujo.SIMULAR

DISPOSITIVO = "/dev/spidev0.1"
PIN_FISICO = 26
GPIO_CS = 7  # SPI0 CE1
DONDE_CS = f"pin físico {PIN_FISICO} = GPIO {GPIO_CS} = CE1"

_spi = threading.Lock()  # protege _fd y cada lectura completa de este sensor
_fd: int | None = None
_hilo: threading.Thread | None = None
_parar = threading.Event()
_error: str | None = None
_ultimo: dict = {}
_acum = [0, 0]


def _cerrar() -> None:  # llamar con _spi tomado
    global _fd
    if _fd is not None:
        try:
            os.close(_fd)
        except OSError:
            pass
        _fd = None


def _abrir() -> int:  # llamar con _spi tomado
    """Abre spidev0.1, descarta la primera lectura y exige ID 0x17."""
    global _fd
    if _fd is not None:
        return _fd
    try:
        fd = os.open(DISPOSITIVO, os.O_RDWR)
    except FileNotFoundError:
        raise RuntimeError(
            f"no existe {DISPOSITIVO}: el sistema no tiene habilitado el chip select CE1 "
            f"({DONDE_CS}) y no voy a cambiar la configuración del SPI"
        ) from None
    try:
        fcntl.ioctl(fd, flujo._WR_MODE, struct.pack("B", flujo.MODO))
        fcntl.ioctl(fd, flujo._WR_BITS, struct.pack("B", 8))
        fcntl.ioctl(fd, flujo._WR_HZ, struct.pack("I", flujo.HZ))
        flujo._reg(fd, flujo.REG_ID)  # la primera lectura se descarta
        pid = flujo._reg(fd, flujo.REG_ID)
    except Exception:
        os.close(fd)
        raise
    if pid != flujo.ID_ESPERADO:
        os.close(fd)
        raise RuntimeError(
            f"el registro 0x00 dio 0x{pid:02X} y debía dar 0x{flujo.ID_ESPERADO:02X}: "
            f"el segundo ADNS-3080 no responde en {DISPOSITIVO} ({DONDE_CS}). "
            f"Si su NCS está en el GPIO 26 (pin físico 37), ese no es un chip select del SPI: "
            f"pásalo al pin físico 26. No activé nada"
        )
    _fd = fd
    return fd


def _leer_una() -> dict:
    if SIMULAR:
        return flujo._simulada()
    with _spi:
        fd = _abrir()
        try:
            m = flujo._reg(fd, flujo.REG_MOTION)
            dx = flujo._s8(flujo._reg(fd, flujo.REG_DX))
            dy = flujo._s8(flujo._reg(fd, flujo.REG_DY))
            q = flujo._reg(fd, flujo.REG_SQUAL)
        except OSError:
            _cerrar()
            raise
    return {"mov": bool(m & 0x80), "desborde": bool(m & 0x10), "dx": dx, "dy": dy, "squal": q}


def _bucle() -> None:
    global _error, _ultimo
    while not _parar.is_set():
        try:
            r = _leer_una()
        except Exception as e:
            _error = f"{type(e).__name__}: {e}"
            return
        _acum[0] += r["dx"]
        _acum[1] += r["dy"]
        _ultimo = r
        _parar.wait(flujo.PERIODO)


def activa() -> bool:
    h = _hilo
    return h is not None and h.is_alive()


def _donde() -> str:
    if SIMULAR:
        return "simulado"
    return f"ID 0x{flujo.ID_ESPERADO:02X} ok en {DISPOSITIVO}, {DONDE_CS}"


def prender() -> str:
    """Confirma el ID y parte la lectura continua en un hilo daemon."""
    global _hilo, _error, _ultimo
    if activa():
        return "flujo2: ya estaba leyendo"
    if not SIMULAR:
        with _spi:
            _abrir()  # lanza si el ID no es 0x17
    _error = None
    _ultimo = {}
    _acum[0] = _acum[1] = 0
    _parar.clear()
    _hilo = threading.Thread(target=_bucle, name="flujo2", daemon=True)
    _hilo.start()
    return f"flujo2: leyendo el segundo ADNS-3080 ({_donde()}); apágalo con on:false"


def apagar() -> str:
    global _hilo
    h = _hilo
    _parar.set()
    if h is not None and h.is_alive():
        h.join(0.5)
    _hilo = None
    with _spi:
        _cerrar()
    return "flujo2: apagado"


def reiniciar() -> str:
    _acum[0] = _acum[1] = 0
    return "flujo2: acumulado en cero"


def estado() -> str:
    """Lectura actual. Si el hilo no corre, hace una lectura suelta (confirma el ID primero)."""
    if activa():
        r = _ultimo
        if not r:
            return "flujo2: partiendo, todavía sin lecturas"
        return f"flujo2 ({_donde()}, leyendo): {flujo._texto(r)}, acumulado x={_acum[0]:+d} y={_acum[1]:+d}"
    previo = f" (la lectura continua se cortó: {_error})" if _error else ""
    r = _leer_una()
    return f"flujo2 ({_donde()}): {flujo._texto(r)}{previo}"


def pines() -> str:
    """Solo lectura: muestra cómo están los chip select (GPIO 8 y 7) y el GPIO 26. No cambia nada."""
    base = (
        f"flujo2 usa {DISPOSITIVO} ({DONDE_CS}); el primer sensor usa {flujo.DISPOSITIVO} "
        f"(pin físico 24 = GPIO 8 = CE0). {DISPOSITIVO} {'existe' if os.path.exists(DISPOSITIVO) else 'NO existe'}"
    )
    if SIMULAR or not shutil.which("pinctrl"):
        return base
    try:
        r = subprocess.run(["pinctrl", "get", "7,8,26"], capture_output=True, text=True, timeout=2)
        return base + " | " + " | ".join(x.strip() for x in r.stdout.splitlines() if x.strip())
    except Exception as e:
        return f"{base} (pinctrl falló: {type(e).__name__})"


def datos() -> dict | None:
    """Para sensores.leer(): no toca el SPI, solo copia lo último del hilo."""
    r = _ultimo
    if not r or not activa():
        return None
    return {"mov": r["mov"], "dx": r["dx"], "dy": r["dy"], "x": _acum[0], "y": _acum[1], "squal": r["squal"]}
