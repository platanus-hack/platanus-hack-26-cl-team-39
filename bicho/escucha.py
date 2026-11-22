"""
Escucha por turnos: marcar con pitidos el inicio y el fin de lo que le dice la persona al bicho.

Cómo funciona de verdad (importante):
  - El Pi NO reconoce palabras: no tiene instalado ningún reconocedor de voz. oido.py corta el audio en
    frases y el cerebro (por el relé) las transcribe. Así que la palabra "bicho" la reconoce el cerebro,
    y cuando la oye le manda al bicho  {"cmd":"escucha","inicio":true}.
  - Con eso el bicho toca el pitido de INICIO (dos notas que suben) y abre el turno.
  - Mientras el turno está abierto, un hilo mira oido.estado() (el detector de voz del ReSpeaker): cuando
    la persona habló y después se queda callada un rato ("silencio", 0,9 s), toca el pitido de CIERRE
    (dos notas que bajan) y cierra el turno. Si nadie dice nada en "espera" segundos, o el turno pasa
    de "max" segundos, también cierra.
  - Con el turno cerrado, sensores publica escucha.abierta = false: el cerebro debe ignorar lo que se
    diga hasta volver a oír "bicho". (El filtro va en el cerebro: bichod.py y oido.py no se tocan.)

    escucha.abrir()      pitido de inicio y abre el turno (parte el hilo)
    escucha.cerrar()     cierra ahora, con pitido     ·  escucha.cortar()  cierra sin pitido
    escucha.pitido(x)    prueba un pitido: "inicio" o "fin"
    escucha.datos()      para sensores.py: solo copia variables

Los pitidos salen por la salida elegida en speaker.py (aplay en su hilo daemon, con timeout).
Nada corre al importar; el hilo vive solo mientras el turno está abierto. Con BICHO_SIMULAR=1 no suena nada.
"""
from __future__ import annotations

import os
import threading
import time

import oido
import salida
import speaker

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

AYUDA = (
    '{"cmd":"escucha"}  estado  ·  "inicio":true pitido de inicio y abre el turno (lo manda el cerebro cuando'
    ' oye "bicho")  ·  cuando la persona termina de hablar toca solo el pitido de cierre  ·  "fin":true cierra'
    ' ahora con pitido  ·  "on":true|false activa o desactiva el modo (false además corta el turno, sin pitido)'
    '  ·  "pitido":"inicio"|"fin" prueba un pitido  ·  "vol":1-100 fuerza de los pitidos  ·  "silencio":0.4-3'
    ' segundos callado que cierran  ·  "espera":2-20 segundos que espera a que empiecen a hablar  ·  "max":3-60'
    ' tope del turno. El volumen general del parlante es {"cmd":"speaker","volumen":100}'
)

PITIDOS = {
    "inicio": [(880.0, 0.11), (0.0, 0.03), (1320.0, 0.17)],  # sube: te escucho
    "fin": [(1320.0, 0.11), (0.0, 0.03), (880.0, 0.17)],  # baja: listo, cerré
}
SORDO = 0.9  # s después de lanzar el pitido de inicio en que no se mira la voz (el micrófono oye el pitido)

_cfg = {"vol": 100.0, "silencio": 0.9, "espera": 6.0, "max": 15.0}
_LIMITES = {"vol": (1.0, 100.0), "silencio": (0.4, 3.0), "espera": (2.0, 20.0), "max": (3.0, 60.0)}

_lock = threading.Lock()
_hilo: threading.Thread | None = None
_activo = True  # el modo "solo después de bicho" (lo consulta el cerebro)
_abierta = False
_pendiente: str | None = None  # pitido que el hilo tiene que tocar
_pedido_fin: str | None = None  # alguien pidió cerrar: motivo
_t_abierta = 0.0
_t_voz = 0.0
_sordo_hasta = 0.0
_hablo = False
_turnos = 0
_ultimo = "todavía no he abierto ningún turno"
_ultimo_pitido = ""


