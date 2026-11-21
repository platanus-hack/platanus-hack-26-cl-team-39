#!/usr/bin/env python3
"""
bicho · señas
Enseñarle una seña al bicho con la voz y que la reconozca con su propia cámara.

  1. Le muestras la mano a la cámara del bicho y le dices «Bicho, esta seña significa para».
  2. El oído del bicho transcribe la frase (llega por el relé como {"t":"oido","texto":…}).
  3. Este servicio toma la mano que veía mientras hablabas, la guarda como la seña «para»
     y lo anuncia en bicho·dev (Cerebro y Habilidades) como algo que aprendió solo.
  4. Cuando vuelve a ver esa seña, manda la acción: para → {"cmd":"stop"} + luz roja.

Corre en el computador (MediaPipe no anda bien en la Pi 3) y habla con el bicho por el relé,
como un cliente más con la clave del equipo. No toca el código del bicho.

Fuentes de imagen:
  --fuente rele   la cámara del bicho (imágenes {"t":"imagen"} que reparte el relé; ~1 por segundo)
  --fuente cam    la cámara de este computador (plan B, 30 fps)
  --video X.mov   un video (pruebas)

Uso:
  .venv/bin/python senas.py --rele https://<relé> --clave <clave>              # cámara del bicho
  .venv/bin/python senas.py --rele https://<relé> --clave <clave> --fuente cam # cámara del Mac
  .venv/bin/python senas.py --fuente cam --sin-rele                            # ensayo sin bicho
Teclado (escribe y Enter): «e para» enseña la mano actual como «para» · «l» lista · «b para» borra.
La clave también puede ir en la variable BICHO_CLAVE. Nunca la subas al repo.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import queue
import re
import socket
import sys
import threading
import time
import unicodedata
from collections import deque
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).parent
MODEL = AQUI / "models" / "hand_landmarker.task"
SENAS_JSON = AQUI / "senas.json"

# Qué hace el bicho con cada seña. Las que no estén aquí solo se anuncian (el cerebro puede aprender a reaccionar).
# "si", "no" y "responder" son comandos que el bicho vivo ya tiene (fw 0.10+): verde, rojo y respuesta con luces.
ACCIONES: dict[str, list[dict]] = {
    "para": [{"cmd": "stop"}, {"cmd": "no"}],
    "alto": [{"cmd": "stop"}, {"cmd": "no"}],
    "detente": [{"cmd": "stop"}, {"cmd": "no"}],
    "stop": [{"cmd": "stop"}, {"cmd": "no"}],
    "hola": [{"cmd": "si"}],
    "saluda": [{"cmd": "si"}],
    "bien": [{"cmd": "si"}],
    "celebra": [{"cmd": "responder"}],
    "no": [{"cmd": "no"}],
}
QUE_HACE = {"para": "me detengo", "alto": "me detengo", "detente": "me detengo", "stop": "me detengo",
            "hola": "saludo con la luz verde", "saluda": "saludo con la luz verde", "bien": "prendo la luz verde",
            "celebra": "celebro con las luces", "no": "prendo la luz roja"}

# «esta seña significa para», «esa seña quiere decir alto», «aprende esta seña: hola», «esta seña es para que pares»
FRASE = re.compile(r"(?:esta|esa|la|una)\s+sen(?:a|al)\s*[:,.]?\s*(?:significa|quiere\s+decir|es|sera|va\s+a\s+ser)\s+(?:que\s+)?(?:te\s+)?([a-z]+(?:\s+[a-z]+)?)"
                   r"|aprende\s+(?:esta|esa)\s+sen(?:a|al)\s*[:,]?\s*([a-z]+)")
NORMALIZA = {"pares": "para", "parar": "para", "detengas": "detente", "detenerte": "detente", "alto": "alto",
             "saludes": "saluda", "saludar": "saluda", "celebres": "celebra", "celebrar": "celebra"}

TIPS = [4, 8, 12, 16, 20]


def sin_tildes(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("ñ", "n")


def nombre_de_frase(texto: str) -> str | None:
    t = sin_tildes(texto)
    m = FRASE.search(t)
    if not m:
        return None
    palabras = (m.group(1) or m.group(2) or "").split()
    if not palabras:
        return None
    w = NORMALIZA.get(palabras[0], palabras[0])
    return w


# ---------------------------------------------------------------- rasgos de una mano

def _ang(a, b, c) -> float:
    u, v = b - a, c - b
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu < 1e-6 or nv < 1e-6:
        return 0.0
    return math.degrees(math.acos(float(np.clip(np.dot(u, v) / (nu * nv), -1, 1))))


def rasgos(w: np.ndarray, img: np.ndarray) -> np.ndarray:
    """Vector que describe la forma de la mano, igual de cerca o de lejos de la cámara.
    w: 21x3 puntos en metros (MediaPipe world). img: 21x3 puntos normalizados de la imagen."""
    palma = max(1e-4, float(np.linalg.norm(w[9] - w[0])))
    f = []
    # flexión de cada dedo (0 = recto, 180 = doblado del todo), en dos tramos
    for mcp in (1, 5, 9, 13, 17):
        f.append(_ang(w[mcp], w[mcp + 1], w[mcp + 2]) / 90.0)
        f.append(_ang(w[mcp + 1], w[mcp + 2], w[mcp + 3]) / 90.0)
    # qué tan lejos queda cada punta de la muñeca, en palmas
    for t in TIPS:
        f.append(float(np.linalg.norm(w[t] - w[0])) / palma / 2.0)
    # separación entre puntas vecinas (abanico) y pulgar-índice (pinza)
    for a, b in ((4, 8), (8, 12), (12, 16), (16, 20)):
        f.append(float(np.linalg.norm(w[a] - w[b])) / palma)
    # hacia dónde apuntan los dedos en la imagen (arriba, de lado, abajo): pesa poco pero separa «para» de «ok»
    d = img[9, :2] - img[0, :2]
    n = float(np.linalg.norm(d)) or 1.0
    f += [0.6 * d[0] / n, 0.6 * d[1] / n]
    return np.array(f, dtype=np.float32)


def gesto_basico(w: np.ndarray) -> str:
    """Mismo criterio que GestureRecognizer.cs: dedo estirado si se dobla < 75° y la punta se aleja de la muñeca."""
    def estirado(mcp):
        return (_ang(w[mcp], w[mcp + 1], w[mcp + 3]) < 75 and
                np.linalg.norm(w[mcp + 3] - w[0]) > np.linalg.norm(w[mcp + 1] - w[0]))
    i, m, r, p = (estirado(k) for k in (5, 9, 13, 17))
    n = i + m + r + p
    if i and m and r:
        return "palma"
    if n == 0:
        return "puno"
    if i and not (m or r or p):
        return "indice"
    if i and m and not (r or p):
        return "victoria"
    return "otra"


# ---------------------------------------------------------------- memoria de señas

class Senas:
    """Plantillas por vecino más cercano. Cada seña guarda varias muestras; una mano nueva es esa seña si su
    distancia a la muestra más parecida baja del umbral y le gana con margen a las demás señas."""

    def __init__(self, path: Path, umbral: float = 0.5):
        self.path, self.umbral = path, umbral
        self.datos: dict[str, dict] = {}      # nombre -> {"gesto": "palma", "muestras": [[…rasgos]]}
        if path.exists():
            try:
                self.datos = json.loads(path.read_text(encoding="utf-8")).get("senas", {})
                self.datos = {k: (v if isinstance(v, dict) else {"gesto": "otra", "muestras": v}) for k, v in self.datos.items()}
            except Exception:
                self.datos = {}

    def guardar(self):
        self.path.write_text(json.dumps({"senas": self.datos}, ensure_ascii=False), encoding="utf-8")

    def ensenar(self, nombre: str, muestras: list[np.ndarray], gestos: list[str] | None = None):
        # La forma básica que más se repitió (palma, puño, índice, victoria…) sirve de filtro al reconocer.
        g = max(set(gestos), key=gestos.count) if gestos else "otra"
        self.datos[nombre] = {"gesto": g, "muestras": [list(map(float, m)) for m in muestras][-12:]}
        self.guardar()

    def borrar(self, nombre: str):
        self.datos.pop(nombre, None)
        self.guardar()

    def reconocer(self, f: np.ndarray, gesto: str | None = None) -> tuple[str | None, float]:
        mejor: list[tuple[float, str]] = []
        for nombre, sena in self.datos.items():
            if gesto and sena["gesto"] != "otra" and gesto != sena["gesto"]:
                continue   # otra forma de mano: no puede ser esta seña
            d = min(float(np.linalg.norm(f - np.asarray(m))) for m in sena["muestras"])
            mejor.append((d / math.sqrt(len(f)) * 4, nombre))   # distancia por rasgo, escalada a ~0..2
        if not mejor:
            return None, 9.0
        mejor.sort()
        d, nombre = mejor[0]
        if d > self.umbral:
            return None, d
        if len(mejor) > 1 and mejor[1][0] - d < 0.08:   # dos señas casi iguales: mejor no decidir
            return None, d
        return nombre, d


# ---------------------------------------------------------------- detector

class Detector:
    def __init__(self, num_hands=1):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        if not MODEL.exists():
            raise SystemExit(f"Falta el modelo {MODEL}: corre ./correr.sh una vez o bájalo (ver hand_tracker.py).")
        self.mp = mp
        self.lm = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=vision.RunningMode.IMAGE,
            num_hands=num_hands, min_hand_detection_confidence=0.5, min_hand_presence_confidence=0.5))

    def __call__(self, bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        r = self.lm.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb))
        manos = []
        for i, lms in enumerate(r.hand_landmarks):
            img = np.array([[p.x, p.y, p.z] for p in lms], dtype=np.float32)
            w = np.array([[p.x, p.y, p.z] for p in r.hand_world_landmarks[i]], dtype=np.float32)
            manos.append({"img": img, "w": w, "lado": r.handedness[i][0].category_name, "score": r.handedness[i][0].score})
        return manos


# ---------------------------------------------------------------- relé

class Rele:
    """Cliente del relé en un hilo propio: recibe imágenes y frases, manda comandos (con la clave)."""

    def __init__(self, url: str, clave: str | None, imagenes: queue.Queue, frases: queue.Queue):
        base = url.strip().rstrip("/")
        base = re.sub(r"^http", "ws", base) if base.startswith("http") else ("wss://" + base if "://" not in base else base)
        self.url = base + "/ws" + (f"?clave={clave}" if clave else "")
        self.publica = base + "/ws"
        self.imagenes, self.frases = imagenes, frases
        self.salida: asyncio.Queue | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.conectado = False
        self.puede_mandar = bool(clave)
        self.ultimo_aviso = ""
        self.al_volver_bicho = None   # se llama cada vez que el bicho aparece en el relé
        threading.Thread(target=self._hilo, daemon=True).start()

    def mandar(self, obj: dict):
        if self.loop and self.salida is not None:
            self.loop.call_soon_threadsafe(self.salida.put_nowait, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

    def _hilo(self):
        self.loop = asyncio.new_event_loop()
        self.loop.run_until_complete(self._correr())

    async def _correr(self):
        import websockets
        self.salida = asyncio.Queue()
        espera = 1
        while True:
            try:
                async with websockets.connect(self.url, max_size=None, open_timeout=10, ping_interval=10) as ws:
                    self.conectado, espera = True, 1
                    print(f"[señas] conectado al relé {self.publica}")
                    envio = asyncio.create_task(self._enviar(ws))
                    try:
                        async for m in ws:
                            for linea in m.splitlines():
                                self._llega(linea)
                    finally:
                        envio.cancel()
            except Exception as e:
                print(f"[señas] relé: {e.__class__.__name__}: {e}; reintento en {espera} s")
            self.conectado = False
            await asyncio.sleep(espera)
            espera = min(espera * 2, 15)

    async def _enviar(self, ws):
        while True:
            await ws.send(await self.salida.get())

    def _llega(self, linea: str):
        try:
            o = json.loads(linea)
        except Exception:
            return
        t = o.get("t")
        if t == "imagen" and o.get("nombre", "camara") == "camara" and o.get("b64"):
            if self.imagenes.full():
                try:
                    self.imagenes.get_nowait()
                except queue.Empty:
                    pass
            self.imagenes.put_nowait((time.time(), o["b64"]))
        elif t == "oido" and o.get("estado") == "listo" and o.get("texto"):
            self.frases.put((o.get("ts") or time.time() * 1000, float(o.get("dur") or 0), o["texto"]))
        elif t == "rele":
            if "puedeMandar" in o:
                self.puede_mandar = bool(o["puedeMandar"])
            print(f"[señas] relé: bicho {'en línea' if o.get('bicho') else 'NO conectado'}")
            if o.get("bicho") and self.al_volver_bicho:
                self.al_volver_bicho()
        elif t == "log" and o.get("lvl") == "warn" and o.get("msg") != self.ultimo_aviso:
            self.ultimo_aviso = o.get("msg")
            if "clave" in self.ultimo_aviso:
                self.puede_mandar = False
                print(f"[señas] relé: {self.ultimo_aviso}")


# ---------------------------------------------------------------- servicio

class Servicio:
    def __init__(self, args):
        self.args = args
        self.senas = Senas(Path(args.senas), args.umbral)
        self.historial: deque = deque(maxlen=400)      # (t, rasgos, gesto) de las últimas manos vistas
        self.actual: tuple[str | None, int] = (None, 0)  # seña candidata y cuántas detecciones seguidas
        self.activa: str | None = None                   # seña ya disparada (hasta que deje de verse)
        self.ultimo_disparo = 0.0
        self.sin_mano_desde = time.time()
        self.rele: Rele | None = None
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if args.udp else None

    # --- avisos a bicho·dev: eventos con la misma forma que los del cerebro, así salen en Cerebro y Habilidades
    def anunciar(self, tipo: str, texto: str, **extra):
        print(f"[señas] {tipo}: {texto}")
        if self.rele and self.rele.puede_mandar:
            self.rele.mandar({"t": "cerebro", "tipo": tipo, "texto": texto, "ts": int(time.time() * 1000),
                              "origen": "senas", **extra})

    def comando(self, c: dict):
        if self.args.sin_enviar or not self.rele:
            print(f"[señas] (no enviado) {json.dumps(c, ensure_ascii=False)}")
            return
        self.rele.mandar(c)
        print(f"[señas] → bicho {json.dumps(c, ensure_ascii=False)}")

    # --- aprender
    def ensenar(self, nombre: str, desde: float, hasta: float, pedido: str | None = None):
        vistas = [(f, g) for (t, f, g) in self.historial if desde <= t <= hasta]
        if not vistas:  # la frase llega transcrita un poco después: usa lo último que vio, si es reciente
            vistas = [(f, g) for (t, f, g) in self.historial if t >= time.time() - self.args.ventana]
        muestras = [f for f, g in vistas]
        if not muestras:
            self.anunciar("responde", f"Te escuché («{nombre}»), pero no vi ninguna mano. Muéstramela a la cámara mientras me lo dices.")
            return
        trabajo = f"sena-{nombre}-{int(time.time())}"
        que = QUE_HACE.get(nombre, f"aviso «{nombre}» para que el cerebro decida qué hacer")
        self.anunciar("paso", f"Empiezo a aprender: la seña «{nombre}» ({len(muestras)} imágenes de tu mano)",
                      trabajo=trabajo, pedido=pedido)
        self.senas.ensenar(nombre, muestras, [g for f, g in vistas])
        self.activa = nombre                      # la está mostrando ahora: no dispararla por enseñarla
        self.ultimo_disparo = time.time()
        self.anunciar("aprendido", f"Aprendí la seña «{nombre}»: cuando la vea, {que}.", trabajo=trabajo,
                      habilidad={"nombre": f"Seña «{nombre}»", "como": f"muéstrale la seña «{nombre}» a su cámara"})
        self.comando({"cmd": "si"})               # luz verde: entendí

    def frase(self, ts_ms: float, dur: float, texto: str):
        nombre = nombre_de_frase(texto)
        if not nombre:
            return
        fin = ts_ms / 1000 if ts_ms > 1e11 else time.time()
        self.ensenar(nombre, fin - dur - 1.0, fin + 1.0, pedido=texto)

    # --- ver
    def mano(self, t: float, mano: dict | None):
        if mano is None:
            if time.time() - self.sin_mano_desde > 1.0:
                self.activa = None
            self.actual = (None, 0)
            return None
        self.sin_mano_desde = time.time()
        f = rasgos(mano["w"], mano["img"])
        g = gesto_basico(mano["w"])
        self.historial.append((t, f, g))
        nombre, d = self.senas.reconocer(f, g)
        cand, n = self.actual
        self.actual = (nombre, n + 1 if nombre == cand else 1)
        necesita = self.args.confirmar
        if nombre and self.actual[1] >= necesita and nombre != self.activa and time.time() - self.ultimo_disparo > 1.5:
            self.activa, self.ultimo_disparo = nombre, time.time()
            que = QUE_HACE.get(nombre)
            self.anunciar("responde", f"Vi la seña «{nombre}»" + (f": {que}." if que else "."))
            for c in ACCIONES.get(nombre, []):
                self.comando(c)
        if nombre is None and self.actual[1] >= necesita:
            self.activa = None
        return nombre, d, g

    def a_unity(self, frame_wh, manos):
        if not self.udp:
            return
        w, h = frame_wh
        pkt = {"t": time.time(), "w": w, "h": h, "hands": [
            {"side": m["lado"], "score": round(m["score"], 3), "lm": [round(float(x), 4) for x in m["img"].ravel()],
             "wlm": [round(float(x), 5) for x in m["w"].ravel()]} for m in manos]}
        self.udp.sendto(json.dumps(pkt, separators=(",", ":")).encode(), ("127.0.0.1", self.args.udp))


def teclado(cola: queue.Queue):
    for linea in sys.stdin:
        cola.put(linea.strip())


def dibujar(frame, manos, rotulo):
    h, w = frame.shape[:2]
    for m in manos:
        pts = [(int(p[0] * w), int(p[1] * h)) for p in m["img"]]
        for a, b in [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
                     (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]:
            cv2.line(frame, pts[a], pts[b], (212, 247, 43), 2)
    cv2.putText(frame, rotulo, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 199, 255), 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rele", default=os.environ.get("BICHO_RELE", ""), help="https://<relé> (o BICHO_RELE)")
    ap.add_argument("--clave", default=os.environ.get("BICHO_CLAVE"), help="clave del equipo (o BICHO_CLAVE)")
    ap.add_argument("--sin-rele", action="store_true", help="ensayo local: no se conecta a nada")
    ap.add_argument("--fuente", choices=["rele", "cam"], default="rele")
    ap.add_argument("--cam", type=int, default=-1)
    ap.add_argument("--video")
    ap.add_argument("--camara-on", default='{"cmd":"camara","on":true}',
                    help="comando para que el bicho mande imágenes (JSON; vacío para no mandarlo)")
    ap.add_argument("--senas", default=str(SENAS_JSON), help="archivo donde se guardan las señas aprendidas")
    ap.add_argument("--umbral", type=float, default=0.5, help="distancia máxima para reconocer (más bajo = más estricto)")
    ap.add_argument("--confirmar", type=int, default=0, help="detecciones seguidas para disparar (0 = automático)")
    ap.add_argument("--ventana", type=float, default=4.0, help="segundos de mano que sirven para enseñar")
    ap.add_argument("--udp", type=int, default=5065, help="manda también las manos a Unity (0 = no)")
    ap.add_argument("--sin-enviar", action="store_true", help="no manda comandos al bicho, solo los imprime")
    ap.add_argument("--ver", action="store_true", help="ventana con lo que ve")
    ap.add_argument("--ensenar-en", help="pruebas con --video: «segundo:nombre», p. ej. 1.5:para")
    args = ap.parse_args()
    if not args.confirmar:
        args.confirmar = 2 if (args.fuente == "rele" and not args.video) else 6

    s = Servicio(args)
    imagenes: queue.Queue = queue.Queue(maxsize=2)
    frases: queue.Queue = queue.Queue()
    if not args.sin_rele and not args.video:
        if not args.rele:
            raise SystemExit("Falta --rele https://<relé> (está en web/src/lib/rele.json) o usa --sin-rele.")
        if not args.clave:
            print("[señas] sin clave: se puede mirar, pero no mandar comandos ni anunciar en bicho·dev")
        s.rele = Rele(args.rele, args.clave, imagenes, frases)
        if args.fuente == "rele" and args.camara_on:
            encender = json.loads(args.camara_on)
            s.rele.al_volver_bicho = lambda: s.comando(encender)   # cámara del bicho: una imagen por segundo
    det = Detector()
    print(f"[señas] señas guardadas: {', '.join(s.senas.datos) or 'ninguna'} · fuente: {args.video or args.fuente}")
    print("[señas] di «Bicho, esta seña significa para» mostrando la mano, o escribe «e para» y Enter")

    cap = None
    if args.video:
        cap = cv2.VideoCapture(args.video)
    elif args.fuente == "cam":
        sys.path.insert(0, str(AQUI))
        from hand_tracker import open_camera
        args.width, args.height = 1280, 720
        cap = open_camera(args)
        if cap is None:
            raise SystemExit("No encontré una cámara que entregue imagen.")
    ensenar_en = None
    if args.ensenar_en:
        seg, nom = args.ensenar_en.split(":")
        ensenar_en = (float(seg), nom)

    tecl: queue.Queue = queue.Queue()
    if not args.video:
        threading.Thread(target=teclado, args=(tecl,), daemon=True).start()
    vistos = reconocidos = 0
    t_video = 0.0
    try:
        while True:
            # 1) una imagen
            if cap is not None:
                ok, frame = cap.read()
                if not ok:
                    if args.video:
                        break
                    time.sleep(0.03)
                    continue
                if args.video:
                    t_video = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                elif args.fuente == "cam":
                    frame = cv2.flip(frame, 1)
                t = t_video if args.video else time.time()
            else:
                try:
                    t, b64 = imagenes.get(timeout=0.2)
                    frame = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
                except queue.Empty:
                    frame = None
                t = time.time()
            # 2) manos
            if frame is not None:
                manos = det(frame)
                vistos += 1
                m = max(manos, key=lambda x: x["score"]) if manos else None
                r = s.mano(t, m)
                s.a_unity((frame.shape[1], frame.shape[0]), manos)
                if r and r[0]:
                    reconocidos += 1
                if args.video and ensenar_en and t >= ensenar_en[0]:
                    s.ensenar(ensenar_en[1], t - 0.6, t)
                    ensenar_en = None
                if args.ver:
                    rot = (f"{r[0] or '-'}  d={r[1]:.2f}  {r[2]}" if r else "sin mano")
                    dibujar(frame, manos, rot)
                    cv2.imshow("bicho · señas (q para salir)", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
            # 3) frases del oído y teclado
            while not frases.empty():
                s.frase(*frases.get())
            while not tecl.empty():
                k = tecl.get()
                if k.startswith("e "):
                    s.ensenar(k[2:].strip().lower(), time.time() - 1.0, time.time())
                elif k.startswith("b "):
                    s.senas.borrar(k[2:].strip().lower())
                    print("[señas] borrada")
                elif k == "l":
                    print("[señas]", {n: f'{v["gesto"]}, {len(v["muestras"])} muestras' for n, v in s.senas.datos.items()})
                elif k:
                    s.frase(time.time() * 1000, 0, k)   # escribir la frase también sirve
    except KeyboardInterrupt:
        pass
    finally:
        if s.rele and not args.sin_enviar:
            s.comando({"cmd": "stop"})
            time.sleep(0.3)
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
    if args.video:
        print(f"[señas] video: {vistos} cuadros, {reconocidos} con seña reconocida")


if __name__ == "__main__":
    main()
