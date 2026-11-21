"""
Expresar: el bicho muestra un estado de su idioma (lenguaje.json) con luz y sonido a la vez, igual que el
simulador de bicho·dev. La luz la dibuja anillo.py en los 12 LEDs del ReSpeaker; el sonido se sintetiza aquí
con las mismas notas que usa el simulador (web/src/sim/sonido.ts) y suena por la salida elegida en speaker.

    {"cmd":"expresar","estado":"contento"}     luz + sonido de un estado ("seg":N cuánto dura la luz)
    {"cmd":"expresar","escena":"perro"}        una escena completa: sus estados en orden, cada uno su tiempo
    {"cmd":"expresar","lista":true}            estados y escenas que conoce
    "sonido":false solo luz  ·  "luz":false solo sonido  ·  {"cmd":"expresar","on":false} corta todo

Notas (formato de lenguaje.json): onda sine | triangle | square | sawtooth | ruido, frecuencia f que se desliza
a f2 (exponencial), inicio t y duración d en segundos, vol, trémolo trem (Hz) y pasa bajos filtro → filtro2 (Hz).
El audio de cada estado se calcula una vez (numpy, ~0,1 s en el Pi 3) y queda guardado en memoria.
Nada corre al importar. Con BICHO_SIMULAR=1 no suena ni se prende nada.
"""
from __future__ import annotations

import io
import os
import threading
import time
import wave

import anillo
import salida
import speaker

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"
SR = 16000  # la frecuencia propia del ReSpeaker: así ALSA no tiene que convertir

_cache: dict[str, tuple[bytes, float]] = {}
_hilo: threading.Thread | None = None
_parar: threading.Event | None = None
_lock = threading.Lock()
_ahora = ""  # qué está expresando


def _log(lvl: str, msg: str) -> None:
    salida.emitir({"t": "log", "lvl": lvl, "msg": "expresar: " + msg})


# ── síntesis (la misma receta que web/src/sim/sonido.ts) ────────────────────


def _lowpass(x, f_ini: float, f_fin: float | None):
    """Pasa bajos de 2 polos (dos de 1 polo en serie) con corte que se desliza de forma exponencial."""
    import numpy as np

    n = len(x)
    if f_fin:
        fc = f_ini * (f_fin / f_ini) ** (np.arange(n) / max(1, n - 1))
    else:
        fc = np.full(n, float(f_ini))
    a = 1.0 - np.exp(-2 * np.pi * np.minimum(fc, SR * 0.45) / SR)
    y = np.empty(n)
    s1 = s2 = 0.0
    xs, al = x.tolist(), a.tolist()
    for i in range(n):
        s1 += al[i] * (xs[i] - s1)
        s2 += al[i] * (s1 - s2)
        y[i] = s2
    return y


def sintetizar(notas: list[dict]) -> tuple[bytes, float]:
    """WAV mono de 16 bits a 16 kHz y cuánto dura (s)."""
    import numpy as np

    largo = max((float(n.get("t", 0)) + float(n.get("d", 0)) for n in notas), default=0.0) + 0.12
    mezcla = np.zeros(int(SR * largo) + 1)
    rng = np.random.default_rng(7)
    for n in notas:
        ini, d = float(n.get("t", 0)), max(0.005, float(n.get("d", 0.1)))
        m = max(1, int(SR * d))
        t = np.arange(m) / SR
        onda = n.get("onda", "sine")
        if onda == "ruido":
            x = rng.uniform(-1, 1, m)
        else:
            f = float(n.get("f", 440))
            f2 = n.get("f2")
            frec = f * (float(f2) / f) ** (t / d) if f2 else np.full(m, f)
            fase = np.cumsum(frec) / SR  # en vueltas
            fr = fase % 1.0
            if onda == "square":
                x = np.where(fr < 0.5, 1.0, -1.0)
            elif onda == "sawtooth":
                x = 2 * fr - 1
            elif onda == "triangle":
                x = 1 - 4 * np.abs(fr - 0.5)
            else:
                x = np.sin(2 * np.pi * fase)
        if n.get("filtro"):
            x = _lowpass(x, float(n["filtro"]), float(n["filtro2"]) if n.get("filtro2") else None)
        if n.get("trem"):
            x = x * (0.5 + 0.5 * np.sin(2 * np.pi * float(n["trem"]) * t))
        vol = float(n.get("vol", 0.4)) * 0.8
        ataque, caida = min(0.012, d / 4), min(0.05, d / 3)
        env = np.minimum(1.0, np.minimum(t / max(ataque, 1e-4), (d - t) / max(caida, 1e-4))).clip(0, 1)
        a = int(SR * ini)
        mezcla[a : a + m] += x[: len(mezcla) - a] * env[: len(mezcla) - a] * vol
    mezcla *= 0.7
    mezcla = np.tanh(mezcla * 1.2) / np.tanh(1.2)  # como el compresor del navegador: nada se pasa de 1
    pico = float(np.abs(mezcla).max())
    if pico > 0:  # el parlante del bicho es chico: cada sonido se lleva al 90 % de la escala
        mezcla *= 0.9 / pico
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mezcla * 32000).astype("<i2").tobytes())
    return buf.getvalue(), largo


