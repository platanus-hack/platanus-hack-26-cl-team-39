"""
Motores del bicho (comando "motores"): 4 motores a través de un PCA9685 (I2C bus 1, dirección 0x40).

El PCA9685 solo genera PWM en 16 canales; qué canal va a qué motor depende de la placa, y eso NO se
puede averiguar por software. Por eso este módulo es prudente a propósito:

  - Nada se mueve sin una orden explícita, y nada se toca al importar.
  - Potencia hasta 100 % y sin tope de tiempo ("seg":0 = hasta "on":false), con rampa suave al partir.
  - Sube el STBY de los drivers (GPIO 27, 22, 23 y 24) al partir y lo baja al terminar.
  - Mover los 4 a la vez ("on":true) solo se permite después de confirmar el mapeo de canales
    ("confirmar":true), que se hace probando un motor a la vez con las ruedas en el aire.
  - Al terminar, al fallar, con "on":false y al salir el programa se apagan los 16 canales.
  - No cambia la frecuencia del PCA9685 (queda la que tenga; 200 Hz recién encendido).

Mapa: una lista con una entrada por motor. Cada entrada puede ser
  [a, b]         dos canales IN1/IN2: adelante = PWM en a y b en 0; atrás = al revés
  [pwm, in1, in2] un canal de velocidad y dos de sentido (TB6612 / Motor HAT)
  [pwm]          un solo canal, sin reversa
Queda guardado (junto con los motores invertidos) en <casa del bicho>/motores.json.

No bloquea: el movimiento corre en un hilo daemon que termina solo; lo que habla con el chip desde
manejar() va en hilos con espera corta. Con BICHO_SIMULAR=1 no se abre ningún dispositivo.
"""
from __future__ import annotations

import atexit
import json
import os
import threading
import time

import herramientas
import salida

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

BUS = 1
DIR = 0x40
POT_MAX = 100.0  # % de ciclo de trabajo: sin tope, para que pueda correr (ojo: son 9 V en motores de 3-6 V)
POT_DEF = 15.0
SIN_LIMITE = float("inf")  # "seg":0 = sigue hasta {"cmd":"motores","on":false}
SEG_DEF = 1.5
_RAMPA_SUBE = 0.4  # s
_RAMPA_BAJA = 0.2  # s
_ESPERA = 0.6  # cuánto espera manejar() a un hilo corto

PRESETS = {
    "pares": [[0, 1], [2, 3], [4, 5], [6, 7]],
    "adafruit": [[8, 10, 9], [13, 11, 12], [2, 4, 3], [7, 5, 6]],
    "simples": [[0], [1], [2], [3]],
}

AYUDA = (
    '{"cmd":"motores"}  estado (mapa, si está confirmado, cómo está el PCA9685 en 0x40)  ·  PRIMERO hay que'
    ' confirmar el mapeo de canales y el sentido de giro, con las ruedas en el aire y potencia mínima:'
    '  "mapa":"pares"|"adafruit"|"simples" o una lista como [[0,1],[2,3],[4,5],[6,7]] ([in1,in2], [pwm,in1,in2]'
    ' o [pwm] por motor)  ·  "motor":1,"pot":12,"seg":1 prueba un solo motor ("sentido":-1 hacia atrás)'
    '  ·  "canal":0,"pot":10,"seg":0.8 prueba un canal PWM en crudo  ·  "invertir":[4] da vuelta SOLO esos motores (los demás quedan como estaban; "invertidos":[1,4] fija la lista completa)'
    '  ·  "confirmar":true deja el mapa como confirmado  ·  recién entonces "on":true mueve los 4 suave'
    f' ("pot" hasta {POT_MAX:g} %; "seg" los segundos que quieras, o "seg":0 para que siga sin límite hasta "on":false; "sentido":-1 atrás)  ·  "on":false para todo'
    ' al tiro (apaga los 16 canales). Con "seg" mayor que cero se detiene solo al cumplirse el tiempo'
)

_lock = threading.Lock()  # estado del módulo
_bus_lock = threading.Lock()  # quién está hablando con el chip
_parar = threading.Event()
_hilo: threading.Thread | None = None
_potencia = 0.0  # % que se está aplicando ahora
_ultimo = ""  # resultado del último movimiento
_usado = False  # ya se tocó el chip alguna vez (para apagar al salir)
_cfg: dict | None = None


# ── configuración guardada ────────────────────────────────────────────────────


def _archivo():
    return herramientas._casa() / "motores.json"


