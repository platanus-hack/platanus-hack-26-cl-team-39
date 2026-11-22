"""
Servos del bicho (comando "servo"): hasta 16 servos en un SEGUNDO PCA9685, en la dirección 0x41.

No se usa el PCA9685 de los motores (0x40) porque la frecuencia es una sola por chip: los motores van a
~200 Hz y un servo necesita 50 Hz. Un servo no se maneja con "potencia" sino con el ANCHO de un pulso que
se repite 50 veces por segundo: ~500 µs es un extremo, ~1500 µs el centro y ~2500 µs el otro extremo.

Cableado (distinto al de los motores):
  - El servo va en las TRES filas de un canal: señal (amarillo), V+ (rojo) y GND (negro o café).
  - La bornera verde del PCA alimenta los servos: 5 a 6 V de una fuente aparte. NUNCA los 9 V de los
    motores (quema el servo) ni los 5 V del Pi (los picos de corriente lo reinician).
  - VCC a 3,3 V del Pi, SDA y SCL en paralelo con el otro PCA, GND común, OE a GND o sin conectar.
  - Dirección 0x41: hay que soldar el puente A0 de este PCA. Sin eso responde en 0x40 y choca con el de
    los motores. {"cmd":"i2c"} muestra qué direcciones hay.

Seguridad: nada se mueve hasta que llega un comando; "soltar" corta el pulso (el servo queda suelto); al
salir el programa se sueltan todos. Lo último pedido queda guardado en <casa del bicho>/servos.json solo
como referencia (no se repone al arrancar: un servo que parte solo puede pegarle a algo).
"""
from __future__ import annotations

import atexit
import json
import os
import threading
import time

import herramientas

BUS = 1
DIR = int(os.environ.get("BICHO_SERVOS_DIR", "0x41"), 0)
HZ = 50.0
US_MIN = 500.0  # ancho de pulso del ángulo 0 (µs)
US_MAX = 2500.0  # ancho de pulso del ángulo 180 (µs)
SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

AYUDA = (
    '{"cmd":"servo"}  estado (qué servos tienen pulso y en qué ángulo; cómo está el PCA9685 de 0x41)  ·  '
    '{"cmd":"servo","i":0,"deg":90} lleva el servo del canal 0 a 90° (de 0 a 180)  ·  "us":1500 manda el ancho'
    ' de pulso en crudo (de 400 a 2600 µs), para calibrar un servo que no llega a los extremos  ·  '
    '"barrer":true con "i" lo pasea 0 → 180 → 90 para probarlo  ·  {"cmd":"servo","i":0,"soltar":true} le corta'
    ' el pulso y queda suelto  ·  {"cmd":"servo","soltar":true} suelta todos. Van en un segundo PCA9685 (0x41,'
    ' puente A0 soldado), a 50 Hz, con los servos alimentados a 5-6 V por la bornera verde'
)

_lock = threading.Lock()
_pulsos: dict[int, float] = {}  # canal -> µs que tiene ahora (solo los que tienen pulso)
_listo = False  # el chip ya quedó a 50 Hz en esta corrida
_registrado = False
_barriendo: threading.Thread | None = None


def _archivo():
    return herramientas._casa() / "servos.json"


def _guardar() -> None:
    try:
        f = _archivo()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(".servos.tmp")
        tmp.write_text(json.dumps({"us": {str(k): round(v) for k, v in sorted(_pulsos.items())}}))
        tmp.replace(f)
    except Exception:
        pass  # sin disco igual se mueven


def _grados(us: float) -> float:
    return round((us - US_MIN) * 180.0 / (US_MAX - US_MIN), 1)


def _us(deg: float) -> float:
    return US_MIN + (US_MAX - US_MIN) * deg / 180.0


def _abrir():
    from smbus2 import SMBus

    return SMBus(BUS)


def _preparar(b) -> None:
    """Deja el PCA9685 de los servos despierto y a 50 Hz. Cambiar la frecuencia exige dormirlo un instante."""
    global _listo
    m1 = b.read_byte_data(DIR, 0x00)
    pre = b.read_byte_data(DIR, 0xFE)
    if pre < 3:
        raise RuntimeError(f"lo que hay en 0x{DIR:02X} no parece un PCA9685 (PRE_SCALE={pre})")
    quiero = int(round(25_000_000 / (4096 * HZ))) - 1  # 121 para 50 Hz
    if pre != quiero or (m1 & 0x10) or not _listo:
        if pre != quiero or (m1 & 0x10):
            b.write_byte_data(DIR, 0xFD, 0x10)  # todo apagado antes de tocar la frecuencia
            b.write_byte_data(DIR, 0x00, (m1 & 0x6F) | 0x10)  # dormir: solo así acepta PRE_SCALE
            b.write_byte_data(DIR, 0xFE, quiero)
            b.write_byte_data(DIR, 0x00, 0x20)  # despierto, con auto-incremento
            time.sleep(0.005)
        b.write_byte_data(DIR, 0x01, 0x04)  # salidas totem-pole
        _listo = True


def _poner(b, canal: int, us: float | None) -> None:
    base = 0x06 + 4 * canal
    if us is None:
        b.write_i2c_block_data(DIR, base, [0, 0, 0, 0x10])  # full off: sin pulso
        return
    cuentas = max(1, min(4095, int(round(us * HZ * 4096 / 1_000_000))))
    b.write_i2c_block_data(DIR, base, [0, 0, cuentas & 0xFF, cuentas >> 8])