def _log(msg: str, lvl: str = "info") -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "escucha: " + msg})


def _tocar(cual: str) -> bool:
    """Lanza el pitido por speaker.py. Si el parlante está ocupado, insiste hasta 1,5 s. Corre en el hilo."""
    global _ultimo_pitido
    patron = PITIDOS[cual]
    ok = False
    try:
        for _ in range(15):
            if speaker._lanzar([(speaker.actual(), patron)], _cfg["vol"], callado=True):
                ok = True
                break
            time.sleep(0.1)
    except Exception as e:
        _ultimo_pitido = f"pitido de {cual}: falló ({type(e).__name__}: {e})"[:160]
        return False
    _ultimo_pitido = f"pitido de {cual}: " + ("mandado al parlante" if ok else "no sonó, el parlante estaba ocupado")
    return ok


def _correr() -> None:
    global _hilo, _abierta, _pendiente, _pedido_fin, _hablo, _t_voz, _sordo_hasta, _ultimo, _turnos
    yo = threading.current_thread()
    try:
        while True:
            with _lock:
                pit, _pendiente = _pendiente, None
                if pit is None and not _abierta:
                    _hilo = None
                    return
            if pit:
                _tocar(pit)
                if pit == "inicio":
                    with _lock:
                        ahora = time.monotonic()
                        _sordo_hasta = ahora + SORDO
                        _t_voz = ahora
                continue
            ahora = time.monotonic()
            motivo = None
            with _lock:
                if _abierta:
                    if _pedido_fin:
                        motivo = _pedido_fin
                    else:
                        if ahora >= _sordo_hasta:
                            o = oido.estado()
                            if o and o.get("voz"):
                                _hablo = True
                                _t_voz = ahora
                        if _hablo and ahora - _t_voz >= _cfg["silencio"]:
                            motivo = "terminó de hablar"
                        elif not _hablo and ahora - _t_abierta >= _cfg["espera"]:
                            motivo = "nadie habló"
                        elif ahora - _t_abierta >= _cfg["max"]:
                            motivo = "llegó al tope de tiempo"
                    if motivo:
                        _abierta = False
                        _pedido_fin = None
                        _pendiente = "fin"
                        _turnos += 1
                        _ultimo = (f"último turno ({time.strftime('%H:%M:%S')}): cerrado porque {motivo}, "
                                   f"duró {ahora - _t_abierta:.1f} s")
            if motivo:
                _log(f"fin de la comunicación ({motivo}); no tomo en cuenta nada hasta oír «bicho» de nuevo")
                continue
            time.sleep(0.05)
    except Exception as e:
        _log(f"el hilo falló: {type(e).__name__}: {e}", "error")
    finally:
        with _lock:
            if _hilo is yo:
                _hilo = None
                _abierta = False


def _asegurar_hilo() -> None:
    """Con _lock tomado."""
    global _hilo
    if _hilo is None:
        _hilo = threading.Thread(target=_correr, name="escucha", daemon=True)
        _hilo.start()


def abrir() -> str:
    global _abierta, _pendiente, _pedido_fin, _t_abierta, _t_voz, _sordo_hasta, _hablo
    if SIMULAR:
        return "escucha: simulada (sin hardware no hay pitidos ni micrófono)"
    with _lock:
        ahora = time.monotonic()
        ya = _abierta
        _abierta = True
        _pedido_fin = None
        _hablo = False
        _t_abierta = _t_voz = ahora
        _sordo_hasta = ahora + SORDO + 2.0  # se ajusta cuando el pitido sale de verdad
        _pendiente = "inicio"
        _asegurar_hilo()
    _log("inicio de la comunicación: te escucho")
    sin_oido = "" if oido.estado() else " (ojo: el micrófono no está dando datos; cerraré por tiempo)"
    return (("escucha: turno reiniciado" if ya else "escucha: turno abierto") + ", pitido de inicio; cierro con otro "
            f"pitido cuando lleves {_cfg['silencio']:g} s callado{sin_oido}")