def _config() -> dict:
    global _cfg
    with _lock:
        if _cfg is not None:
            return _cfg
        cfg = {"mapa": None, "invertir": [], "confirmado": False}
        try:
            d = json.loads(_archivo().read_text(encoding="utf-8"))
            if isinstance(d, dict):
                m = d.get("mapa")
                if m is not None and _validar_mapa(m) is None:
                    cfg["mapa"] = [list(x) for x in m]
                    cfg["confirmado"] = d.get("confirmado") is True
                    inv = d.get("invertir")
                    if isinstance(inv, list):
                        cfg["invertir"] = sorted({int(i) for i in inv if isinstance(i, int) and 1 <= i <= len(m)})
        except (OSError, ValueError, TypeError):
            pass
        _cfg = cfg
        return _cfg


def _guardar() -> str:
    cfg = _config()
    try:
        f = _archivo()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(".motores.tmp")
        tmp.write_text(json.dumps(cfg), encoding="utf-8")
        os.replace(tmp, f)
        return ""
    except OSError as e:
        return f" (no pude guardarlo: {e})"


def _validar_mapa(m) -> str | None:
    """None si el mapa sirve; si no, el motivo."""
    if not isinstance(m, list) or not 1 <= len(m) <= 8:
        return "tiene que ser una lista con una entrada por motor (1 a 8)"
    vistos: set[int] = set()
    for e in m:
        if not isinstance(e, list) or not 1 <= len(e) <= 3:
            return "cada motor es [in1,in2], [pwm,in1,in2] o [pwm]"
        for ch in e:
            if isinstance(ch, bool) or not isinstance(ch, int) or not 0 <= ch <= 15:
                return "los canales son enteros de 0 a 15"
            if ch in vistos:
                return f"el canal {ch} está repetido"
            vistos.add(ch)
    return None


def _seg(c: dict, defecto: float) -> float:
    """Cuánto dura: lo que pidan, sin tope. "seg":0 (o negativo) es sin límite: sigue hasta que lo paren."""
    v = c.get("seg")
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v <= 0:
        return SIN_LIMITE
    return _num(v, defecto, 0.2, 86400.0)


def _dur(seg: float) -> str:
    return "sin límite de tiempo" if seg == SIN_LIMITE else f"por {seg:g} s"


def _num(v, defecto: float, lo: float, hi: float) -> float:
    if isinstance(v, bool):
        return defecto
    try:
        x = float(v)
    except (TypeError, ValueError):
        return defecto
    if x != x:
        return defecto
    return max(lo, min(x, hi))


# ── PCA9685 ───────────────────────────────────────────────────────────────────


def _todo_apagado(b) -> None:
    """Apaga los 16 canales (bit full-off de ALL_LED). Lo primero que se escribe es lo que apaga."""
    b.write_byte_data(DIR, 0xFD, 0x10)  # ALL_LED_OFF_H: full off
    b.write_byte_data(DIR, 0xFB, 0x00)  # ALL_LED_ON_H: sin full on
    b.write_byte_data(DIR, 0xFA, 0x00)
    b.write_byte_data(DIR, 0xFC, 0x00)


def _escribir(b, canal: int, duty: float) -> None:
    if duty <= 0:
        datos = [0, 0, 0, 0x10]
    elif duty >= 1:
        datos = [0, 0x10, 0, 0]
    else:
        off = max(1, min(4095, int(round(duty * 4096))))
        datos = [0, 0, off & 0xFF, off >> 8]
    b.write_i2c_block_data(DIR, 0x06 + 4 * canal, datos)


def _preparar(b) -> float:
    """Comprueba que parezca un PCA9685 y lo despierta sin cambiarle la frecuencia. Devuelve los Hz."""
    m1 = b.read_byte_data(DIR, 0x00)
    pre = b.read_byte_data(DIR, 0xFE)
    if pre < 3:
        raise RuntimeError(f"lo que hay en 0x{DIR:02X} no parece un PCA9685 (PRE_SCALE={pre})")
    if m1 & 0x10:  # dormido: dejar todo apagado antes de despertar
        _todo_apagado(b)
    nuevo = (m1 & 0x6F) | 0x20  # sin RESTART, sin SLEEP, con auto-incremento
    if nuevo != m1:
        b.write_byte_data(DIR, 0x00, nuevo)
        time.sleep(0.005)
    return 25_000_000 / (4096 * (pre + 1))


