"""
Salida del bicho: para que cualquier módulo le mande algo a la web sin tocar bichod.py.

    import salida
    salida.emitir({"t": "imagen", "nombre": "camara", "fmt": "jpeg", "b64": "..."})

bichod.py recoge lo emitido unas 20 veces por segundo y lo reparte a todos los que estén mirando
(la web directa y el relé). Sirve desde cualquier hilo. Tipos que la web ya entiende:

  {"t": "imagen", "nombre": "camara", "fmt": "jpeg", "b64": "..."}   una imagen; la web muestra la
      última de cada nombre en la sección Vista. Que pese menos de 300 KB y no más de 2 por segundo.
  {"t": "log", "lvl": "info", "msg": "..."}                            una línea en la consola.

Si nadie está mirando, hay_publico() devuelve False: conviene no gastar cámara ni red en ese caso.
"""
from __future__ import annotations

import queue

_cola: "queue.Queue[dict]" = queue.Queue(maxsize=16)
_publico = False


def emitir(mensaje: dict) -> bool:
    """Encola un mensaje para la web. Devuelve False si la cola está llena (se bota)."""
    try:
        _cola.put_nowait(mensaje)
        return True
    except queue.Full:
        return False


def hay_publico() -> bool:
    return _publico


def _recoger() -> list[dict]:  # lo usa bichod.py
    out = []
    while True:
        try:
            out.append(_cola.get_nowait())
        except queue.Empty:
            return out


def _marcar_publico(hay: bool) -> None:  # lo usa bichod.py
    global _publico
    _publico = hay
