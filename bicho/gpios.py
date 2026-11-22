"""
Salidas digitales del bicho en los GPIO 23 y 24 (pines físicos 16 y 18).

    gpios.poner(True)        prende los dos      gpios.poner(False)       apaga los dos
    gpios.poner(True, 23)    solo uno            gpios.estado()           cómo están
    gpios.prendido(23)       booleano (para sensores.py; no toca nada si el pin no se ha usado)

Usa gpiozero igual que luces.py. Los GPIO 27 y 22 NO se tocan aquí: son la luz verde y la roja
(luces.py, comandos verde / rojo / luces). El 17 es de luz.py.

Los pines se toman recién con la primera orden de prender o apagar (no al importar): hasta entonces
quedan como estaban (entradas). Sin gpiozero o con BICHO_SIMULAR=1 son simulados: solo guardan el estado.
Nada bloquea ni deja hilos corriendo: prender y apagar son instantáneos.
"""
from __future__ import annotations

import os
import threading

PINES = (23, 24)
FISICO = {23: 16, 24: 18}
SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

AYUDA = (
    '{"cmd":"gpio23_24"}  cómo están las salidas de los GPIO 23 y 24 (pines físicos 16 y 18)'
    '  ·  "on":true prende las dos y las deja prendidas  ·  "on":false las apaga'
    '  ·  "pin":23 (o 24) para una sola  ·  los GPIO 27 y 22 son las luces verde y roja (comandos verde, rojo, luces)'
)

_lock = threading.Lock()
_salidas: dict = {}  # pin -> gpiozero.DigitalOutputDevice (solo si hay GPIO de verdad)
_sim: dict = {p: False for p in PINES}  # estado guardado (lo único que hay en simulación)
_errores: dict = {}  # pin -> por qué no se pudo tomar


def _tomar(pin: int):
    """Devuelve el dispositivo gpiozero del pin (lo crea la primera vez) o None si queda simulado."""
    if SIMULAR:
        return None
    d = _salidas.get(pin)
    if d is not None:
        return d
    try:
        from gpiozero import DigitalOutputDevice

        d = DigitalOutputDevice(pin, initial_value=False)
        _salidas[pin] = d
        _errores.pop(pin, None)
        return d
    except Exception as e:  # pin ocupado, sin gpiozero o sin GPIO
        _errores[pin] = f"{type(e).__name__}: {e}"[:160]
        return None


def _elegir(pin) -> tuple | None:
    if pin is None:
        return PINES
    try:
        p = int(pin)
    except (TypeError, ValueError):
        return None
    return (p,) if p in PINES else None


def real(pin: int) -> bool:
    return pin in _salidas


def prendido(pin: int) -> bool:
    """Rápido y sin efectos: si el pin no se ha tomado todavía, dice False."""
    d = _salidas.get(pin)
    if d is not None:
        try:
            return bool(d.value)
        except Exception:
            return False
    return bool(_sim.get(pin, False))


def _uno(pin: int) -> str:
    if real(pin):
        donde = f"pin físico {FISICO[pin]}"
    elif SIMULAR:
        donde = "simulado"
    elif pin in _errores:
        donde = "no pude tomarlo: " + _errores[pin]
    else:
        return f"GPIO {pin} sin usar todavía (pin físico {FISICO[pin]})"
    return f"GPIO {pin} {'prendido' if prendido(pin) else 'apagado'} ({donde})"


def poner(on: bool, pin=None) -> str:
    pines = _elegir(pin)
    if pines is None:
        return 'gpio23_24: "pin" tiene que ser 23 o 24 (el 27 y el 22 se manejan con verde y rojo)'
    with _lock:
        for p in pines:
            d = _tomar(p)
            if d is not None:
                if on:
                    d.on()
                else:
                    d.off()
                _sim[p] = bool(on)
            elif SIMULAR:
                _sim[p] = bool(on)
            else:
                _sim[p] = False  # no se pudo tomar: no digo que está prendido
    return ", ".join(_uno(p) for p in pines)


def estado(pin=None) -> str:
    pines = _elegir(pin)
    if pines is None:
        return 'gpio23_24: "pin" tiene que ser 23 o 24'
    return ", ".join(_uno(p) for p in pines)


def manejar(c: dict) -> str:
    pin = c.get("pin")
    if "on" in c:
        return poner(bool(c.get("on")), pin)
    return estado(pin)
