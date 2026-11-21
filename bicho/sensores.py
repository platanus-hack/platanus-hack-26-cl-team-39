"""
Sensores del bicho. Edita leer(): devuelve un dict y la web grafica sola todo lo numérico.

Se puede anidar ({"imu": {"pitch": 3.1}}) y usar listas ({"servo": [90, 45]}).
leer() se llama 20 veces por segundo mientras haya alguien mirando: que sea rápida.
Para probar sin hardware: BICHO_SIMULAR=1 python3 bichod.py
"""
from __future__ import annotations

import math
import os
import random
import time
from pathlib import Path

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"
_t0 = time.time()


def _cpu_temp() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


def _wifi_dbm() -> float | None:
    try:
        for line in Path("/proc/net/wireless").read_text().splitlines()[2:]:
            parts = line.split()
            if parts and parts[0].startswith("wlan"):
                return float(parts[3].rstrip("."))
    except (OSError, ValueError, IndexError):
        pass
    return None


# ── Ejemplos para cuando conecten el hardware (descomentar y ajustar) ─────────
#
# Botón en el GPIO 17 (gpiozero viene en Raspberry Pi OS):
#   from gpiozero import Button
#   boton = Button(17)
#   ...en leer():  d["boton"] = boton.is_pressed
#
# IMU MPU-6050 por I2C (activar I2C en raspi-config; pip install smbus2):
#   from smbus2 import SMBus
#   bus = SMBus(1); bus.write_byte_data(0x68, 0x6B, 0)   # despertar
#   def _word(reg):
#       v = (bus.read_byte_data(0x68, reg) << 8) | bus.read_byte_data(0x68, reg + 1)
#       return v - 65536 if v > 32767 else v
#   ...en leer():  d["imu"] = {"ax": _word(0x3B) / 16384, "ay": _word(0x3D) / 16384, "az": _word(0x3F) / 16384}
# ──────────────────────────────────────────────────────────────────────────────


def leer() -> dict:
    d: dict = {}
    t = _cpu_temp()
    if t is not None:
        d["temp_cpu"] = round(t, 1)
    d["carga"] = round(os.getloadavg()[0], 2)
    w = _wifi_dbm()
    if w is not None:
        d["wifi_dbm"] = w

    if SIMULAR:
        s = time.time() - _t0
        d["mic"] = round(abs(math.sin(s * 3.1)) * 0.6 + random.random() * 0.3, 3)
        d["imu"] = {"pitch": round(math.sin(s * 0.7) * 25, 2), "roll": round(math.cos(s * 0.5) * 12, 2)}
        d["dist_cm"] = round(60 + math.sin(s * 0.3) * 40, 1)
        d["servo"] = [round(90 + math.sin(s) * 60), round(90 + math.cos(s * 1.3) * 45)]
        d["boton"] = math.sin(s * 0.9) > 0.92
    return d
