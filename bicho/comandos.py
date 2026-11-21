"""
Comandos propios del bicho: servos, LEDs, sonido, etc.

La web (consola) y el harness mandan líneas JSON como {"cmd":"servo","i":0,"deg":90}.
manejar() recibe ese dict y devuelve un texto para la consola, o None si no conoce el comando.
Los comandos "info", "rate" y "reboot" ya los resuelve bichod.py.
"""
from __future__ import annotations


def manejar(c: dict) -> str | None:
    cmd = c.get("cmd")

    if cmd == "hola":
        return "hola desde el bicho"

    # Ejemplo con un servo en el GPIO 18 (gpiozero viene en Raspberry Pi OS):
    #   from gpiozero import AngularServo
    #   servo = AngularServo(18, min_angle=0, max_angle=180)   ← crear una vez, fuera de la función
    # if cmd == "servo":
    #     servo.angle = float(c.get("deg", 90))
    #     return f"servo en {servo.angle}°"

    return None
