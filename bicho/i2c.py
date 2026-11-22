"""
Escáner del bus I2C del bicho (comando "i2c"): qué direcciones responden y qué podrían ser.

  {"cmd":"i2c"}                 escanea el bus 1 (pines físicos 3 y 5 = GPIO 2 SDA y GPIO 3 SCL)
  {"cmd":"i2c","bus":2}         otro bus que exista (los de la cámara, 0/10/11, no se tocan)
  {"cmd":"i2c","ultimo":true}   repite el último resultado sin volver a escanear

Hace lo mismo que "i2cdetect -y": a cada dirección 0x08-0x77 le manda un sondeo mínimo (lectura de
un byte en 0x30-0x37 y 0x50-0x5F, "quick write" en el resto) y anota cuáles contestan. No configura
ni mueve nada. Si aparece algo en 0x40-0x47 o 0x60-0x67 lee además dos registros (MODE1 y PRE_SCALE)
para decir si parece un PCA9685, el chip típico de los drivers de motores y servos.

Si el bus no está habilitado (no existe /dev/i2c-N) lo dice y explica cómo habilitarlo; el bicho
no cambia la configuración del sistema.

No bloquea: el escaneo corre en un hilo daemon que parte con el comando y termina solo; manejar()
lo espera a lo más 0,6 s y, si tarda más, el resultado sale después por la consola.
Nada se abre al importar, y con BICHO_SIMULAR=1 no se toca ningún dispositivo.
"""
from __future__ import annotations

import errno
import glob
import os
import subprocess
import threading
import time

import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

AYUDA = (
    '{"cmd":"i2c"}  escanea el bus I2C 1 (pines 3 y 5) y lista las direcciones que responden, en hexadecimal,'
    ' con lo que podrían ser (PCA9685 en 0x40, Motor HAT en 0x60, MD25 en 0x58...)  ·  "bus":2 otro bus'
    ' (los de la cámara no)  ·  "ultimo":true repite el último resultado  ·  solo sondea, no mueve nada; si el'
    ' bus no está habilitado dice cómo habilitarlo'
)

_BUS_CAMARA = (0, 10, 11)  # i2c0 y su multiplexor: sensor de la cámara y EEPROM de HATs; no se sondean
_TOPE_SEG = 8.0  # un escaneo normal tarda mucho menos de 1 s; si el bus está pegado, se corta aquí
_ESPERA = 0.6  # cuánto espera manejar() al hilo antes de contestar "sigo escaneando"
_NADIE = (errno.ENXIO, getattr(errno, "EREMOTEIO", 121))  # lo que devuelve el kernel cuando nadie contesta en esa dirección

# Dirección de 7 bits -> qué suele haber ahí (pistas, no certezas).
_CONOCIDOS = {
    0x0F: "Grove I2C Motor Driver (L298)",
    0x14: "Grove I2C Motor Driver (TB6612)",
    0x1E: "magnetómetro HMC5883L",
    0x29: "sensor de distancia VL53L0X / color TCS34725",
    0x30: "motor shield Wemos/LOLIN",
    0x3C: "pantalla OLED SSD1306",
    0x3D: "pantalla OLED SSD1306",
    0x48: "ADC ADS1115 / PCF8591",
    0x53: "acelerómetro ADXL345",
    0x68: "IMU MPU-6050 / reloj DS3231",
    0x69: "IMU MPU-6050 (AD0 en alto)",
    0x70: "dirección general (all call) de un PCA9685, o multiplexor TCA9548A",
    0x76: "BME280 / BMP280",
    0x77: "BME280 / BMP180",
}

_lock = threading.Lock()
_hilo: threading.Thread | None = None
_ultimo: str = ""
_ultimo_t: float = 0.0


def _pista(addr: int) -> str:
    if addr in _CONOCIDOS:
        return _CONOCIDOS[addr]
    if addr == 0x40:
        return "típico de un PCA9685 (driver PWM de motores/servos); también INA219 o HTU21D"
    if 0x41 <= addr <= 0x4F:
        return "PCA9685 con otra dirección, o INA219"
    if addr == 0x60:
        return "típico de un Motor HAT / Motor Shield v2 de Adafruit (PCA9685) o un DRV8830; también MCP4725"
    if 0x61 <= addr <= 0x6F and addr not in (0x68, 0x69):
        return "Motor HAT apilado (PCA9685) o DRV8830"
    if 0x58 <= addr <= 0x5F:
        return "controlador de motores MD25/MD03 (0xB0-0xBE en 8 bits), o una EEPROM"
    if 0x50 <= addr <= 0x57:
        return "EEPROM"
    if 0x20 <= addr <= 0x27:
        return "expansor de pines MCP23017 / PCF8574"
    return ""