def cerrar(motivo: str = "me pidieron cerrar") -> str:
    global _pedido_fin
    if SIMULAR:
        return "escucha: simulada"
    with _lock:
        if not _abierta:
            return "escucha: no había un turno abierto"
        _pedido_fin = motivo
    return "escucha: cierro el turno con su pitido"


def cortar() -> str:
    """Cierra sin pitido y deja que el hilo termine."""
    global _abierta, _pendiente, _pedido_fin, _ultimo
    with _lock:
        estaba = _abierta
        _abierta = False
        _pendiente = None
        _pedido_fin = None
        if estaba:
            _ultimo = f"último turno ({time.strftime('%H:%M:%S')}): cortado sin pitido"
    return "escucha: turno cortado" if estaba else "escucha: no había un turno abierto"


def pitido(cual) -> str:
    global _pendiente
    c = str(cual or "").strip().lower()
    if c in ("cierre", "termino", "término", "final"):
        c = "fin"
    if c not in PITIDOS:
        return 'escucha: "pitido" puede ser "inicio" o "fin"'
    if SIMULAR:
        return f"escucha: pitido de {c} simulado"
    with _lock:
        if _abierta:
            return "escucha: hay un turno abierto; prueba el pitido cuando cierre"
        _pendiente = c
        _asegurar_hilo()
    return f"escucha: toco el pitido de {c} (vol {_cfg['vol']:g}%) por {speaker._describir(speaker.actual())}"


def configurar(c: dict) -> list[str]:
    dicho = []
    for k, (lo, hi) in _LIMITES.items():
        if k in c:
            try:
                x = float(c.get(k))
                if x != x:
                    raise ValueError
            except (TypeError, ValueError):
                dicho.append(f"{k}: un número de {lo:g} a {hi:g}")
                continue
            _cfg[k] = max(lo, min(x, hi))
            dicho.append(f"{k} {_cfg[k]:g}")
    return dicho


def activar(si: bool) -> str:
    global _activo
    _activo = bool(si)
    if _activo:
        return 'escucha: modo activado (solo tomo en cuenta lo que venga después de "bicho")'
    cortar()
    return "escucha: modo desactivado (sin pitidos ni turnos)"


def abierta() -> bool:
    return _abierta


def datos() -> dict:
    """Para sensores.py: solo copia variables."""
    return {"activa": _activo, "abierta": _abierta, "turnos": _turnos}


def estado() -> str:
    if SIMULAR:
        return "escucha: simulada (sin hardware)"
    p = ["escucha: modo " + ("activado" if _activo else "desactivado")]
    if _abierta:
        seg = time.monotonic() - _t_abierta
        p.append(f"turno ABIERTO hace {seg:.1f} s (" + ("ya oí voz" if _hablo else "esperando que hablen") + ")")
    else:
        p.append('turno cerrado: espero a que digan "bicho"')
    p.append(f"pitidos vol {_cfg['vol']:g}% por {speaker._describir(speaker.actual())}")
    p.append(f"cierra con {_cfg['silencio']:g} s de silencio, espera {_cfg['espera']:g} s, tope {_cfg['max']:g} s")
    p.append(f"turnos: {_turnos}")
    p.append(_ultimo)
    if _ultimo_pitido:
        p.append(_ultimo_pitido)
    return " · ".join(p)


def manejar(c: dict) -> str:
    partes = configurar(c)
    if "on" in c:
        partes.append(activar(bool(c.get("on"))))
    if c.get("inicio"):
        if not _activo:
            partes.append('escucha: el modo está desactivado; actívalo con "on":true')
        else:
            partes.append(abrir())
    elif c.get("fin") or c.get("parar"):
        partes.append(cerrar())
    elif "pitido" in c:
        partes.append(pitido(c.get("pitido")))
    return " · ".join(partes) if partes else estado()
