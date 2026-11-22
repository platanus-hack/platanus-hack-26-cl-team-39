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

import camara
import descubrir
import escucha
import flujo
import flujo2
import gesto
import gpios
import luces
import luz
import motores
import servos
import oido
import oido_luz
import respeaker
import speaker
import vibrar

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
    d["luz"] = luz.prendida()
    d["verde"] = luces.prendida("verde")  # luz del "sí" (GPIO 27)
    d["rojo"] = luces.prendida("rojo")  # luz del "no" (GPIO 22)
    d["gpio23"] = gpios.prendido(23)  # salidas de los GPIO 23 y 24 (comando gpio23_24): solo lee el estado
    d["gpio24"] = gpios.prendido(24)
    d["camara"] = camara.activa()  # solo un booleano: no toca la cámara
    g = gesto.datos()  # dedo del medio a la vista y cuántas veces: solo copia variables
    if g:
        d["gesto"] = g
    o = oido.estado()  # ReSpeaker: de qué ángulo viene la voz y si hay alguien hablando
    if o:
        d["oido"] = o
    d["oido_luz"] = oido_luz.activa()  # la luz del micrófono sigue a la voz: solo un booleano
    d["escucha"] = escucha.datos()  # turno de escucha (entre el pitido de inicio y el de cierre): solo copia
    r = respeaker.datos()  # monitor del chip del micrófono (comando mic): energía de voz y haces; solo copia
    if r:
        d["respeaker"] = r
    d["speaker"] = speaker.sonando()  # hay una prueba del speaker sonando: solo un booleano
    d["vibrar"] = vibrar.activa()  # está vibrando (tono grave por el parlante): solo un booleano
    d["motores"] = motores.datos()  # motores (PCA9685): si se están moviendo y a qué potencia; solo copia
    sv = servos.datos()  # servos con pulso: canal -> ángulo; solo copia, no toca el bus
    if sv:
        d["servos"] = sv
    d["descubrir"] = descubrir.activa()  # está probando canales de motores: solo un booleano
    f = flujo.datos()  # ADNS-3080: solo copia lo último que leyó su hilo (si está prendido)
    if f:
        d["flujo"] = f
    f2 = flujo2.datos()  # segundo ADNS-3080 (spidev0.1): igual, solo copia
    if f2:
        d["flujo2"] = f2

    if SIMULAR:
        s = time.time() - _t0
        d["mic"] = round(abs(math.sin(s * 3.1)) * 0.6 + random.random() * 0.3, 3)
        d["imu"] = {"pitch": round(math.sin(s * 0.7) * 25, 2), "roll": round(math.cos(s * 0.5) * 12, 2)}
        d["dist_cm"] = round(60 + math.sin(s * 0.3) * 40, 1)
        d["servo"] = [round(90 + math.sin(s) * 60), round(90 + math.cos(s * 1.3) * 45)]
        d["boton"] = math.sin(s * 0.9) > 0.92
    return d