def _apagar_chip() -> str:
    """Abre el bus y apaga todo, con reintentos. Devuelve "" si resultó, o el error."""
    if SIMULAR:
        return ""
    err = ""
    for _ in range(3):
        try:
            from smbus2 import SMBus

            b = SMBus(BUS)
            try:
                _todo_apagado(b)
            finally:
                b.close()
            return ""
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(0.05)
    return err


def _al_salir() -> None:
    _parar.set()
    if _usado:
        _apagar_chip()


def _leer_chip() -> str:
    if SIMULAR:
        return "simulado, sin PCA9685"
    if not os.path.exists(f"/dev/i2c-{BUS}"):
        return f"no existe /dev/i2c-{BUS} (I2C no habilitado)"
    if not _bus_lock.acquire(timeout=0.4):
        return "el chip está ocupado (hay un movimiento en curso)"
    try:
        from smbus2 import SMBus

        b = SMBus(BUS)
        try:
            m1 = b.read_byte_data(DIR, 0x00)
            pre = b.read_byte_data(DIR, 0xFE)
            activos = []
            for ch in range(16):
                r = [b.read_byte_data(DIR, 0x06 + 4 * ch + i) for i in range(4)]
                if r[3] & 0x10:
                    continue  # full off
                if r[1] & 0x10:
                    activos.append(f"{ch}=100%")
                    continue
                on = r[0] | ((r[1] & 0x0F) << 8)
                off = r[2] | ((r[3] & 0x0F) << 8)
                if off != on:
                    activos.append(f"{ch}={((off - on) % 4096) / 40.96:.0f}%")
        finally:
            b.close()
    except Exception as e:
        return f"no pude leer el PCA9685 en 0x{DIR:02X}: {type(e).__name__}: {e}"
    finally:
        _bus_lock.release()
    if pre < 3:
        return f"lo que hay en 0x{DIR:02X} no parece un PCA9685 (PRE_SCALE={pre})"
    hz = 25_000_000 / (4096 * (pre + 1))
    dormido = "dormido" if m1 & 0x10 else "despierto"
    return (
        f"PCA9685 en 0x{DIR:02X}: MODE1=0x{m1:02X} ({dormido}), ~{hz:.0f} Hz, "
        + ("canales con salida: " + ", ".join(activos) if activos else "los 16 canales apagados")
    )


def _con_tope(fn) -> str | None:
    """Corre fn en un hilo daemon y la espera a lo más _ESPERA. None si no alcanzó."""
    caja: dict = {}

    def _t():
        try:
            caja["r"] = fn()
        except Exception as e:
            caja["r"] = f"falló: {type(e).__name__}: {e}"

    h = threading.Thread(target=_t, name="motores-aux", daemon=True)
    h.start()
    h.join(_ESPERA)
    return caja.get("r")


# ── movimiento ────────────────────────────────────────────────────────────────


def _plan(indices: list[int], sentido: int) -> tuple[list[int], list[int], list[int]] | str:
    """Canales (pwm, en alto, en bajo) para mover esos motores (base 0). Texto si no se puede."""
    cfg = _config()
    pwm: list[int] = []
    altos: list[int] = []
    bajos: list[int] = []
    for i in indices:
        e = cfg["mapa"][i]
        s = -sentido if (i + 1) in cfg["invertir"] else sentido
        if len(e) == 1:
            if s < 0:
                return f"el motor {i + 1} tiene un solo canal ({e[0]}): no puede girar hacia atrás"
            pwm.append(e[0])
        elif len(e) == 2:
            a, b = (e[0], e[1]) if s > 0 else (e[1], e[0])
            pwm.append(a)
            bajos.append(b)
        else:
            pwm.append(e[0])
            a, b = (e[1], e[2]) if s > 0 else (e[2], e[1])
            altos.append(a)
            bajos.append(b)
    return pwm, altos, bajos


# STBY de los 4 drivers TB6612: sin eso en alto no gira nada, aunque el PCA9685 mande bien. Van en los
# GPIO 27 y 22 (los lleva luces.py) y 23 y 24 (gpios.py). BICHO_STBY=0 si algún día se cablean fijos a 3,3 V.
_USAR_STBY = os.environ.get("BICHO_STBY", "1") != "0"


def _standby(habilitar: bool) -> None:
    """En alto mientras se mueve; en bajo en reposo, así un PWM perdido no mueve ninguna rueda."""
    if not _USAR_STBY:
        return
    try:
        import gpios
        import luces

        luces.reservar(habilitar)
        gpios.poner(habilitar)
    except Exception:
        pass  # sin GPIO (simulación u otro computador) no hay nada que habilitar


