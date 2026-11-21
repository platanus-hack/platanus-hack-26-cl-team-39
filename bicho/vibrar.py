"""
Vibrar: el bicho no tiene motor vibrador (el diagnóstico no muestra ninguno: los únicos GPIO de salida
son las luces 17/22/27 y los chip select del SPI), así que vibra con lo que sí tiene: el parlante.
Toca pulsos de un tono grave (por defecto 80 Hz) por la salida de audio elegida en speaker.py; con el
parlante apoyado en el cuerpo del bicho eso se siente como un zumbido/vibración.

    vibrar.vibrar(seg=3, hz=80, vol=100, continuo=False)   parte la vibración (no bloquea)
    vibrar.parar()                                         la corta
    vibrar.estado()                                        cómo está
    vibrar.activa()                                        booleano barato para sensores.py

No abre nada al importar. El sonido lo toca speaker.py (aplay en un hilo daemon con timeout), así que
comparte su candado: mientras vibra no se puede probar el speaker y al revés.
El bicho no puede sentirse: "aplay terminó bien" significa que ALSA aceptó el audio, no que vibró.
"""
from __future__ import annotations

import os
import time

import speaker

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

_fin = 0.0  # time.monotonic() hasta el que dura la vibración que yo lancé
_ultima = "todavía no he vibrado"


def _num(v, defecto: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = defecto
    if x != x:
        x = defecto
    return max(lo, min(x, hi))


def activa() -> bool:
    return speaker.sonando() and time.monotonic() < _fin


def vibrar(seg=None, hz=None, vol=None, continuo=False) -> str:
    global _fin, _ultima
    if SIMULAR:
        return "vibrar: simulado (sin hardware no vibra nada)"
    s = _num(seg, 3.0, 0.3, 10.0)
    f = _num(hz, 80.0, 30.0, 250.0)
    v = _num(vol, 100.0, 1.0, 100.0)
    if continuo:
        patron = [(f, s)]
    else:
        patron, total = [], 0.0
        while total < s - 0.01:
            d = min(0.35, s - total)
            patron.append((f, d))
            total += d
            if total < s - 0.01:
                patron.append((0.0, 0.12))
                total += 0.12
    dev = speaker.actual()
    if not speaker._lanzar([(dev, patron)], v):
        if activa():
            return 'vibrar: ya estoy vibrando (para cortar: {"cmd":"vibrar","on":false})'
        return 'vibrar: el parlante está ocupado con otro sonido (córtalo con {"cmd":"speaker","on":false})'
    dura = sum(d for _, d in patron)
    _fin = time.monotonic() + dura + 8.0
    _ultima = f"última vibración {time.strftime('%H:%M:%S')}: {f:g} Hz, {dura:.1f} s, vol {v:g}%, por {dev}"
    return (f"vibrar: vibrando {dura:.1f} s con {'un tono' if continuo else 'pulsos'} de {f:g} Hz por el parlante "
            f"({speaker._describir(dev)}), vol {v:g}%. No tengo motor vibrador: vibro con el parlante. "
            'Para cortar: {"cmd":"vibrar","on":false}')


def parar() -> str:
    global _fin
    if not activa():
        return "vibrar: no estaba vibrando"
    _fin = 0.0
    speaker.parar()
    return "vibrar: cortado"


def estado() -> str:
    if SIMULAR:
        return "vibrar: simulado (sin hardware)"
    return ("vibrar: " + ("vibrando ahora" if activa() else "quieto")
            + " · sin motor vibrador: uso el parlante (" + speaker._describir(speaker.actual()) + ") con un tono grave"
            + " · " + _ultima)