def _buses() -> list[int]:
    out = []
    for p in glob.glob("/dev/i2c-*"):
        try:
            out.append(int(p.rsplit("-", 1)[1]))
        except ValueError:
            pass
    return sorted(out)


def _pines() -> str:
    """Cómo están GPIO 2 y 3 según pinctrl (solo lectura). Texto corto, o "" si no se pudo."""
    try:
        r = subprocess.run(["pinctrl", "get", "2,3"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return ""
    partes = []
    for linea in r.stdout.splitlines():
        if "//" in linea:
            partes.append(linea.split("//", 1)[1].strip())
    return ", ".join(partes)[:120]


def _config() -> str:
    """Qué dice config.txt sobre i2c_arm (solo lectura)."""
    for ruta in ("/boot/firmware/config.txt", "/boot/config.txt"):
        try:
            with open(ruta, encoding="utf-8", errors="replace") as f:
                lineas = f.read(100_000).splitlines()
        except OSError:
            continue
        hallado = [l.strip() for l in lineas if "i2c_arm" in l and not l.strip().startswith("#")]
        if hallado:
            return f"{ruta} tiene {hallado[-1][:60]!r}"
        return f"{ruta} no tiene dtparam=i2c_arm=on"
    return ""


def _sin_bus(bus: int) -> str:
    otros = _buses()
    txt = f"i2c: el bus {bus} no está habilitado en este Pi: no existe /dev/i2c-{bus}"
    if otros:
        txt += " (solo hay " + ", ".join(f"i2c-{b}" for b in otros) + ", que son de la cámara y el HDMI)"
    txt += "."
    if bus == 1:
        p = _pines()
        if p:
            txt += f" Pines 3 y 5: {p}"
            txt += "." if "SDA" in p or "SCL" in p else " (para I2C deberían decir SDA1 y SCL1)."
        cfg = _config()
        if cfg:
            txt += f" {cfg}."
        txt += (
            " Así no puedo ver nada de lo conectado a los pines 3 y 5. Para habilitarlo: sudo raspi-config nonint"
            " do_i2c 0 (o agregar dtparam=i2c_arm=on a /boot/firmware/config.txt) y reiniciar el Pi; yo no cambio"
            ' la configuración del sistema. Después repite {"cmd":"i2c"}.'
        )
    return txt


def _pca9685(b, addr: int) -> str:
    """Lee MODE1 (0x00) y PRE_SCALE (0xFE) sin escribir nada. Devuelve una pista o ""."""
    try:
        modo = b.read_byte_data(addr, 0x00)
        pre = b.read_byte_data(addr, 0xFE)
    except OSError:
        return ""
    if pre < 3:
        return ""  # un PCA9685 nunca tiene PRE_SCALE menor que 3
    hz = 25_000_000 / (4096 * (pre + 1))
    dormido = "dormido" if modo & 0x10 else "despierto"
    if pre == 0x1E and modo == 0x11:
        return f"los registros calzan con un PCA9685 recién encendido (MODE1=0x11, PRE_SCALE=0x1E, {dormido})"
    return f"si es un PCA9685: MODE1=0x{modo:02X} ({dormido}), PRE_SCALE=0x{pre:02X} (~{hz:.0f} Hz)"


def _escanear(bus: int) -> str:
    if not os.path.exists(f"/dev/i2c-{bus}"):
        return _sin_bus(bus)
    try:
        from smbus2 import SMBus
    except Exception as e:
        return f"i2c: no pude cargar smbus2: {type(e).__name__}: {e}"
    try:
        b = SMBus(bus)
    except PermissionError:
        return f"i2c: no tengo permiso para abrir /dev/i2c-{bus} (el usuario del bicho tiene que estar en el grupo i2c)"
    except OSError as e:
        return f"i2c: no pude abrir /dev/i2c-{bus}: {e}"

    hallados: list[int] = []
    ocupados: list[int] = []
    raros: dict[str, int] = {}  # otros errores del bus, por nombre (ETIMEDOUT, EIO, EOPNOTSUPP...)
    cortado = False
    t0 = time.monotonic()
    detalles: dict[int, str] = {}
    try:
        for addr in range(0x08, 0x78):
            if time.monotonic() - t0 > _TOPE_SEG:
                cortado = True
                break
            try:
                if 0x30 <= addr <= 0x37 or 0x50 <= addr <= 0x5F:
                    b.read_byte(addr)
                else:
                    b.write_quick(addr)
                hallados.append(addr)
            except OSError as e:
                if e.errno == errno.EBUSY:
                    ocupados.append(addr)  # lo tiene tomado un driver del kernel (el "UU" de i2cdetect)
                elif e.errno not in _NADIE:
                    nombre = errno.errorcode.get(e.errno or 0, f"errno {e.errno}")
                    raros[nombre] = raros.get(nombre, 0) + 1
        for addr in hallados:
            if 0x40 <= addr <= 0x47 or 0x60 <= addr <= 0x67:
                d = _pca9685(b, addr)
                if d:
                    detalles[addr] = d
    finally:
        try:
            b.close()
        except OSError:
            pass
    seg = time.monotonic() - t0

    if not hallados and not ocupados:
        txt = f"i2c bus {bus}: no respondió ningún dispositivo (0x08-0x77, {seg:.1f} s)"
        if bus == 1:
            txt += ". Revisa que el driver tenga alimentación y GND común con el Pi, SDA en el pin 3 y SCL en el pin 5"
    else:
        partes = []
        for addr in hallados:
            p = _pista(addr)
            d = detalles.get(addr)
            extra = "; ".join(x for x in (p, d) if x)
            partes.append(f"0x{addr:02X}" + (f" ({extra})" if extra else ""))
        for addr in ocupados:
            partes.append(f"0x{addr:02X} (en uso por un driver del kernel)")
        n = len(hallados) + len(ocupados)
        txt = f"i2c bus {bus}: {n} dispositivo{'s' if n != 1 else ''}: " + " · ".join(partes)
        if 0x70 in hallados and any(0x40 <= a <= 0x6F and a in detalles for a in hallados):
            txt += ". Ojo: 0x70 es el mismo PCA9685 contestando en su dirección general, no otro chip"
    if raros:
        detalle = ", ".join(f"{k} ×{v}" for k, v in sorted(raros.items()))
        txt += f". En {sum(raros.values())} direcciones el sondeo dio otro error ({detalle}), así que ahí no sé si hay algo"
        if "ETIMEDOUT" in raros:
            txt += "; los timeout suelen ser un cable suelto, falta de pull-up o una línea pegada a GND"
    if cortado:
        txt += f". Corté el escaneo a los {_TOPE_SEG:g} s: el bus está muy lento o pegado"
    return txt[:1800]


def _trabajo(bus: int, caja: dict) -> None:
    global _ultimo, _ultimo_t
    try:
        txt = _escanear(bus)
    except Exception as e:  # nunca dejar morir el hilo sin contestar
        txt = f"i2c: falló el escaneo: {type(e).__name__}: {e}"
    with _lock:
        _ultimo, _ultimo_t = txt, time.time()
        caja["txt"] = txt
        avisar = caja.get("avisar")
    if avisar:
        salida.emitir({"t": "log", "lvl": "info", "msg": txt})


def ultimo() -> str:
    with _lock:
        if not _ultimo:
            return 'i2c: todavía no he escaneado. Usa {"cmd":"i2c"}'
        return f"(hace {time.time() - _ultimo_t:.0f} s) {_ultimo}"


def manejar(c: dict) -> str:
    global _hilo
    if c.get("ultimo"):
        return ultimo()
    try:
        bus = int(c.get("bus", 1))
    except (TypeError, ValueError):
        return 'i2c: "bus" tiene que ser un número, por ejemplo 1'
    if not 0 <= bus <= 99:
        return 'i2c: "bus" tiene que estar entre 0 y 99'
    if bus in _BUS_CAMARA:
        return f"i2c: el bus {bus} es el de la cámara, no lo sondeo. Los motores van en el bus 1 (pines 3 y 5)"
    if SIMULAR:
        return f"i2c: simulado, no hay bus {bus} que escanear"
    caja: dict = {}
    with _lock:
        if _hilo is not None and _hilo.is_alive():
            return 'i2c: sigo escaneando; el resultado sale por la consola (o pide {"cmd":"i2c","ultimo":true})'
        _hilo = threading.Thread(target=_trabajo, args=(bus, caja), name="i2c-scan", daemon=True)
        _hilo.start()
        hilo = _hilo
    hilo.join(_ESPERA)
    with _lock:
        if "txt" in caja:
            return caja["txt"]
        caja["avisar"] = True
    return f'i2c: escaneando el bus {bus}…; el resultado sale por la consola (o pide {{"cmd":"i2c","ultimo":true}})'