def _trabajo(pwm: list[int], altos: list[int], bajos: list[int], pot: float, seg: float, desc: str) -> None:
    global _potencia, _ultimo, _usado
    err = ""
    hz = 0.0
    t0 = time.monotonic()
    tomado = _bus_lock.acquire(timeout=1.0)
    try:
        if not tomado:
            raise RuntimeError("el bus I2C está ocupado")
        _standby(True)
        if SIMULAR:
            _potencia = pot
            _parar.wait(None if seg == SIN_LIMITE else seg)
        else:
            from smbus2 import SMBus

            b = SMBus(BUS)
            try:
                hz = _preparar(b)
                _usado = True
                for ch in pwm + bajos:
                    _escribir(b, ch, 0)
                for ch in altos:
                    _escribir(b, ch, 1)
                duty = pot / 100.0
                actual = 0.0
                t0 = time.monotonic()
                while not _parar.is_set():
                    t = time.monotonic() - t0
                    if t >= seg:
                        break
                    f = min(1.0, t / _RAMPA_SUBE, (seg - t) / _RAMPA_BAJA)
                    nivel = duty * max(0.0, f)
                    if abs(nivel - actual) > 0.002:
                        for ch in pwm:
                            _escribir(b, ch, nivel)
                        actual = nivel
                        _potencia = round(nivel * 100, 1)
                    _parar.wait(0.04)
            finally:
                try:
                    _todo_apagado(b)
                except Exception:
                    pass  # se reintenta abajo con el bus recién abierto
                try:
                    b.close()
                except Exception:
                    pass
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    finally:
        apagado = _apagar_chip() if tomado and not SIMULAR else ""
        _standby(False)
        if tomado:
            _bus_lock.release()
        _potencia = 0.0
    dur = time.monotonic() - t0
    if apagado:
        txt = (
            f"motores: OJO, {desc}: NO PUDE APAGAR el PCA9685 ({apagado}). Corta la alimentación de los motores"
            ' y prueba {"cmd":"motores","on":false}'
        )
    elif err:
        txt = f"motores: {desc}: falló ({err}); canales apagados"
    else:
        como = "detenido por orden" if _parar.is_set() else "terminó solo"
        txt = f"motores: {desc}: {como} a los {dur:.1f} s" + (f" (PWM ~{hz:.0f} Hz)" if hz else "") + "; canales apagados"
    with _lock:
        _ultimo = txt
    salida.emitir({"t": "log", "lvl": "warn" if (err or apagado) else "info", "msg": txt})


def _lanzar(plan, pot: float, seg: float, desc: str) -> str | None:
    """Parte el hilo de movimiento. Devuelve un texto si no se pudo partir."""
    global _hilo, _registrado
    if not SIMULAR and not os.path.exists(f"/dev/i2c-{BUS}"):
        return f"motores: no existe /dev/i2c-{BUS}; no puedo hablar con el PCA9685"
    pwm, altos, bajos = plan
    with _lock:
        if _hilo is not None and _hilo.is_alive():
            return 'motores: ya hay un movimiento en curso; espera a que termine o páralo con {"cmd":"motores","on":false}'
        if not _registrado:
            atexit.register(_al_salir)
            _registrado = True
        _parar.clear()
        _hilo = threading.Thread(
            target=_trabajo, args=(pwm, altos, bajos, pot, seg, desc), name="motores", daemon=True
        )
        _hilo.start()
    return None


_registrado = False


def parar() -> str:
    _parar.set()
    with _lock:
        h = _hilo
    if h is not None and h.is_alive():
        h.join(_ESPERA)
        if h.is_alive():
            return "motores: orden de parar dada; el hilo todavía está apagando los canales"
        return "motores: detenidos; los 16 canales del PCA9685 apagados"
    if SIMULAR:
        return "motores: detenidos (simulado)"
    if not os.path.exists(f"/dev/i2c-{BUS}"):
        return f"motores: no hay nada moviéndose (y no existe /dev/i2c-{BUS})"

    def _off():
        if not _bus_lock.acquire(timeout=0.4):
            return "ocupado"
        try:
            return _apagar_chip()
        finally:
            _bus_lock.release()

    r = _con_tope(_off)
    if r is None:
        return "motores: mandé a apagar los 16 canales, pero el bus I2C está lento y aún no confirma"
    if r:
        return f"motores: no pude apagar el PCA9685 ({r}). Si algo gira, corta la alimentación de los motores"
    return "motores: no había movimiento; igual dejé los 16 canales del PCA9685 apagados"


