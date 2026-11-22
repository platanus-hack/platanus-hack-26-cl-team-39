"""
Luces de colores del bicho, para responder sí o no.

  verde: GPIO 27 (pin físico 13)   -> "sí"
  roja:  GPIO 22 (pin físico 15)   -> "no"

Cada LED va con su resistencia de 220-330 Ω entre el pin y GND (por ejemplo el pin físico 14 o el 9).
La luz original del GPIO 17 sigue en luz.py y no se toca.

Sin gpiozero o sin GPIO (BICHO_SIMULAR=1, o un computador) las luces son simuladas: solo guardan el estado.
Nada de esto bloquea: el parpadeo y el apagado solo los hace gpiozero en su propio hilo.
"""
from __future__ import annotations

import os
import time

PINES = {
    "verde": int(os.environ.get("BICHO_VERDE_PIN", "27")),
    "rojo": int(os.environ.get("BICHO_ROJO_PIN", "22")),
}

_leds: dict = {}  # color -> gpiozero.LED (solo si hay GPIO de verdad)
_sim: dict = {c: 0.0 for c in PINES}  # color -> hasta cuándo está "prendida" (time.monotonic)
_INF = float("inf")

if os.environ.get("BICHO_SIMULAR") != "1":
    try:
        from gpiozero import LED

        for _c, _p in PINES.items():
            try:
                _leds[_c] = LED(_p)
            except Exception:  # pin ocupado o sin GPIO: ese color queda simulado
                pass
    except Exception:  # sin gpiozero
        pass


# Los GPIO 27 y 22 van además al STBY de dos drivers de motor (TB6612). Mientras los motores se mueven,
# motores.py los reserva: quedan en alto y ningún comando de luces (ni el parpadeo del gesto) los cambia.
_reservadas = False


def reservar(on: bool) -> None:
    """La usa motores.py: en alto y bloqueadas mientras se mueve; al soltar quedan en bajo."""
    global _reservadas
    _reservadas = False
    for c in PINES:
        (prender if on else apagar)(c)
    _reservadas = bool(on)


def real(color: str) -> bool:
    return color in _leds


def donde(color: str) -> str:
    return f"GPIO {PINES[color]}" if real(color) else "simulada"


def prender(color: str) -> None:
    if _reservadas:
        return
    led = _leds.get(color)
    if led:
        led.on()
    _sim[color] = _INF


def apagar(color: str) -> None:
    if _reservadas:
        return
    led = _leds.get(color)
    if led:
        led.off()
    _sim[color] = 0.0


def apagar_todas() -> None:
    for c in PINES:
        apagar(c)


def parpadear(color: str, n: int = 5, periodo: float = 0.5) -> None:
    """Parpadea n veces sin bloquear y termina apagada."""
    if _reservadas:
        return
    led = _leds.get(color)
    if led:
        led.blink(on_time=periodo / 2, off_time=periodo / 2, n=n, background=True)
    _sim[color] = time.monotonic() + n * periodo


def destello(color: str, segundos: float = 2.0) -> None:
    """Prende la luz un rato y se apaga sola, sin bloquear."""
    if _reservadas:
        return
    led = _leds.get(color)
    if led:
        led.blink(on_time=segundos, off_time=0.05, n=1, background=True)
    _sim[color] = time.monotonic() + segundos


def responder(si: bool, segundos: float = 2.0) -> str:
    """Sí = verde, no = roja. Apaga la otra y deja esta prendida unos segundos."""
    color, otro = ("verde", "rojo") if si else ("rojo", "verde")
    apagar(otro)
    destello(color, segundos)
    return color


def prendida(color: str) -> bool:
    led = _leds.get(color)
    if led:
        return bool(led.value)
    return time.monotonic() < _sim[color]