def _sonido_de(estado: str) -> tuple[bytes, float] | None:
    if estado not in _cache:
        e = _estado(estado)
        notas = (e or {}).get("sonido") or []
        if not notas:
            return None
        _cache[estado] = sintetizar(notas)
    return _cache[estado]


# ── idioma ───────────────────────────────────────────────────────────────────


def _estado(eid: str) -> dict | None:
    d = anillo._lenguaje_json()
    for e in [d.get("reposo", {})] + list(d.get("estados", [])):
        if e.get("id") == eid:
            return e
    return None


def _escena(eid: str) -> dict | None:
    for e in anillo._lenguaje_json().get("escenas", []):
        if e.get("id") == eid:
            return e
    return None


def lista() -> str:
    d = anillo._lenguaje_json()
    es = [e["id"] for e in [d.get("reposo", {})] + list(d.get("estados", [])) if e.get("id")]
    sc = [f"{e['id']} ({e.get('nombre', '')}: {' → '.join(p[0] for p in e.get('pasos', []))})" for e in d.get("escenas", [])]
    return "expresar: estados → " + ", ".join(es) + " · escenas → " + " · ".join(sc)


# ── mostrar ──────────────────────────────────────────────────────────────────


def _sonar(estado: str) -> str:
    s = _sonido_de(estado)
    if s is None:
        return "sin sonido"
    data, dura = s
    for _ in range(3):  # si algo estaba sonando, se corta: manda lo último que se expresa
        if speaker.tocar_wav(data, dura):
            return "con sonido"
        speaker.parar()
        time.sleep(0.12)
    return "sin sonido (el parlante estaba ocupado)"


def _mostrar(estado: str, seg: float | None, luz: bool, sonido: bool) -> str:
    partes = []
    if luz:
        c = {"estado": estado}
        if seg is not None:
            c["seg"] = seg
        anillo.mostrar_patron(c, estado)
        partes.append("con luz")
    if sonido:
        partes.append(_sonar(estado))
    return " y ".join(partes)


def _correr_escena(parar: threading.Event, esc: dict, luz: bool, sonido: bool) -> None:
    global _ahora
    try:
        pasos = esc.get("pasos", [])
        for i, (eid, dura) in enumerate(pasos):
            if parar.is_set():
                return
            _ahora = f"escena {esc['id']}: {eid} ({i + 1}/{len(pasos)})"
            # la luz dura un poco más que el paso, para que el siguiente la reemplace sin quedar a oscuras;
            # la del último paso se apaga sola (y vuelve a seguir la voz si estaba en eso)
            _mostrar(eid, float(dura) + (0.4 if i < len(pasos) - 1 else 0), luz, sonido)
            if parar.wait(float(dura)):
                return
        _log("info", f"terminé la escena {esc['id']}")
    except Exception as e:
        _log("error", f"la escena falló: {type(e).__name__}: {e}")
    finally:
        _ahora = ""


def _detener() -> None:
    global _hilo, _parar
    if _parar is not None:
        _parar.set()
    h = _hilo
    _hilo, _parar = None, None
    if h is not None and h.is_alive():
        h.join(0.3)


def manejar(c: dict) -> str:
    global _hilo, _parar, _ahora
    if c.get("lista") or c.get("estados"):
        return lista()
    luz = c.get("luz", True) is not False
    sonido = c.get("sonido", True) is not False
    if ("on" in c and not c.get("on")) or c.get("parar"):
        with _lock:
            _detener()
        speaker.parar()
        anillo.apagar()
        return "expresar: corté todo"
    if "escena" in c:
        esc = _escena(str(c.get("escena")).strip())
        if esc is None:
            return 'expresar: no conozco esa escena (lista: {"cmd":"expresar","lista":true})'
        if SIMULAR:
            return f"expresar: escena {esc['id']} (simulada)"
        with _lock:
            _detener()
            _parar = threading.Event()
            _hilo = threading.Thread(target=_correr_escena, args=(_parar, esc, luz, sonido), daemon=True, name="expresar")
            _hilo.start()
        total = sum(float(p[1]) for p in esc.get("pasos", []))
        return f"expresar: escena «{esc.get('nombre', esc['id'])}» ({total:g} s): " + " → ".join(p[0] for p in esc.get("pasos", []))
    if "estado" in c:
        eid = str(c.get("estado")).strip()
        e = _estado(eid)
        if e is None:
            return 'expresar: no conozco ese estado (lista: {"cmd":"expresar","lista":true})'
        if SIMULAR:
            return f"expresar: {eid} (simulado)"
        with _lock:
            _detener()
        seg = None
        if "seg" in c:
            try:
                seg = max(0.2, min(float(c.get("seg")), 3600.0))
            except (TypeError, ValueError):
                seg = None
        como = _mostrar(eid, seg, luz, sonido)
        return f"expresar: {e.get('nombre', eid)} ({eid}) {como}" + (f" · en la app: {e['app']}" if e.get("app") else "")
    return "expresar: " + (_ahora or "tranquilo") + " · " + anillo.estado()