def _aplicar(cambios: dict[int, float | None]) -> str:
    """Manda los pulsos. Devuelve "" si resultó o el motivo si no."""
    global _registrado
    if not SIMULAR:
        if not os.path.exists(f"/dev/i2c-{BUS}"):
            return f"no existe /dev/i2c-{BUS}: el bus I2C no está habilitado"
        try:
            b = _abrir()
        except Exception as e:
            return f"no pude abrir el bus I2C: {type(e).__name__}: {e}"
        try:
            _preparar(b)
            for canal, us in cambios.items():
                _poner(b, canal, us)
        except OSError as e:
            return (
                f"el PCA9685 de los servos no responde en 0x{DIR:02X} ({e.strerror or e}). Revisa que tenga VCC y"
                ' que el puente A0 esté soldado (sin él responde en 0x40, la de los motores); {"cmd":"i2c"} muestra'
                " qué direcciones hay"
            )
        except Exception as e:
            return f"{type(e).__name__}: {e}"
        finally:
            try:
                b.close()
            except Exception:
                pass
    with _lock:
        for canal, us in cambios.items():
            if us is None:
                _pulsos.pop(canal, None)
            else:
                _pulsos[canal] = us
        if not _registrado:
            atexit.register(_al_salir)
            _registrado = True
    _guardar()
    return ""


def _al_salir() -> None:
    try:
        if _pulsos:
            _aplicar({c: None for c in list(_pulsos)})
    except Exception:
        pass


def _barrer(canal: int) -> None:
    for deg in (0.0, 180.0, 90.0):
        if _aplicar({canal: _us(deg)}):
            return
        time.sleep(0.7)


def datos() -> dict:
    """Para los sensores: canal -> ángulo de los servos que tienen pulso. Solo copia, no toca el bus."""
    with _lock:
        return {str(c): _grados(us) for c, us in sorted(_pulsos.items())}


def estado() -> str:
    with _lock:
        activos = ", ".join(f"canal {c} en {_grados(us):g}° ({us:.0f} µs)" for c, us in sorted(_pulsos.items()))
    chip = "simulado, sin PCA9685"
    if not SIMULAR:
        if not os.path.exists(f"/dev/i2c-{BUS}"):
            chip = f"no existe /dev/i2c-{BUS}"
        else:
            try:
                b = _abrir()
                try:
                    m1 = b.read_byte_data(DIR, 0x00)
                    pre = b.read_byte_data(DIR, 0xFE)
                finally:
                    b.close()
                hz = 25_000_000 / (4096 * (pre + 1))
                chip = f"PCA9685 en 0x{DIR:02X}: {'dormido' if m1 & 0x10 else 'despierto'}, ~{hz:.0f} Hz" + (
                    "" if abs(hz - HZ) < 3 else f" (se pone a {HZ:g} Hz con el primer movimiento)"
                )
            except Exception as e:
                chip = f"nadie responde en 0x{DIR:02X} ({type(e).__name__}): ¿está conectado y con el puente A0 soldado?"
    return "servo: " + (activos or "ningún servo tiene pulso (están sueltos)") + " | " + chip


def manejar(c: dict) -> str:
    global _barriendo
    i = c.get("i", c.get("canal"))
    tiene_i = i is not None
    if tiene_i and (isinstance(i, bool) or not isinstance(i, int) or not 0 <= i <= 15):
        return 'servo: "i" es el canal del PCA9685, de 0 a 15'

    if c.get("soltar") or ("on" in c and not c.get("on")):
        canales = [i] if tiene_i else list(range(16))
        no = _aplicar({ch: None for ch in canales})
        if no:
            return "servo: " + no
        return "servo: " + (f"canal {i} suelto (sin pulso)" if tiene_i else "todos los servos sueltos (sin pulso)")

    if not tiene_i:
        if any(k in c for k in ("deg", "us", "barrer")):
            return 'servo: falta "i" (el canal, de 0 a 15). Por ejemplo {"cmd":"servo","i":0,"deg":90}'
        return estado()

    if c.get("barrer"):
        if _barriendo is not None and _barriendo.is_alive():
            return "servo: ya hay un barrido en curso; espera un par de segundos"
        no = _aplicar({i: _us(90.0)})
        if no:
            return "servo: " + no
        _barriendo = threading.Thread(target=_barrer, args=(i,), name="servo-barrer", daemon=True)
        _barriendo.start()
        return f"servo: barro el canal {i}: 0° → 180° → 90°, 0,7 s en cada uno. Mira que llegue a los extremos sin forzarse"

    if "us" in c:
        us = c.get("us")
        if isinstance(us, bool) or not isinstance(us, (int, float)) or not 400 <= us <= 2600:
            return 'servo: "us" es el ancho del pulso en microsegundos, de 400 a 2600 (1500 es el centro)'
        us = float(us)
    elif "deg" in c:
        deg = c.get("deg")
        if isinstance(deg, bool) or not isinstance(deg, (int, float)) or not 0 <= deg <= 180:
            return 'servo: "deg" va de 0 a 180'
        us = _us(float(deg))
    else:
        return f'servo: di a dónde: "deg" (0 a 180) o "us" (400 a 2600). Canal {i}: ' + (
            f"está en {_grados(_pulsos[i]):g}°" if i in _pulsos else "sin pulso"
        )

    no = _aplicar({i: us})
    if no:
        return "servo: " + no
    return f"servo: canal {i} a {_grados(us):g}° (pulso de {us:.0f} µs a {HZ:g} Hz); queda sosteniendo esa posición. Para soltarlo: \"soltar\":true"
