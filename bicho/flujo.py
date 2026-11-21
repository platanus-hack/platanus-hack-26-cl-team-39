"""
Sensor de flujo óptico ADNS-3080 por SPI (/dev/spidev0.0, modo 3, 500 kHz).

Habla con spidev directo por ioctl (solo librería estándar, sin el módulo spidev).
Cada lectura de registro es un solo mensaje SPI con CS abajo: se manda la dirección,
se esperan 75 µs y se lee el dato. Al abrir se descarta la primera lectura y se
confirma que el registro 0x00 (Product_ID) dé 0x17; si no, no se lee nada más.

  0x02 Motion (bit 7 = hubo movimiento, bit 4 = desborde)
  0x03 Delta_X, 0x04 Delta_Y (con signo, se borran al leerlos)
  0x05 SQUAL (calidad de superficie, 0..169)

Nada se abre al importar. Con BICHO_SIMULAR=1 no se toca el hardware: valores inventados.
La lectura continua corre en un hilo daemon (prender/apagar).
"""
from __future__ import annotations

import ctypes
import fcntl
import math
import os
import struct
import threading
import time

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

DISPOSITIVO = "/dev/spidev0.0"
MODO = 3
HZ = 500_000
ESPERA_US = 75
ID_ESPERADO = 0x17
PERIODO = 0.05  # s entre lecturas del hilo

REG_ID, REG_MOTION, REG_DX, REG_DY, REG_SQUAL = 0x00, 0x02, 0x03, 0x04, 0x05

# ioctl de spidev (linux/spi/spidev.h)
_WR_MODE = 0x40016B01
_WR_BITS = 0x40016B03
_WR_HZ = 0x40046B04
_MSG_2 = 0x40406B00  # SPI_IOC_MESSAGE(2): dos struct spi_ioc_transfer de 32 bytes
_XFER = "=QQIIHBBBBBB"  # tx_buf, rx_buf, len, speed_hz, delay_usecs, bits, cs_change, tx_nbits, rx_nbits, word_delay, pad

_spi = threading.Lock()  # protege _fd y cada transacción
_fd: int | None = None
_hilo: threading.Thread | None = None
_parar = threading.Event()
_error: str | None = None
_ultimo: dict = {}  # última lectura del hilo
_acum = [0, 0]  # x, y acumulados


def _reg(fd: int, addr: int) -> int:
    tx = ctypes.create_string_buffer(bytes([addr & 0x7F]), 1)  # bit 7 en 0 = leer
    rx = ctypes.create_string_buffer(1)
    msg = struct.pack(_XFER, ctypes.addressof(tx), 0, 1, HZ, ESPERA_US, 8, 0, 0, 0, 0, 0)
    msg += struct.pack(_XFER, 0, ctypes.addressof(rx), 1, HZ, 0, 8, 0, 0, 0, 0, 0)
    fcntl.ioctl(fd, _MSG_2, msg)
    return rx.raw[0]


def _cerrar() -> None:  # llamar con _spi tomado
    global _fd
    if _fd is not None:
        try:
            os.close(_fd)
        except OSError:
            pass
        _fd = None


def _abrir() -> int:  # llamar con _spi tomado
    """Abre y configura el SPI, descarta la primera lectura y exige ID 0x17."""
    global _fd
    if _fd is not None:
        return _fd
    fd = os.open(DISPOSITIVO, os.O_RDWR)
    try:
        fcntl.ioctl(fd, _WR_MODE, struct.pack("B", MODO))
        fcntl.ioctl(fd, _WR_BITS, struct.pack("B", 8))
        fcntl.ioctl(fd, _WR_HZ, struct.pack("I", HZ))
        _reg(fd, REG_ID)  # la primera lectura se descarta
        pid = _reg(fd, REG_ID)
    except Exception:
        os.close(fd)
        raise
    if pid != ID_ESPERADO:
        os.close(fd)
        raise RuntimeError(
            f"el registro 0x00 dio 0x{pid:02X} y debía dar 0x{ID_ESPERADO:02X}: "
            f"el ADNS-3080 no responde en {DISPOSITIVO} (revisa cableado y alimentación)"
        )
    _fd = fd
    return fd


def _s8(v: int) -> int:
    return v - 256 if v > 127 else v


def _simulada() -> dict:
    s = time.monotonic()
    return {"mov": True, "desborde": False, "dx": round(math.sin(s) * 5), "dy": round(math.cos(s * 0.7) * 5), "squal": 80}


def _leer_una() -> dict:
    """Una lectura completa: Motion, Delta_X, Delta_Y y SQUAL (en ese orden)."""
    if SIMULAR:
        return _simulada()
    with _spi:
        fd = _abrir()
        try:
            m = _reg(fd, REG_MOTION)
            dx = _s8(_reg(fd, REG_DX))
            dy = _s8(_reg(fd, REG_DY))
            q = _reg(fd, REG_SQUAL)
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
        _parar.wait(PERIODO)


def activa() -> bool:
    h = _hilo
    return h is not None and h.is_alive()


def _texto(r: dict) -> str:
    return (
        f"movimiento {'sí' if r['mov'] else 'no'}, dx={r['dx']:+d}, dy={r['dy']:+d}, "
        f"calidad {r['squal']}/169" + (" (¡desborde!)" if r["desborde"] else "")
    )


def _donde() -> str:
    return "simulado" if SIMULAR else f"ID 0x{ID_ESPERADO:02X} ok en {DISPOSITIVO}"


def prender() -> str:
    """Confirma el ID y parte la lectura continua (20 por segundo) en un hilo daemon."""
    global _hilo, _error, _ultimo
    if activa():
        return "flujo: ya estaba leyendo"
    if not SIMULAR:
        with _spi:
            _abrir()  # lanza si el ID no es 0x17
    _error = None
    _ultimo = {}
    _acum[0] = _acum[1] = 0
    _parar.clear()
    _hilo = threading.Thread(target=_bucle, name="flujo", daemon=True)
    _hilo.start()
    return f"flujo: leyendo el ADNS-3080 ({_donde()}); apágalo con on:false"


def apagar() -> str:
    global _hilo
    h = _hilo
    _parar.set()
    if h is not None and h.is_alive():
        h.join(0.5)
    _hilo = None
    with _spi:
        _cerrar()
    return "flujo: apagado"


def reiniciar() -> str:
    _acum[0] = _acum[1] = 0
    return "flujo: acumulado en cero"


def estado() -> str:
    """Texto con la lectura actual. Si el hilo no corre, hace una lectura suelta (confirma el ID primero)."""
    if activa():
        r = _ultimo
        if not r:
            return "flujo: partiendo, todavía sin lecturas"
        return f"flujo ({_donde()}, leyendo): {_texto(r)}, acumulado x={_acum[0]:+d} y={_acum[1]:+d}"
    previo = f" (la lectura continua se cortó: {_error})" if _error else ""
    r = _leer_una()
    return f"flujo ({_donde()}): {_texto(r)}{previo}"


def datos() -> dict | None:
    """Para sensores.leer(): no toca el SPI, solo copia lo último del hilo."""
    r = _ultimo
    if not r or not activa():
        return None
    return {"mov": r["mov"], "dx": r["dx"], "dy": r["dy"], "x": _acum[0], "y": _acum[1], "squal": r["squal"]}
