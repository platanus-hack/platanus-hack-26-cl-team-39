#!/usr/bin/env python3
"""
Bicho simulado: servidor WebSocket en ws://0.0.0.0:8080/ws que imita a la Pi.
Imprime cada comando que llega desde Unity y manda telemetría {"t":"s",...} a 10 Hz.
Incluye el watchdog que debe tener el firmware real: si no llega drive en 0,5 s, frena.

  .venv/bin/python mock_bicho.py            # luego en Unity: IP = 127.0.0.1
"""
import asyncio, json, math, time
import websockets

WATCHDOG_S = 0.5
state = {"l": 0.0, "r": 0.0, "servo": [90, 90], "last_drive": 0.0, "stopped_by_wd": False}


async def telemetry(ws):
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        d = {"mic": 0.1, "imu": {"pitch": round(math.sin(t) * 3, 2), "roll": 0.0},
             "dist_cm": round(80 + 30 * math.sin(t * 0.5), 1), "servo": state["servo"], "temp_cpu": 51.0, "boton": False}
        await ws.send(json.dumps({"t": "s", "ms": int(t * 1000), "d": d}))
        if (state["l"] or state["r"]) and time.monotonic() - state["last_drive"] > WATCHDOG_S:
            state["l"] = state["r"] = 0.0
            print("  ⚠ watchdog: sin comandos de manejo hace 0,5 s → motores en 0")
        await asyncio.sleep(0.1)


async def handler(ws):
    print(f"[bicho] cliente conectado desde {ws.remote_address}")
    task = asyncio.create_task(telemetry(ws))
    try:
        async for msg in ws:
            try:
                m = json.loads(msg)
            except ValueError:
                print("  (no JSON)", msg); continue
            cmd = m.get("cmd")
            if cmd == "info":
                await ws.send(json.dumps({"t": "info", "name": "bicho", "fw": "mock-0.3.0"}))
            elif cmd == "drive":
                state.update(l=float(m["l"]), r=float(m["r"]), last_drive=time.monotonic())
                bar = lambda v: ("+" if v >= 0 else "-") + "█" * int(abs(v) * 10)
                print(f"  drive  izq {m['l']:+.2f} {bar(m['l']):<12} der {m['r']:+.2f} {bar(m['r'])}")
            elif cmd == "stop":
                state.update(l=0.0, r=0.0); print("  ■ STOP")
            elif cmd == "servo":
                state["servo"][int(m["i"])] = int(m["deg"]); print(f"  servo {m['i']} → {m['deg']}°")
            elif cmd == "gesto":
                print(f"  gesto: {m.get('g')} (mano {m.get('mano')})")
            else:
                print("  ?", m)
    finally:
        task.cancel()
        state.update(l=0.0, r=0.0)
        print("[bicho] cliente desconectado → motores en 0")


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8080, process_request=None) as server:
        print("[bicho] simulado escuchando en ws://0.0.0.0:8080/ws")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
