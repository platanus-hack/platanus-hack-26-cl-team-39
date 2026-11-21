#!/usr/bin/env python3
"""
bicho · hand tracker
Cámara (o video) -> MediaPipe HandLandmarker -> UDP JSON a Unity (127.0.0.1:5065).

Paquete (uno por cuadro, compatible con JsonUtility de Unity):
{
  "t": 12.345,                      # segundos desde que arrancó
  "w": 1280, "h": 720,              # tamaño del cuadro
  "hands": [
    {"side": "Right", "score": 0.97,
     "lm":  [x0,y0,z0, x1,y1,z1, ...],   # 21 puntos normalizados (0..1, origen arriba-izq.)
     "wlm": [x0,y0,z0, ...]}             # 21 puntos en metros, centrados en la mano
  ]
}
"side" ya viene corregido para imagen en espejo: "Right" = mano derecha real del usuario.

Uso:
  .venv/bin/python hand_tracker.py                 # cámara 0, con ventana de vista previa
  .venv/bin/python hand_tracker.py --cam 1 --no-preview
  .venv/bin/python hand_tracker.py --video clip.mov --loop
  .venv/bin/python hand_tracker.py --fake          # mano sintética (probar Unity sin cámara)
"""
import argparse
import json
import math
import socket
import time
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).parent / "models" / "hand_landmarker.task"
CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
               (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17),
               (17, 18), (18, 19), (19, 20)]


def flat(points, nd=4):
    out = []
    for p in points:
        out += [round(p.x, nd), round(p.y, nd), round(p.z, nd)]
    return out


def make_landmarker(num_hands):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    if not MODEL.exists():
        raise SystemExit(f"Falta el modelo {MODEL}. Bájalo con:\n  curl -L -o {MODEL} "
                         "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                         "hand_landmarker/float16/latest/hand_landmarker.task")
    opts = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=num_hands,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp, vision.HandLandmarker.create_from_options(opts)


def detect(mp, landmarker, frame_bgr, ts_ms, mirrored):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    res = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms)
    hands = []
    for i, lms in enumerate(res.hand_landmarks):
        cat = res.handedness[i][0]
        side = cat.category_name
        # MediaPipe asume imagen espejada (selfie). Si NO espejamos, invertimos la etiqueta.
        if not mirrored:
            side = "Left" if side == "Right" else "Right"
        hands.append({"side": side, "score": round(cat.score, 3), "lm": flat(lms),
                      "wlm": flat(res.hand_world_landmarks[i], 5)})
    return hands


def fake_hands(t):
    """Mano derecha sintética abierta que dibuja un círculo y cierra el puño cada 6 s."""
    cx, cy = 0.5 + 0.18 * math.cos(t * 0.8), 0.5 + 0.15 * math.sin(t * 0.8)
    fist = (t % 6.0) > 4.5
    # Forma de mano abierta aprox. (offsets normalizados, mano de ~0.25 de alto)
    base = [(0, .12), (-.05, .08), (-.08, .04), (-.10, 0), (-.12, -.03),
            (-.04, -.01), (-.045, -.06), (-.05, -.09), (-.05, -.12),
            (0, -.015), (0, -.07), (0, -.105), (0, -.135),
            (.035, -.01), (.04, -.06), (.042, -.09), (.044, -.115),
            (.065, .005), (.075, -.035), (.08, -.06), (.085, -.08)]
    pts = [list(b) for b in base]
    if fist:
        wx, wy = base[0]
        for mcp in (5, 9, 13, 17):  # cada dedo se dobla de vuelta hacia la muñeca
            mx, my = base[mcp]
            pts[mcp + 1] = [mx, my - 0.03]                          # pip sobresale un poco
            pts[mcp + 2] = [mx + (wx - mx) * 0.1, my + (wy - my) * 0.1]
            pts[mcp + 3] = [mx + (wx - mx) * 0.3, my + (wy - my) * 0.3]
        pts[3] = [-0.06, 0.03]                                      # pulgar cruzado sobre los dedos
        pts[4] = [-0.01, 0.04]
    lm, wlm = [], []
    for dx, dy in pts:
        lm += [round(cx + dx, 4), round(cy + dy, 4), 0.0]
        wlm += [round(dx * 0.4, 5), round(dy * 0.4, 5), 0.0]
    return [{"side": "Right", "score": 1.0, "lm": lm, "wlm": wlm}]