def activa() -> bool:
    h = _hilo
    return h is not None and h.is_alive()


def datos() -> dict:
    """Para sensores.leer(): solo copia variables."""
    return {"activo": activa(), "pot": _potencia}


def _txt_mapa() -> str:
    cfg = _config()
    if not cfg["mapa"]:
        return "sin mapa de canales"
    partes = []
    for i, e in enumerate(cfg["mapa"], 1):
        if len(e) == 1:
            d = f"pwm {e[0]}"
        elif len(e) == 2:
            d = f"in1 {e[0]}, in2 {e[1]}"
        else:
            d = f"pwm {e[0]}, in1 {e[1]}, in2 {e[2]}"
        partes.append(f"M{i}: {d}" + (" (invertido)" if i in cfg["invertir"] else ""))
    return "mapa " + ("CONFIRMADO" if cfg["confirmado"] else "SIN CONFIRMAR") + ": " + " · ".join(partes)


_PASOS = (
    'Pasos, con las ruedas en el aire: 1) elige el mapa según tu placa: {"cmd":"motores","mapa":"pares"} (o'
    ' "adafruit", o una lista propia)  2) prueba de a uno: {"cmd":"motores","motor":1,"pot":12,"seg":1} y mira'
    ' cuál gira y hacia dónde (sube "pot" de a poco si no parte; "canal":N prueba un canal en crudo)'
    '  3) da vuelta los que giren al revés: "invertir":[2,4]  4) {"cmd":"motores","confirmar":true}'
    '  5) {"cmd":"motores","on":true}. Para parar: {"cmd":"motores","on":false}'
)


def estado() -> str:
    cfg = _config()
    partes = [_txt_mapa()]
    if activa():
        partes.append(f"moviéndose ahora ({_potencia:g} %)")
    else:
        partes.append("quieto")
        chip = _con_tope(_leer_chip)
        partes.append(chip if chip else "el PCA9685 no contestó a tiempo")
    with _lock:
        if _ultimo:
            partes.append("último: " + _ultimo)
    txt = "motores: " + " | ".join(partes) + f" | potencia hasta {POT_MAX:g} %, sin tope de tiempo (\"seg\":0 = hasta \"on\":false)"
    if not cfg["confirmado"]:
        txt += ". " + _PASOS
    return txt[:1900]


def _aviso_pot(c: dict, pot: float) -> str:
    try:
        pedido = float(c.get("pot"))
    except (TypeError, ValueError):
        return ""
    return f" (pediste {pedido:g} %, el tope es {POT_MAX:g} %)" if pedido > POT_MAX else ""


