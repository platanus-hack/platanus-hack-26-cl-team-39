"""
ReSpeaker XVF3800: leer la documentación de Seeed (wiki) y hablar con el chip del micrófono por USB.

Comando wiki (documentación, solo lectura, SOLO https://wiki.seeedstudio.com):
  {"cmd":"wiki","url":"respeaker_xvf3800_introduction/"}  baja esa página y la deja en memoria
  {"cmd":"wiki"}                    estado  ·  "pag":2 un trozo ("largo")  ·  "q":"DOA" busca  ·  "links":"xvf"

Comando mic (parámetros del chip, tabla sacada de wiki.seeedstudio.com/respeaker_xvf_3800_i2c_list/):
  {"cmd":"mic"}                               resumen: versión, dirección y voz, haces, energía, AGC, ruido
  {"cmd":"mic","lista":"agc"}                 qué parámetros conozco (filtra por texto)
  {"cmd":"mic","leer":"PP_AGCGAIN"}           lee uno (o una lista de hasta 8)
  {"cmd":"mic","poner":"PP_MIN_NS","valor":0.2}  cambia uno de los parámetros de ajuste permitidos
  {"cmd":"mic","on":true}                     mide 5 veces por segundo la energía de voz y los haces (gráficos
                                              respeaker.*)  ·  "on":false lo apaga

Cómo se habla con el chip (lo que dice la wiki): transferencia de control USB de tipo vendor al dispositivo
2886:001a con wValue = cmd (| 0x80 para leer) y wIndex = resid. Al leer llega un byte de estado antes de los
datos (0 = listo, 64 = reintentar). Los enteros y floats van en little-endian.

Comprobado en este bicho (firmware 2.0.6): el estado 65 aparece cuando el firmware no tiene ese parámetro
(por ejemplo AIC3104_HP_LEVEL), y AEC_RT60 no entrega un valor útil.

Cuidados: lo que se cambia con "poner" NO se guarda en la flash del chip (no se usa SAVE_CONFIGURATION): se
pierde cuando el chip se reinicia. No se exponen REBOOT, SAVE/CLEAR_CONFIGURATION, pruebas (TEST_*), GPO ni
el ruteo de canales, que podrían dejar mudo al oído. Los LEDs los maneja oido_luz.py.
Nada corre al importar; lo que toca el USB o la red va en hilos daemon. Con BICHO_SIMULAR=1 no se toca nada.
"""
from __future__ import annotations

import math
import os
import re
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SIMULAR = os.environ.get("BICHO_SIMULAR") == "1"

COMANDOS = ("wiki", "mic")
AYUDA = {
    "wiki": '{"cmd":"wiki"}  estado  ·  "url":"respeaker_xvf3800_introduction/" baja una página de wiki.seeedstudio.com'
    ' (solo ese sitio)  ·  "pag":2 muestra un trozo  ·  "q":"DOA" busca en la página  ·  "links":"xvf" enlaces',
    "mic": '{"cmd":"mic"}  resumen del chip del micrófono (XVF3800): versión, dirección, haces, energía de voz, AGC,'
    ' ruido  ·  "lista":"agc" parámetros que conozco  ·  "leer":"PP_AGCGAIN" lee uno  ·  "poner":"PP_MIN_NS",'
    '"valor":0.2 ajusta uno permitido (no queda guardado en el chip)  ·  "on":true grafica energía de voz y haces'
    '  ·  "on":false',
}

# ══ wiki ══════════════════════════════════════════════════════════════════════

HOST = "wiki.seeedstudio.com"
_MAX_BYTES = 2_500_000
_MAX_SEG = 40.0
_MAX_PAGINAS = 6

_lock = threading.Lock()
_paginas: dict[str, dict] = {}  # url -> {"lineas": [...], "texto": str, "links": [(href, texto)], "t": float}
_errores: dict[str, str] = {}
_bajando: str | None = None
_actual: str | None = None


def _normalizar(url) -> str | None:
    """Devuelve la URL limpia si es de la wiki de Seeed por https; si no, None."""
    u = str(url or "").strip()
    if not u or len(u) > 300:
        return None
    if "://" not in u:
        u = f"https://{HOST}/" + u.lstrip("/")
    try:
        p = urllib.parse.urlsplit(u)
        if p.scheme != "https" or p.hostname != HOST or p.port not in (None, 443) or p.username or p.password:
            return None
    except ValueError:
        return None
    ruta = urllib.parse.quote(urllib.parse.unquote(p.path or "/"), safe="/-_.~")
    return f"https://{HOST}{ruta}"