def try_camera(idx, args, warmup_s=3.0):
    """Abre la cámara idx y espera hasta warmup_s a que entregue un cuadro real."""
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    t = time.monotonic()
    while time.monotonic() - t < warmup_s:
        ok, frame = cap.read()
        if ok and frame is not None and frame.size:
            return cap
        time.sleep(0.1)
    cap.release()
    return None


def open_camera(args):
    """--cam N usa esa; si no, prueba 0..3 y se queda con la primera que entregue imagen.
    (En Mac con iPhone cerca, la cámara 0 puede ser Continuity y no dar imagen.)
    Reintenta hasta 30 s por si macOS está pidiendo el permiso de cámara."""
    candidates = [args.cam] if args.cam >= 0 else [0, 1, 2, 3]
    deadline = time.monotonic() + 30
    warned = False
    while time.monotonic() < deadline:
        for i in candidates:
            cap = try_camera(i, args)
            if cap is not None:
                print(f"[tracker] usando cámara {i} ({int(cap.get(3))}x{int(cap.get(4))})")
                return cap
            print(f"[tracker] cámara {i}: no entrega imagen")
        if not warned:
            print("[tracker] esperando permiso/cámara… (acepta el aviso de macOS)")
            warned = True
        time.sleep(1)
    return None


def draw(frame, hands):
    h, w = frame.shape[:2]
    for hand in hands:
        pts = [(int(hand["lm"][k * 3] * w), int(hand["lm"][k * 3 + 1] * h)) for k in range(21)]
        for a, b in CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], (212, 247, 43), 2)
        for p in pts:
            cv2.circle(frame, p, 4, (255, 255, 255), -1)
        cv2.putText(frame, f'{hand["side"]} {hand["score"]:.2f}', (pts[0][0] - 30, pts[0][1] + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cam", type=int, default=-1, help="índice de cámara (default: la primera que entregue imagen)")
    ap.add_argument("--video", help="archivo de video en vez de cámara")
    ap.add_argument("--loop", action="store_true", help="repetir el video al terminar")
    ap.add_argument("--fake", action="store_true", help="mano sintética, sin cámara ni modelo")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5065)
    ap.add_argument("--hands", type=int, default=2)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--no-mirror", action="store_true", help="no espejar la cámara")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--print", action="store_true", help="imprimir manos detectadas por consola")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.host, args.port)
    t0 = time.monotonic()
    print(f"[tracker] enviando a udp://{args.host}:{args.port}  (Ctrl+C para salir)")

    if args.fake:
        while True:
            t = time.monotonic() - t0
            pkt = {"t": round(t, 3), "w": 1280, "h": 720, "hands": fake_hands(t)}
            sock.sendto(json.dumps(pkt, separators=(",", ":")).encode(), dest)
            time.sleep(1 / 30)

    mp, landmarker = make_landmarker(args.hands)
    if args.video:
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            raise SystemExit(f"No pude abrir el video {args.video}")
    else:
        cap = open_camera(args)
        if cap is None:
            raise SystemExit("No encontré ninguna cámara que entregue imagen. Revisa Ajustes > Privacidad y "
                             "seguridad > Cámara (habilita tu terminal y ábrela de nuevo) o prueba --cam 1.")

    mirrored = not args.no_mirror and not args.video
    last_ts, frames, fps_t, fps, fails = -1, 0, time.monotonic(), 0.0, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if args.video:
                    if args.loop:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break
                fails += 1  # cámara: un cuadro perdido no cierra el tracker
                if fails == 30:
                    print("[tracker] la cámara dejó de entregar imagen; sigo intentando…")
                time.sleep(0.03)
                continue
            fails = 0
            if mirrored:
                frame = cv2.flip(frame, 1)
            ts = int((time.monotonic() - t0) * 1000)
            ts = max(ts, last_ts + 1)  # VIDEO mode exige timestamps crecientes
            last_ts = ts
            hands = detect(mp, landmarker, frame, ts, mirrored=True if mirrored else False)
            h, w = frame.shape[:2]
            pkt = {"t": round(ts / 1000, 3), "w": w, "h": h, "hands": hands}
            sock.sendto(json.dumps(pkt, separators=(",", ":")).encode(), dest)

            frames += 1
            if time.monotonic() - fps_t >= 1:
                fps, frames, fps_t = frames / (time.monotonic() - fps_t), 0, time.monotonic()
                if args.print:
                    print(f"[tracker] {fps:4.1f} fps · manos: {[x['side'] for x in hands]}")
            if not args.no_preview:
                draw(frame, hands)
                cv2.putText(frame, f"{fps:.0f} fps -> udp {args.port}", (12, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (43, 247, 212), 2)
                cv2.imshow("bicho · hand tracker (q para salir)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
