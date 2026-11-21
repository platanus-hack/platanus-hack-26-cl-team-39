#!/usr/bin/env python3
"""
bichod: el agente que corre en el Raspberry Pi del bicho.

Habla el protocolo de PROTOCOLO.md en un solo puerto (8080 por defecto):
  - WebSocket en  ws://<bicho>:8080/ws   → info, sensores a 20 Hz, logs y comandos
  - HTTP GET      /info                  → la misma info en JSON
  - HTTP POST     /update                → recibe un paquete .tar.gz con una versión nueva,
                                           la instala en releases/<versión>, cambia el enlace
                                           current y se reinicia con esa versión.

Solo usa la librería estándar (Python 3.9+): en el Pi no hay que instalar nada.
Lo que hay que editar está en sensores.py (lecturas) y comandos.py (acciones).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import comandos  # noqa: E402
import sensores  # noqa: E402

PORT = int(os.environ.get("BICHO_PORT", "8080"))
MAX_PACKAGE = 64 * 1024 * 1024
START = time.time()
META = json.loads((HERE / "version.json").read_text(encoding="utf-8"))


def _home() -> Path:
    if os.environ.get("BICHO_HOME"):
        return Path(os.environ["BICHO_HOME"])
    opt = Path("/opt/bicho")
    if opt.exists() and os.access(opt, os.W_OK):
        return opt
    return Path.home() / ".bicho"


HOME = _home()
RELEASES = HOME / "releases"
CURRENT = HOME / "current"

clients: set[WebSocket] = set()
period = 0.05  # 20 Hz


def log(msg: str) -> None:
    print(f"[bichod] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Info del dispositivo
# ---------------------------------------------------------------------------


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip("\x00\n ")
    except OSError:
        return None


def _ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no manda nada; solo elige la interfaz de salida
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _mac() -> str:
    for iface in ("wlan0", "eth0"):
        m = _read(f"/sys/class/net/{iface}/address")
        if m:
            return m.upper()
    n = uuid.getnode()
    return ":".join(f"{(n >> i) & 0xFF:02X}" for i in range(40, -1, -8))


def _mem_available() -> int | None:
    txt = _read("/proc/meminfo")
    if txt:
        m = re.search(r"MemAvailable:\s+(\d+)\s*kB", txt)
        if m:
            return int(m.group(1)) * 1024
    return None


def info() -> dict:
    built = META.get("built")
    if not built:
        built = time.strftime("%Y-%m-%d %H:%M", time.localtime((HERE / "version.json").stat().st_mtime))
    return {
        "t": "info",
        "name": socket.gethostname().split(".")[0],
        "fw": META["version"],
        "desc": META.get("desc", ""),
        "chip": _read("/proc/device-tree/model") or f"{platform.system()} {platform.machine()}",
        "build": built,
        "ip": _ip(),
        "mac": _mac(),
        "uptime": int(time.time() - START),
        "heap": _mem_available(),
        "python": platform.python_version(),
    }


# ---------------------------------------------------------------------------
# WebSocket mínimo (RFC 6455)
# ---------------------------------------------------------------------------

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocket:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.lock = asyncio.Lock()
        self.closed = False

    @staticmethod
    def frame(opcode: int, payload: bytes) -> bytes:
        n = len(payload)
        head = bytes([0x80 | opcode])
        if n < 126:
            head += bytes([n])
        elif n < 65536:
            head += bytes([126]) + n.to_bytes(2, "big")
        else:
            head += bytes([127]) + n.to_bytes(8, "big")
        return head + payload

    async def _write(self, data: bytes) -> None:
        async with self.lock:
            self.writer.write(data)
            await asyncio.wait_for(self.writer.drain(), timeout=2)

    async def send(self, text: str) -> None:
        if not self.closed:
            await self._write(self.frame(0x1, text.encode("utf-8")))

    async def recv(self) -> str | None:
        """Devuelve el próximo mensaje de texto, o None si el cliente cerró."""
        parts: list[bytes] = []
        while True:
            h = await self.reader.readexactly(2)
            fin, opcode = h[0] & 0x80, h[0] & 0x0F
            masked, n = h[1] & 0x80, h[1] & 0x7F
            if n == 126:
                n = int.from_bytes(await self.reader.readexactly(2), "big")
            elif n == 127:
                n = int.from_bytes(await self.reader.readexactly(8), "big")
            if n > 1024 * 1024:
                return None
            mask = await self.reader.readexactly(4) if masked else b""
            data = await self.reader.readexactly(n)
            if masked:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:  # cierre
                self.closed = True
                try:
                    await self._write(self.frame(0x8, data[:2]))
                except Exception:
                    pass
                return None
            if opcode == 0x9:  # ping
                await self._write(self.frame(0xA, data))
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode in (0x0, 0x1):
                parts.append(data)
                if fin:
                    return b"".join(parts).decode("utf-8", errors="replace")


async def broadcast(obj: dict) -> None:
    if not clients:
        return
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    for ws in list(clients):
        try:
            await ws.send(text)
        except Exception:
            clients.discard(ws)


async def send_log(msg: str, lvl: str = "info") -> None:
    log(msg)
    await broadcast({"t": "log", "lvl": lvl, "msg": msg})


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


async def handle_cmd(text: str, ws: WebSocket) -> None:
    global period
    try:
        c = json.loads(text)
        if not isinstance(c, dict):
            raise ValueError
    except ValueError:
        await send_log(f"comando no es JSON: {text[:120]}", "warn")
        return
    cmd = c.get("cmd")
    if cmd == "info":
        await ws.send(json.dumps(info(), ensure_ascii=False))
    elif cmd == "rate":
        hz = float(c.get("hz", 0) or 0)
        if 0 < hz <= 100:
            period = 1 / hz
            await send_log(f"tasa de sensores: {hz:g} Hz")
    elif cmd == "reboot":
        await send_log("reiniciando el agente")
        asyncio.get_running_loop().call_later(0.3, restart)
    else:
        try:
            out = comandos.manejar(c)
        except Exception as e:  # un error en comandos.py no debe botar el agente
            await send_log(f"error en comandos.py: {e!r}", "error")
            return
        await send_log(out if out else f"comando desconocido: {text[:120]}", "info" if out else "warn")


# ---------------------------------------------------------------------------
# Actualizaciones
# ---------------------------------------------------------------------------

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([-.][\w.]+)?$")


def _norm(name: str) -> str:
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def install_release(data: bytes) -> str:
    """Instala un paquete .tar.gz y apunta current a él. Devuelve la versión instalada."""
    RELEASES.mkdir(parents=True, exist_ok=True)
    # r:* acepta .tar.gz y también .tar plano: algunos servidores mandan el .gz con
    # Content-Encoding: gzip y el navegador lo entrega ya descomprimido.
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        members = [m for m in tf.getmembers() if _norm(m.name) not in ("", ".")]
        for m in members:
            p = Path(_norm(m.name))
            if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
                raise ValueError(f"el paquete trae una ruta no permitida: {m.name}")
        names = {_norm(m.name): m for m in members}
        if "version.json" not in names or "bichod.py" not in names:
            raise ValueError("el paquete no trae version.json y bichod.py en la raíz")
        meta = json.load(tf.extractfile(names["version.json"]))  # type: ignore[arg-type]
        version = str(meta.get("version", ""))
        if not VERSION_RE.match(version):
            raise ValueError(f"versión inválida en version.json: {version!r}")

        tmp = RELEASES / f".{version}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        for m in members:
            target = tmp / _norm(m.name)
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tf.extractfile(m).read())  # type: ignore[union-attr]

    _install_requirements(tmp)

    dest = RELEASES / version
    if dest.exists():
        shutil.rmtree(dest)
    tmp.rename(dest)

    link_tmp = HOME / "current.tmp"
    if link_tmp.is_symlink() or link_tmp.exists():
        link_tmp.unlink()
    os.symlink(Path("releases") / version, link_tmp)
    os.replace(link_tmp, CURRENT)
    _prune(keep=5)
    return version


def _install_requirements(new: Path) -> None:
    req = new / "requirements.txt"
    if not req.exists():
        return
    wanted = [l for l in req.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
    cur = CURRENT / "requirements.txt"
    if not wanted or (cur.exists() and cur.read_text() == req.read_text()):
        return
    log(f"instalando dependencias: {', '.join(wanted)}")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"pip falló: {(r.stderr or r.stdout).strip()[-400:]}")


def _prune(keep: int) -> None:
    current = CURRENT.resolve().name if CURRENT.exists() else None
    olds = sorted((p for p in RELEASES.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in olds[keep:]:
        if p.name != current:
            shutil.rmtree(p, ignore_errors=True)


def restart() -> None:
    """Se reemplaza a sí mismo por la versión que apunta current (o por este mismo archivo)."""
    target = CURRENT / "bichod.py" if (CURRENT / "bichod.py").exists() else HERE / "bichod.py"
    log(f"reiniciando con {target}")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, str(target)])


# ---------------------------------------------------------------------------
# HTTP + upgrade a WebSocket en el mismo puerto
# ---------------------------------------------------------------------------

CORS = [
    "Access-Control-Allow-Origin: *",
    "Access-Control-Allow-Methods: GET, POST, OPTIONS",
    "Access-Control-Allow-Headers: *",
    "Access-Control-Allow-Private-Network: true",
]
REASONS = {200: "OK", 204: "No Content", 400: "Bad Request", 404: "Not Found", 413: "Payload Too Large", 500: "Internal Server Error"}


async def respond(writer: asyncio.StreamWriter, status: int, body: str | bytes = b"", ctype: str = "text/plain; charset=utf-8") -> None:
    data = body.encode("utf-8") if isinstance(body, str) else body
    head = [f"HTTP/1.1 {status} {REASONS.get(status, 'OK')}", f"Content-Type: {ctype}", f"Content-Length: {len(data)}", "Connection: close", *CORS]
    writer.write(("\r\n".join(head) + "\r\n\r\n").encode() + data)
    await writer.drain()


async def handle_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        raw = await reader.readuntil(b"\r\n\r\n")
        lines = raw.decode("latin-1").split("\r\n")
        method, path, _ = (lines[0].split(" ") + ["", "", ""])[:3]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        if headers.get("upgrade", "").lower() == "websocket" and path.split("?")[0] in ("/ws", "/"):
            await ws_session(reader, writer, headers)
            return

        route = path.split("?")[0]
        if method == "OPTIONS":
            await respond(writer, 204)
        elif method == "GET" and route == "/info":
            await respond(writer, 200, json.dumps(info(), ensure_ascii=False), "application/json")
        elif method == "GET" and route == "/":
            await respond(writer, 200, f"bichod v{META['version']} corriendo. WebSocket en /ws.\n")
        elif method == "POST" and route == "/update":
            n = int(headers.get("content-length", "0") or 0)
            if n <= 0:
                await respond(writer, 400, "falta el paquete (.tar.gz) en el cuerpo")
                return
            if n > MAX_PACKAGE:
                await respond(writer, 413, "paquete demasiado grande")
                return
            data = await reader.readexactly(n)
            await send_log(f"recibiendo actualización ({n // 1024} KB)")
            try:
                version = await asyncio.get_running_loop().run_in_executor(None, install_release, data)
            except Exception as e:
                await send_log(f"no se pudo instalar: {e}", "error")
                await respond(writer, 400, f"FALLO: {e}")
                return
            await send_log(f"v{version} instalada, reiniciando")
            await respond(writer, 200, f"OK, reiniciando con v{version}")
            asyncio.get_running_loop().call_later(0.4, restart)
        else:
            await respond(writer, 404, "bichod: no existe")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, asyncio.TimeoutError):
        pass
    except Exception:
        traceback.print_exc()
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def ws_session(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, headers: dict) -> None:
    key = headers.get("sec-websocket-key", "")
    accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
    writer.write(
        ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode()
    )
    await writer.drain()
    ws = WebSocket(reader, writer)
    clients.add(ws)
    peer = writer.get_extra_info("peername")
    log(f"cliente conectado: {peer}")
    try:
        await ws.send(json.dumps(info(), ensure_ascii=False))
        while True:
            msg = await ws.recv()
            if msg is None:
                break
            for line in msg.split("\n"):
                if line.strip():
                    await handle_cmd(line.strip(), ws)
    except (asyncio.IncompleteReadError, ConnectionError, asyncio.TimeoutError):
        pass
    finally:
        clients.discard(ws)
        log(f"cliente desconectado: {peer}")


# ---------------------------------------------------------------------------
# Bucles
# ---------------------------------------------------------------------------


async def sensor_loop() -> None:
    last_err = 0.0
    while True:
        t0 = time.monotonic()
        if clients:
            try:
                d = sensores.leer()
            except Exception as e:  # un sensor desconectado no debe botar el agente
                d = {}
                if time.monotonic() - last_err > 5:
                    last_err = time.monotonic()
                    await send_log(f"error leyendo sensores: {e!r}", "error")
            await broadcast({"t": "s", "ms": int((time.time() - START) * 1000), "d": d})
        await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))


async def info_loop() -> None:
    while True:
        await asyncio.sleep(10)
        await broadcast(info())


async def main() -> None:
    server = await asyncio.start_server(handle_conn, host="0.0.0.0", port=PORT, reuse_address=True)
    log(f"v{META['version']} escuchando en http://{_ip()}:{PORT} (WebSocket en /ws) · releases en {RELEASES}")
    async with server:
        await asyncio.gather(server.serve_forever(), sensor_loop(), info_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