class _SoloSeeed(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _normalizar(newurl) is None:
            raise urllib.error.HTTPError(newurl, code, "redirige fuera de la wiki de Seeed", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _Texto(HTMLParser):
    _SALTAR = {"script", "style", "nav", "footer", "svg", "noscript", "aside", "button"}
    _BLOQUE = {"p", "div", "li", "br", "tr", "pre", "table", "ul", "ol", "section", "article", "header"}
    _TITULO = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.todo: list[str] = []
        self.articulo: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._salto = 0
        self._art = 0
        self._a: list | None = None

    def _poner(self, s: str) -> None:
        if self._salto:
            return
        self.todo.append(s)
        if self._art:
            self.articulo.append(s)

    def handle_starttag(self, tag, attrs):
        if tag in self._SALTAR:
            self._salto += 1
        elif tag == "article":
            self._art += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            self._a = [href, []]
        if tag in self._TITULO:
            self._poner("\n## ")
        elif tag in self._BLOQUE:
            self._poner("\n")
        elif tag in ("td", "th"):
            self._poner(" | ")

    def handle_endtag(self, tag):
        if tag in self._SALTAR and self._salto:
            self._salto -= 1
        elif tag == "article" and self._art:
            self._art -= 1
        if tag == "a" and self._a is not None:
            href, partes = self._a
            self._a = None
            txt = " ".join("".join(partes).split())[:80]
            if href and not href.startswith("#") and len(self.links) < 3000:
                self.links.append((href[:200], txt))
        if tag in self._TITULO or tag in self._BLOQUE:
            self._poner("\n")

    def handle_data(self, data):
        if self._a is not None:
            self._a[1].append(data)
        self._poner(data)


def _limpiar(trozos: list[str]) -> list[str]:
    out: list[str] = []
    for linea in "".join(trozos).split("\n"):
        l = re.sub(r"[ \t\u00a0\u200b]+", " ", linea).strip()
        if l or (out and out[-1]):
            out.append(l[:600])
    while out and not out[-1]:
        out.pop()
    return out


def _bajar(url: str) -> None:
    global _bajando, _actual
    try:
        abridor = urllib.request.build_opener(_SoloSeeed())
        req = urllib.request.Request(url, headers={"User-Agent": "bicho/1 (Raspberry Pi; lee documentacion)", "Accept": "text/html"})
        limite = time.monotonic() + _MAX_SEG
        trozos, total = [], 0
        with abridor.open(req, timeout=15) as r:
            if _normalizar(r.geturl()) is None:
                raise ValueError("la página terminó fuera de la wiki de Seeed")
            while True:
                b = r.read(65536)
                if not b:
                    break
                trozos.append(b)
                total += len(b)
                if total > _MAX_BYTES:
                    raise ValueError("la página es demasiado grande")
                if time.monotonic() > limite:
                    raise TimeoutError("la descarga tardó demasiado")
        html = b"".join(trozos).decode("utf-8", errors="replace")
        p = _Texto()
        p.feed(html)
        p.close()
        lineas = _limpiar(p.articulo)
        if sum(len(l) for l in lineas) < 200:
            lineas = _limpiar(p.todo)
        vistos, links = set(), []
        for href, txt in p.links:
            if href not in vistos:
                vistos.add(href)
                links.append((href, txt))
        with _lock:
            _paginas[url] = {"lineas": lineas, "texto": "\n".join(lineas), "links": links, "t": time.time(), "bytes": total}
            while len(_paginas) > _MAX_PAGINAS:
                _paginas.pop(next(iter(_paginas)))
            _errores.pop(url, None)
            _actual = url
    except Exception as e:
        with _lock:
            _errores[url] = f"{type(e).__name__}: {e}"[:200]
    finally:
        _bajando = None


def _entero(v, defecto: int, lo: int, hi: int) -> int:
    try:
        x = int(float(v))
    except (TypeError, ValueError, OverflowError):
        x = defecto
    return max(lo, min(x, hi))


def _estado_wiki() -> str:
    partes = []
    if _bajando:
        partes.append(f"bajando {_bajando}…")
    with _lock:
        for u, p in _paginas.items():
            marca = " (actual)" if u == _actual else ""
            partes.append(f"{u}{marca}: {len(p['texto'])} letras, {len(p['links'])} enlaces")
        for u, e in _errores.items():
            partes.append(f"{u}: falló ({e})")
    return "wiki: " + (" · ".join(partes) if partes else 'nada bajado. Usa "url":"respeaker_xvf3800_introduction/"')


def _wiki(c: dict) -> str:
    global _bajando, _actual
    if SIMULAR:
        return "wiki: simulado, no salgo a la red"
    if "url" in c:
        url = _normalizar(c.get("url"))
        if url is None:
            return f"wiki: solo leo páginas de https://{HOST}/"
        with _lock:
            tengo = url in _paginas and not c.get("de_nuevo")
            if tengo:
                _actual = url
            elif _bajando:
                return f"wiki: todavía estoy bajando {_bajando}; espera un momento"
            else:
                _bajando = url
                _errores.pop(url, None)
        if not tengo:
            threading.Thread(target=_bajar, args=(url,), daemon=True, name="wiki").start()
            return f'wiki: bajando {url}… pregunta de nuevo con {{"cmd":"wiki"}}'
    with _lock:
        p = _paginas.get(_actual) if _actual else None
        url = _actual
    if "links" in c:
        if p is None:
            return _estado_wiki()
        f = str(c.get("links") or "").strip().lower()[:60]
        hallados = [f"{h} [{t}]" if t else h for h, t in p["links"] if f in h.lower() or f in t.lower()]
        tope = _entero(c.get("max"), 60, 1, 200)
        txt = f"wiki: {len(hallados)} enlaces" + (f' con "{f}"' if f else "") + ":\n" + "\n".join(hallados[:tope])
        return txt[:9000]
    if "q" in c:
        if p is None:
            return _estado_wiki()
        q = str(c.get("q") or "").strip().lower()[:80]
        if len(q) < 2:
            return "wiki: dime qué buscar (mínimo 2 letras)"
        ctx = _entero(c.get("ctx"), 1, 0, 30)
        tope = _entero(c.get("max"), 10, 1, 40)
        lineas = p["lineas"]
        idx = [i for i, l in enumerate(lineas) if q in l.lower()]
        out, ultimo = [], -1
        for i in idx[:tope]:
            a, b = max(i - ctx, ultimo + 1), min(i + ctx + 1, len(lineas))
            if a >= b:
                continue
            out.append("\n".join(f"{j + 1}: {lineas[j][:300]}" for j in range(a, b)))
            ultimo = b - 1
        return (f'wiki "{q}": {len(idx)} líneas de {len(lineas)} en {url}\n' + "\n--\n".join(out))[:9000]
    if "pag" in c or "linea" in c or "url" in c:
        if p is None:
            return _estado_wiki()
        largo = _entero(c.get("largo"), 2800, 200, 9000)
        if "linea" in c:  # desde una línea (las que muestra "q")
            n0 = _entero(c.get("linea"), 1, 1, max(1, len(p["lineas"])))
            trozo = "\n".join(p["lineas"][n0 - 1 :])[:largo]
            return f"wiki {url} desde la línea {n0} de {len(p['lineas'])}:\n{trozo}"
        texto = p["texto"]
        total = max(1, -(-len(texto) // largo))
        n = _entero(c.get("pag"), 1, 1, total)
        return f"wiki {url} trozo {n}/{total}:\n" + texto[(n - 1) * largo : n * largo]
    return _estado_wiki()


# ══ chip XVF3800 por USB ══════════════════════════════════════════════════════

VID, PID = 0x2886, 0x001A
T_USB = 300  # ms por transferencia
_REINTENTAR = 64  # byte de estado: el chip pide volver a preguntar
_FMT = {"uint8": "B", "char": "B", "uint16": "H", "uint32": "I", "int32": "i", "float": "f", "radians": "f"}

# nombre: (resid, cmd, cantidad, tipo, "ro"|"rw", descripción). Solo lo que se puede leer sin riesgo.
PARAMS: dict[str, tuple[int, int, int, str, str, str]] = {
    # resid 48: sistema
    "VERSION": (48, 0, 3, "uint8", "ro", "versión del firmware"),
    "BLD_MSG": (48, 1, 50, "char", "ro", "configuración con que se compiló"),
    "BLD_REPO_HASH": (48, 3, 40, "char", "ro", "hash de git del firmware"),
    "BOOT_STATUS": (48, 5, 3, "char", "ro", "modo de arranque"),
    "USB_BIT_DEPTH": (48, 8, 2, "uint8", "ro", "bits del audio USB (16/24/32)"),
    "AIC3104_HP_LEVEL": (48, 11, 1, "uint8", "rw", "nivel de la salida de audífonos [0..9]"),
    "AIC3104_LINEOUT_LEVEL": (48, 12, 1, "uint8", "rw", "nivel de la salida de línea [0..9]"),
    # resid 20: GPO, LEDs y dirección
    "GPO_READ_VALUES": (20, 0, 5, "uint8", "ro", "niveles de los 5 pines de salida"),
    "LED_EFFECT": (20, 12, 1, "uint8", "ro", "efecto LED (0 apagado, 1 respira, 2 arcoíris, 3 fijo, 4 DOA, 5 anillo)"),
    "LED_BRIGHTNESS": (20, 13, 1, "uint8", "ro", "brillo de los LEDs"),
    "LED_GAMMIFY": (20, 14, 1, "uint8", "ro", "corrección gamma de los LEDs"),
    "LED_SPEED": (20, 15, 1, "uint8", "ro", "velocidad del efecto LED"),
    "LED_COLOR": (20, 16, 1, "uint32", "ro", "color de los LEDs (RGB)"),
    "LED_DOA_COLOR": (20, 17, 2, "uint32", "ro", "colores del modo DOA (fondo, dirección)"),
    "DOA_VALUE": (20, 18, 2, "uint16", "ro", "ángulo de la voz 0-359 y 1 si hay voz"),
    "LED_RING_COLOR": (20, 19, 12, "uint32", "ro", "color de cada LED en modo anillo"),
    # resid 33: AEC y haces
    "AEC_AECPATHCHANGE": (33, 0, 1, "int32", "ro", "cambió el camino del eco"),
    "AEC_HPFONOFF": (33, 1, 1, "int32", "rw", "pasa-altos (0 no, 1=70 Hz, 2=125, 3=150, 4=180)"),
    "AEC_AECSILENCELEVEL": (33, 2, 2, "float", "ro", "umbral de silencio"),
    "AEC_AECCONVERGED": (33, 3, 1, "int32", "ro", "el cancelador de eco convergió"),
    "AEC_AECEMPHASISONOFF": (33, 4, 1, "int32", "ro", "pre/de-énfasis"),
    "AEC_FAR_EXTGAIN": (33, 5, 1, "float", "ro", "ganancia externa del parlante (dB)"),
    "AEC_RT60": (33, 9, 1, "float", "ro", "reverberación estimada de la pieza (s)"),
    "AEC_ASROUTONOFF": (33, 35, 1, "int32", "rw", "salida para reconocimiento de voz (0 residual, 1 procesada)"),
    "AEC_ASROUTGAIN": (33, 36, 1, "float", "rw", "ganancia de la salida para reconocimiento [0..1000]"),
    "AEC_FIXEDBEAMSONOFF": (33, 37, 1, "int32", "ro", "haces fijos (0,1)"),
    "AEC_FIXEDBEAMNOISETHR": (33, 38, 2, "float", "ro", "umbral de ruido de los haces fijos"),
    "SHF_BYPASS": (33, 70, 1, "uint8", "ro", "AEC en bypass"),
    "AEC_NUM_MICS": (33, 71, 1, "int32", "ro", "cantidad de micrófonos"),
    "AEC_NUM_FARENDS": (33, 72, 1, "int32", "ro", "cantidad de referencias de parlante"),
    "AEC_MIC_ARRAY_TYPE": (33, 73, 1, "int32", "ro", "tipo de arreglo (1 lineal, 2 cuadrado)"),
    "AEC_MIC_ARRAY_GEO": (33, 74, 12, "float", "ro", "posición x,y,z de cada micrófono (m)"),
    "AEC_AZIMUTH_VALUES": (33, 75, 4, "radians", "ro", "azimut de los haces (haz 1, haz 2, libre, automático)"),
    "AEC_SPENERGY_VALUES": (33, 80, 4, "float", "ro", "energía de voz por haz (haz 1, haz 2, libre, automático)"),
    "AEC_FIXEDBEAMSAZIMUTH_VALUES": (33, 81, 2, "radians", "ro", "azimut de los haces fijos"),
    "AEC_FIXEDBEAMSELEVATION_VALUES": (33, 82, 2, "radians", "ro", "elevación de los haces fijos"),
    "AEC_FIXEDBEAMSGATING": (33, 83, 1, "uint8", "ro", "compuerta de los haces fijos"),
    # resid 35: audio
    "AUDIO_MGR_MIC_GAIN": (35, 0, 1, "float", "ro", "ganancia de los micrófonos"),
    "AUDIO_MGR_REF_GAIN": (35, 1, 1, "float", "ro", "ganancia de la referencia"),
    "AUDIO_MGR_SELECTED_AZIMUTHS": (35, 11, 2, "radians", "ro", "azimut elegido (procesado, automático)"),
    "AUDIO_MGR_SELECTED_CHANNELS": (35, 12, 2, "uint8", "ro", "canales de salida elegidos"),
    "AUDIO_MGR_OP_L": (35, 15, 2, "uint8", "ro", "qué sale por el canal izquierdo (categoría, fuente)"),
    "AUDIO_MGR_OP_R": (35, 19, 2, "uint8", "ro", "qué sale por el canal derecho (categoría, fuente)"),
    "AUDIO_MGR_SYS_DELAY": (35, 26, 1, "int32", "ro", "retardo de la referencia (muestras)"),
    # resid 17: post-proceso (AGC, ruido, eco)
    "PP_AGCONOFF": (17, 10, 1, "int32", "rw", "control automático de ganancia (0,1)"),
    "PP_AGCMAXGAIN": (17, 11, 1, "float", "rw", "ganancia máxima del AGC [1..1000]"),
    "PP_AGCDESIREDLEVEL": (17, 12, 1, "float", "rw", "potencia objetivo del AGC [1e-8..1]"),
    "PP_AGCGAIN": (17, 13, 1, "float", "ro", "ganancia actual del AGC"),
    "PP_AGCTIME": (17, 14, 1, "float", "rw", "constante de tiempo del AGC [0.5..4] s"),
    "PP_AGCFASTTIME": (17, 15, 1, "float", "rw", "bajada rápida del AGC [0.05..4] s"),
    "PP_LIMITONOFF": (17, 19, 1, "int32", "rw", "limitador (0,1)"),
    "PP_LIMITPLIMIT": (17, 20, 1, "float", "ro", "potencia máxima del limitador"),
    "PP_MIN_NS": (17, 21, 1, "float", "rw", "piso de ganancia para ruido constante [0..1] (menos = más supresión)"),
    "PP_MIN_NN": (17, 22, 1, "float", "rw", "piso de ganancia para ruido cambiante [0..1] (menos = más supresión)"),
    "PP_ECHOONOFF": (17, 23, 1, "int32", "rw", "supresión de eco (0,1)"),
    "PP_GAMMA_E": (17, 24, 1, "float", "ro", "sobre-resta de eco"),
    "PP_GAMMA_ETAIL": (17, 25, 1, "float", "ro", "sobre-resta de cola de eco"),
    "PP_GAMMA_ENL": (17, 26, 1, "float", "ro", "sobre-resta de eco no lineal"),
    "PP_NLATTENONOFF": (17, 27, 1, "int32", "ro", "atenuación de eco no lineal"),
    "PP_MGSCALE": (17, 29, 3, "float", "ro", "escala de ganancia mínima (máx, mín, actual)"),
    "PP_DTSENSITIVE": (17, 31, 1, "int32", "ro", "sensibilidad al habla simultánea"),
    "PP_ATTNS_MODE": (17, 32, 1, "int32", "rw", "atenuación extra cuando no hay voz (0,1)"),
    "PP_ATTNS_NOMINAL": (17, 33, 1, "float", "rw", "atenuación nominal sin voz [0..1]"),
    "PP_ATTNS_SLOPE": (17, 34, 1, "float", "rw", "pendiente de esa atenuación [0..5]"),
}

# Lo único que se deja cambiar, con el rango que publica la wiki.
RANGOS: dict[str, tuple[float, float]] = {
    "AIC3104_HP_LEVEL": (0, 9), "AIC3104_LINEOUT_LEVEL": (0, 9),
    "AEC_HPFONOFF": (0, 4), "AEC_ASROUTONOFF": (0, 1), "AEC_ASROUTGAIN": (0.0, 1000.0),
    "PP_AGCONOFF": (0, 1), "PP_AGCMAXGAIN": (1.0, 1000.0), "PP_AGCDESIREDLEVEL": (1e-8, 1.0),
    "PP_AGCTIME": (0.5, 4.0), "PP_AGCFASTTIME": (0.05, 4.0), "PP_LIMITONOFF": (0, 1),
    "PP_MIN_NS": (0.0, 1.0), "PP_MIN_NN": (0.0, 1.0), "PP_ECHOONOFF": (0, 1),
    "PP_ATTNS_MODE": (0, 1), "PP_ATTNS_NOMINAL": (0.0, 1.0), "PP_ATTNS_SLOPE": (0.0, 5.0),
}

_usb = threading.Lock()  # una operación de este módulo a la vez
_mon_hilo: threading.Thread | None = None
_mon_parar: threading.Event | None = None
_mon_datos: dict | None = None
_mon_error = ""
_mon_lock = threading.Lock()
_sim_on = False


def _buscar_dev():
    import usb.core

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        raise RuntimeError("no encuentro el ReSpeaker en el USB")
    return dev


def _soltar(dev) -> None:
    if dev is None:
        return
    try:
        import usb.util

        usb.util.dispose_resources(dev)
    except Exception:
        pass


def _usb_leer(dev, nombre: str) -> list:
    import usb.util

    resid, cmd, n, tipo, _modo, _desc = PARAMS[nombre]
    f = _FMT[tipo]
    largo = struct.calcsize("<" + f) * n
    pedir = usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    estado = None
    for _ in range(8):
        r = bytes(dev.ctrl_transfer(pedir, 0, 0x80 | cmd, resid, largo + 1, T_USB))
        if len(r) >= largo + 1 and r[0] == 0:
            return list(struct.unpack(f"<{n}{f}", r[1 : 1 + largo]))
        estado = r[0] if r else None
        if estado != _REINTENTAR:  # cualquier otro estado: este firmware no tiene el parámetro
            raise RuntimeError(f"este firmware no entrega {nombre} (estado {estado})")
        time.sleep(0.01)
    raise RuntimeError(f"el chip no entregó {nombre} (pidió reintentar demasiadas veces)")


def _usb_escribir(dev, nombre: str, valores: list) -> None:
    import usb.util

    resid, cmd, n, tipo, _modo, _desc = PARAMS[nombre]
    datos = struct.pack(f"<{n}{_FMT[tipo]}", *valores)
    mandar = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    dev.ctrl_transfer(mandar, 0, cmd, resid, datos, T_USB)


def _g(x: float) -> str:
    return f"{x:.4g}" if math.isfinite(x) else "?"


def _grados(rad: float) -> float | None:
    return round(math.degrees(rad) % 360, 1) if math.isfinite(rad) else None


def _mostrar(nombre: str, v: list) -> str:
    tipo = PARAMS[nombre][3]
    if tipo == "char":
        return bytes(v).split(b"\x00")[0].decode("ascii", errors="replace").strip() or "(vacío)"
    if tipo == "radians":
        return " ".join("?" if _grados(x) is None else f"{_grados(x):g}°" for x in v)
    if tipo == "float":
        return " ".join(_g(x) for x in v)
    if nombre in ("LED_COLOR", "LED_DOA_COLOR", "LED_RING_COLOR"):
        return " ".join(f"{x:06x}" for x in v)
    return " ".join(str(x) for x in v)


def _con_chip(fn, espera: float = 1.3) -> str:
    """Corre fn(dev) en un hilo daemon y espera poco: manejar() no se queda pegado si el USB no contesta."""
    if SIMULAR:
        return "mic: simulado, no toco el USB"
    try:
        import usb.core  # noqa: F401
    except ImportError:
        return "mic: falta pyusb (python3-usb)"
    out: list[str] = []

    def tarea() -> None:
        if not _usb.acquire(timeout=1.0):
            out.append("mic: el USB del micrófono está ocupado; prueba de nuevo")
            return
        dev = None
        try:
            dev = _buscar_dev()
            out.append(fn(dev))
        except Exception as e:
            out.append(f"mic: falló: {type(e).__name__}: {e}")
        finally:
            _soltar(dev)
            _usb.release()

    h = threading.Thread(target=tarea, daemon=True, name="mic-usb")
    h.start()
    h.join(espera)
    return out[0] if out else "mic: el chip no contestó a tiempo; prueba de nuevo"


def _resumen(dev) -> str:
    def leer(nombre):
        try:
            return _usb_leer(dev, nombre)
        except Exception:
            return None

    partes = []
    v = leer("VERSION")
    partes.append("firmware " + (".".join(str(x) for x in v) if v else "?"))
    v = leer("DOA_VALUE")
    if v:
        partes.append(f"voz desde {v[0]}° ({'hablando' if v[1] else 'en silencio'})")
    az, en = leer("AEC_AZIMUTH_VALUES"), leer("AEC_SPENERGY_VALUES")
    if az:
        partes.append("haces (1, 2, libre, auto): " + _mostrar("AEC_AZIMUTH_VALUES", az))
    if en:
        partes.append("energía de voz por haz: " + " ".join(_g(x) for x in en))
    v = leer("AEC_NUM_MICS")
    if v:
        partes.append(f"{v[0]} micrófonos")
    agc, gan, tope = leer("PP_AGCONOFF"), leer("PP_AGCGAIN"), leer("PP_AGCMAXGAIN")
    if agc:
        txt = f"AGC {'prendido' if agc[0] else 'apagado'}"
        if gan:
            txt += f", ganancia {_g(gan[0])}"
        if tope:
            txt += f" (máx {_g(tope[0])})"
        partes.append(txt)
    v = leer("AUDIO_MGR_MIC_GAIN")
    if v:
        partes.append(f"ganancia de micrófonos {_g(v[0])}")
    ns, nn = leer("PP_MIN_NS"), leer("PP_MIN_NN")
    if ns and nn:
        partes.append(f"piso de supresión de ruido: constante {_g(ns[0])}, cambiante {_g(nn[0])}")
    v = leer("AEC_HPFONOFF")
    if v:
        partes.append(f"pasa-altos {v[0]}")
    v = leer("AEC_RT60")
    if v and math.isfinite(v[0]) and 0.05 <= v[0] <= 5:  # fuera de eso el firmware no está estimando nada
        partes.append(f"reverberación de la pieza {_g(v[0])} s")
    v = leer("GPO_READ_VALUES")
    if v:
        # La wiki nombra 5 pines (X0D11, X0D30 mute, X0D31 amplificador, X0D33 LEDs, X0D39) pero no dice en qué
        # orden los entrega este comando: se muestran crudos, sin interpretar.
        partes.append("pines de salida (crudo, orden sin confirmar): " + " ".join(str(x) for x in v))
    v = leer("LED_EFFECT")
    if v:
        partes.append(f"efecto LED {v[0]}")
    if len(partes) <= 1 and partes[0].endswith("?"):
        return "mic: el chip no contestó ningún parámetro"
    return "mic (XVF3800): " + " · ".join(partes) + f" · monitor {'prendido' if activa() else 'apagado'}"


def _lista(filtro) -> str:
    f = "" if filtro is True else str(filtro or "").strip().lower()[:40]
    filas = []
    for nombre, (_r, _c, n, tipo, _modo, desc) in PARAMS.items():
        if f and f not in nombre.lower() and f not in desc.lower():
            continue
        marca = " [se puede poner]" if nombre in RANGOS else ""
        filas.append(f"{nombre} ({n} {tipo}){marca}: {desc}")
    if not filas:
        return f'mic: no conozco parámetros con "{f}"'
    if not f and len(filas) > 30:
        return (
            f"mic: conozco {len(filas)} parámetros; filtra con \"lista\":\"agc\", \"aec\", \"led\", \"pp_\", \"audio\"…"
            " Se pueden poner: " + ", ".join(RANGOS)
        )
    return ("mic: " + "\n".join(filas))[:6000]


def _leer_cmd(que) -> str:
    nombres = que if isinstance(que, list) else [que]
    nombres = [str(n).strip().upper() for n in nombres][:8]
    malos = [n for n in nombres if n not in PARAMS]
    if malos or not nombres:
        return f'mic: no conozco {", ".join(m[:40] for m in malos) or "ese parámetro"}; mira "lista":true'

    def fn(dev) -> str:
        out = []
        for n in nombres:
            try:
                out.append(f"{n} = {_mostrar(n, _usb_leer(dev, n))}")
            except Exception as e:
                out.append(f"{n}: no ({type(e).__name__}: {e})")
        return "mic: " + " · ".join(out)

    return _con_chip(fn)


def _poner_cmd(que, valor) -> str:
    nombre = str(que or "").strip().upper()
    if nombre not in PARAMS:
        return 'mic: no conozco ese parámetro; mira "lista":true'
    if nombre not in RANGOS:
        return f"mic: {nombre} no se cambia desde aquí. Se pueden poner: " + ", ".join(RANGOS)
    _r, _c, n, tipo, _modo, desc = PARAMS[nombre]
    lo, hi = RANGOS[nombre]
    crudos = valor if isinstance(valor, list) else [valor]
    if len(crudos) != n:
        return f'mic: {nombre} lleva {n} valor(es) en "valor"'
    valores: list = []
    for x in crudos:
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
            return f'mic: "valor" tiene que ser un número entre {lo:g} y {hi:g}'
        if tipo != "float":
            if x != int(x):
                return f"mic: {nombre} es entero ({lo:g} a {hi:g})"
            x = int(x)
        if not lo <= x <= hi:
            return f"mic: {nombre} va entre {lo:g} y {hi:g} ({desc})"
        valores.append(x)

    def fn(dev) -> str:
        try:
            antes = _mostrar(nombre, _usb_leer(dev, nombre))
        except Exception as e:
            return f"mic: no cambié nada: {e}"
        _usb_escribir(dev, nombre, valores)
        time.sleep(0.03)
        ahora = _mostrar(nombre, _usb_leer(dev, nombre))
        return f"mic: {nombre} estaba en {antes} y quedó en {ahora} ({desc}). No queda guardado: vuelve a lo de fábrica si el chip se reinicia."

    return _con_chip(fn)


# ── monitor: energía de voz y haces para los gráficos ─────────────────────────


def _monitor(parar: threading.Event) -> None:
    global _mon_datos, _mon_error
    dev = None
    try:
        while not parar.is_set():
            try:
                if dev is None:
                    dev = _buscar_dev()
                with _usb:
                    en = _usb_leer(dev, "AEC_SPENERGY_VALUES")
                    az = _usb_leer(dev, "AEC_AZIMUTH_VALUES")
                d: dict = {}
                finitas = [x for x in en if math.isfinite(x)]
                if finitas:
                    d["energia"] = float(f"{max(finitas):.4g}")
                for clave, i in (("haz1", 0), ("haz2", 1), ("haz_auto", 3)):
                    g = _grados(az[i])
                    if g is not None:
                        d[clave] = g
                _mon_datos = d or None
                _mon_error = ""
                parar.wait(0.2)
            except Exception as e:  # desenchufado o sin permiso: se reintenta con calma
                _mon_error = f"{type(e).__name__}: {e}"[:160]
                _mon_datos = None
                _soltar(dev)
                dev = None
                parar.wait(2)
    finally:
        _soltar(dev)
        _mon_datos = None


def activa() -> bool:
    if SIMULAR:
        return _sim_on
    h, p = _mon_hilo, _mon_parar
    return bool(h is not None and h.is_alive() and p is not None and not p.is_set())


def datos() -> dict | None:
    """Para sensores.py: solo copia lo último que midió el monitor (None si está apagado)."""
    d = _mon_datos
    return dict(d) if d and activa() else None


def _prender() -> str:
    global _mon_hilo, _mon_parar, _sim_on, _mon_error
    if SIMULAR:
        _sim_on = True
        return "mic: monitor prendido (simulado)"
    try:
        import usb.core  # noqa: F401
    except ImportError:
        return "mic: falta pyusb (python3-usb)"
    with _mon_lock:
        if activa():
            return "mic: el monitor ya estaba prendido" + (f" (sin el chip: {_mon_error})" if _mon_error else "")
        h = _mon_hilo
        if h is not None and h.is_alive():
            h.join(0.5)
            if h.is_alive():
                return "mic: el monitor todavía se está apagando; prueba de nuevo"
        _mon_error = ""
        _mon_parar = threading.Event()
        _mon_hilo = threading.Thread(target=_monitor, args=(_mon_parar,), daemon=True, name="mic-monitor")
        _mon_hilo.start()
    return "mic: monitor prendido: energía de voz y haces 5 veces por segundo (gráficos respeaker.*)"


def _apagar() -> str:
    global _sim_on
    if SIMULAR:
        _sim_on = False
        return "mic: monitor apagado (simulado)"
    with _mon_lock:
        h, p = _mon_hilo, _mon_parar
        if h is None or not h.is_alive():
            return "mic: el monitor ya estaba apagado"
        if p is not None:
            p.set()
    h.join(0.6)
    return "mic: monitor apagado" if not h.is_alive() else "mic: apagando el monitor…"


def _mic(c: dict) -> str:
    partes = []
    if "on" in c:
        partes.append(_prender() if c.get("on") else _apagar())
    if c.get("lista"):
        partes.append(_lista(c.get("lista")))
    if "poner" in c:
        partes.append(_poner_cmd(c.get("poner"), c.get("valor")))
    if "leer" in c:
        partes.append(_leer_cmd(c.get("leer")))
    if partes:
        return " · ".join(partes)
    txt = _con_chip(_resumen, 1.5)
    if activa() and _mon_error:
        txt += f" · monitor sin el chip: {_mon_error}"
    return txt


def manejar(c: dict) -> str | None:
    cmd = c.get("cmd")
    if cmd == "wiki":
        return _wiki(c)
    if cmd == "mic":
        return _mic(c)
    return None