def manejar(c: dict) -> str:
    # 1. Parar tiene prioridad sobre todo lo demás.
    if ("on" in c and not c.get("on")) or c.get("parar"):
        return parar()

    cfg = _config()

    # 2. Configuración: no mueve nada.
    if "mapa" in c or "invertir" in c or "invertidos" in c or "confirmar" in c:
        if activa():
            return 'motores: primero páralos ({"cmd":"motores","on":false}) y después cambia la configuración'
        partes = []
        if "mapa" in c:
            m = c.get("mapa")
            if isinstance(m, str):
                k = m.strip().lower()
                if k not in PRESETS:
                    return "motores: mapas con nombre: " + ", ".join(PRESETS) + "; o una lista como [[0,1],[2,3],[4,5],[6,7]]"
                m = [list(x) for x in PRESETS[k]]
            motivo = _validar_mapa(m)
            if motivo:
                return f'motores: "mapa" {motivo}'
            with _lock:
                cfg["mapa"] = [list(x) for x in m]
                cfg["invertir"] = []
                cfg["confirmado"] = False
            partes.append("mapa cambiado (queda sin confirmar)")
        if "invertir" in c:
            inv = c.get("invertir")
            if isinstance(inv, int) and not isinstance(inv, bool):
                inv = [inv]
            if not cfg["mapa"]:
                return 'motores: primero elige un "mapa"'
            n = len(cfg["mapa"])
            if not isinstance(inv, list) or any(isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= n for i in inv):
                return f'motores: "invertir" es la lista de motores a dar vuelta, de 1 a {n}, por ejemplo [4]; los demás quedan como estaban'
            with _lock:
                # "Da vuelta": cambia el sentido de ESOS motores y deja los demás como estaban. Antes esta lista
                # reemplazaba a la anterior, y dar vuelta el motor 4 dejaba el 1 de nuevo al revés sin avisar.
                cfg["invertir"] = sorted(set(cfg["invertir"]) ^ set(inv))
            partes.append(
                "di vuelta " + (", ".join(f"M{i}" for i in sorted(set(inv))) or "ninguno")
                + "; ahora invertidos: " + (", ".join(f"M{i}" for i in cfg["invertir"]) or "ninguno")
            )
        if "invertidos" in c:
            inv = c.get("invertidos")
            if isinstance(inv, int) and not isinstance(inv, bool):
                inv = [inv]
            if not cfg["mapa"]:
                return 'motores: primero elige un "mapa"'
            n = len(cfg["mapa"])
            if not isinstance(inv, list) or any(isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= n for i in inv):
                return f'motores: "invertidos" es la lista completa de motores invertidos, de 1 a {n}, por ejemplo [1,4] ([] para ninguno)'
            with _lock:
                cfg["invertir"] = sorted(set(inv))
            partes.append("invertidos: " + (", ".join(f"M{i}" for i in cfg["invertir"]) or "ninguno"))
        if "confirmar" in c:
            if c.get("confirmar") is True and not cfg["mapa"]:
                return 'motores: no hay mapa que confirmar. ' + _PASOS
            with _lock:
                cfg["confirmado"] = c.get("confirmar") is True
            partes.append(
                "mapa confirmado: ya se puede usar \"on\":true" if cfg["confirmado"] else "mapa marcado como sin confirmar"
            )
        return "motores: " + " · ".join(partes) + _guardar() + " | " + _txt_mapa()

    pot = _num(c.get("pot"), POT_DEF, 1.0, POT_MAX)
    sentido = -1 if _num(c.get("sentido"), 1, -1, 1) < 0 else 1
    hacia = "adelante" if sentido > 0 else "atrás"

    # 3. Un canal PWM en crudo (para descubrir el mapeo).
    if "canal" in c:
        ch = c.get("canal")
        if isinstance(ch, bool) or not isinstance(ch, int) or not 0 <= ch <= 15:
            return 'motores: "canal" va de 0 a 15'
        seg = _seg(c, 0.8)
        no = _lanzar(([ch], [], []), pot, seg, f"canal {ch} al {pot:g} % {_dur(seg)}")
        return no or (
            f"motores: canal {ch} del PCA9685 al {pot:g} % {_dur(seg)}{_aviso_pot(c, pot)}; se apaga solo. Mira"
            " qué motor se mueve y hacia dónde (en placas con canal de velocidad + dos de sentido, un canal solo no mueve nada)"
        )

    # 4. Un solo motor (para confirmar mapeo y sentido).
    if "motor" in c:
        if not cfg["mapa"]:
            return "motores: todavía no hay mapa de canales. " + _PASOS
        n = c.get("motor")
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= len(cfg["mapa"]):
            return f'motores: "motor" va de 1 a {len(cfg["mapa"])}'
        seg = _seg(c, 1.0)
        plan = _plan([n - 1], sentido)
        if isinstance(plan, str):
            return "motores: " + plan
        no = _lanzar(plan, pot, seg, f"motor {n} {hacia} al {pot:g} % {_dur(seg)}")
        return no or (
            f"motores: motor {n} {hacia} al {pot:g} % {_dur(seg)}{_aviso_pot(c, pot)} (canal PWM {plan[0][0]});"
            + (" sigue hasta que lo pares con \"on\":false." if seg == SIN_LIMITE else " se detiene solo.")
            + " Fíjate cuál rueda gira y si va hacia adelante"
        )

    # 5. Los 4 a la vez: solo con el mapa confirmado.
    if c.get("on"):
        if not cfg["mapa"]:
            return "motores: no los muevo todavía: no hay mapa de canales. " + _PASOS
        if not cfg["confirmado"]:
            return "motores: no muevo todos a la vez con el mapa sin confirmar (" + _txt_mapa() + "). " + _PASOS
        seg = _seg(c, SEG_DEF)
        plan = _plan(list(range(len(cfg["mapa"]))), sentido)
        if isinstance(plan, str):
            return "motores: " + plan
        n = len(cfg["mapa"])
        no = _lanzar(plan, pot, seg, f"{n} motores {hacia} al {pot:g} % {_dur(seg)}")
        return no or (
            f"motores: {n} motores {hacia} al {pot:g} % {_dur(seg)}{_aviso_pot(c, pot)}, con rampa suave; "
            + ("siguen hasta que los pares" if seg == SIN_LIMITE else "se detienen solos")
            + '. Para parar: {"cmd":"motores","on":false}'
        )

    return estado()
