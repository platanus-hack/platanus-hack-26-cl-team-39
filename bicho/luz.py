"""
Luz del bicho: un LED en el GPIO 17 (pin físico 11), con resistencia de 220-330 Ω a GND (pin 9).

comandos.py la prende y apaga; sensores.py reporta su estado.
Sin gpiozero o sin GPIO (por ejemplo en un computador) la luz es simulada: solo guarda el estado.
"""
from __future__ import annotations

import os

PIN = int(os.environ.get("BICHO_LUZ_PIN", "17"))

_led = None
_sim = False  # estado cuando no hay GPIO
real = False  # True si se está manejando un pin de verdad

if os.environ.get("BICHO_SIMULAR") != "1":
    try:
        from gpiozero import LED

        _led = LED(PIN)
        real = True
    except Exception:  # sin gpiozero, sin GPIO o pin ocupado: queda simulada
        _led = None


def prender() -> None:
    global _sim
    if _led:
        _led.on()
    _sim = True


def apagar() -> None:
    global _sim
    if _led:
        _led.off()
    _sim = False


def parpadear(n: int = 5, periodo: float = 0.5) -> None:
    """Parpadea n veces sin bloquear y termina apagada."""
    global _sim
    if _led:
        _led.blink(on_time=periodo / 2, off_time=periodo / 2, n=n, background=True)
    _sim = False


def prendida() -> bool:
    return bool(_led.value) if _led else _sim
