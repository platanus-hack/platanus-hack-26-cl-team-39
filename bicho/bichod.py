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
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


# ---------------------------------------------------------------------------
# Vuelta atrás: una versión recién instalada está "a prueba" hasta que demuestra que funciona
# ---------------------------------------------------------------------------
# install_release() deja prueba.json con la versión anterior. Si la nueva no logra cargar sus
# módulos, se cae 3 veces seguidas o no confirma en 60 s, el bicho vuelve solo a la anterior.
# Va antes de cargar comandos.py y sensores.py, que son los archivos que cambian al aprender.


def _casa() -> Path:
    if os.environ.get("BICHO_HOME"):
        return Path(os.environ["BICHO_HOME"])
    opt = Path("/opt/bicho")
    return opt if opt.exists() and os.access(opt, os.W_OK) else Path.home() / ".bicho"


_PRUEBA = _casa() / "prueba.json"


def _a_prueba() -> dict | None:
    try:
        p = json.loads(_PRUEBA.read_text(encoding="utf-8"))
        return p if p.get("nueva") == HERE.name else None
    except (OSError, ValueError):
        return None


def volver_atras(motivo: str) -> None:
    """Apunta current a la versión anterior y se reinicia con ella."""
    p = _a_prueba()
    casa = _casa()
    anterior = casa / "releases" / str((p or {}).get("anterior", ""))
    try:
        _PRUEBA.unlink()
    except OSError:
        pass
    if not p or not (anterior / "bichod.py").exists():
        return
    print(f"[bichod] VUELTA ATRÁS a v{anterior.name}: {motivo}", flush=True)
    (casa / "vuelta-atras.json").write_text(json.dumps({"de": HERE.name, "a": anterior.name, "motivo": motivo[-600:], "cuando": time.time()}), encoding="utf-8")
    tmp = casa / "current.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(Path("releases") / anterior.name, tmp)
    os.replace(tmp, casa / "current")
    os.execv(sys.executable, [sys.executable, str(anterior / "bichod.py")])


_p = _a_prueba()
if _p:
    _p["arranques"] = int(_p.get("arranques", 0)) + 1
    if _p["arranques"] > 3:
        volver_atras("la versión nueva se reinició más de 3 veces sin confirmar")
    else:
        _PRUEBA.write_text(json.dumps(_p), encoding="utf-8")

try:
    import comandos  # noqa: E402
    import oido  # noqa: E402
    import salida  # noqa: E402
    import sensores  # noqa: E402
except Exception:
    if _a_prueba():
        volver_atras("no cargaron los módulos: " + traceback.format_exc())
    raise

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


_red_cache: tuple[float, str | None] = (0.0, None)


def _red() -> str | None:
    """A qué red está conectado el bicho, p. ej. "WiFi: MiRed" o "WiFi: MiRed + cable"."""
    global _red_cache
    if time.time() - _red_cache[0] < 8:
        return _red_cache[1]
    red = None
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-e", "no", "-f", "TYPE,STATE,CONNECTION", "dev"], capture_output=True, text=True, timeout=2
        ).stdout
        partes = []
        for line in out.splitlines():
            tipo, estado, nombre = (line.split(":", 2) + ["", ""])[:3]
            if estado != "connected":
                continue
            if tipo == "wifi":
                partes.insert(0, f"WiFi: {nombre}")
            elif tipo == "ethernet":
                partes.append("cable")
        red = " + ".join(partes) or "sin red"
    except (OSError, subprocess.SubprocessError):
        pass  # sin nmcli (por ejemplo en un computador): no se informa
    _red_cache = (time.time(), red)
    return red


def _mem_available() -> int | None:
    txt = _read("/proc/meminfo")
    if txt:
        m = re.search(r"MemAvailable:\s+(\d+)\s*kB", txt)
        if m:
            return int(m.group(1)) * 1024
    return None


def _ultima_vuelta_atras() -> dict | None:
    """Si hace poco una versión nueva falló y se volvió a la anterior, cuál y por qué."""
    try:
        v = json.loads((HOME / "vuelta-atras.json").read_text(encoding="utf-8"))
        return {"de": v.get("de"), "motivo": v.get("motivo")} if time.time() - float(v.get("cuando", 0)) < 600 else None
    except (OSError, ValueError):
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
        "red": _red(),
        "vuelta_atras": _ultima_vuelta_atras(),
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
        self.max_msg = 1024 * 1024

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
            if n > self.max_msg:
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
    elif cmd == "diag":
        d = await asyncio.get_running_loop().run_in_executor(None, _diag)
        await broadcast({"t": "diag", "id": c.get("id"), "d": d})
    elif cmd == "fuente":
        await broadcast({"t": "fuente", "id": c.get("id"), "version": META["version"], "archivos": _fuente()})
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


# Qué hardware ve el Pi. Son comandos fijos, de solo lectura: el cerebro los usa antes de aprender algo.
_DIAG = {
    "usb": "lsusb",
    "video": "ls -l /dev/video* 2>&1 | head -20",
    "camaras_v4l2": "v4l2-ctl --list-devices 2>&1 | head -40",
    "camaras_csi": "(rpicam-hello --list-cameras || libcamera-hello --list-cameras) 2>&1 | head -30",
    "microfonos": "arecord -l 2>&1 | head -12",
    "parlantes": "aplay -l 2>&1 | grep '^card' | head -8",
    "i2c": "ls /dev/i2c-* 2>&1",
    "programas": "for p in ffmpeg rpicam-still rpicam-jpeg libcamera-still fswebcam v4l2-ctl pinctrl aplay; do printf '%s: ' $p; command -v $p || echo no; done",
    "python": "python3 -c \"import importlib.util as u; print({m: bool(u.find_spec(m)) for m in ['picamera2','cv2','PIL','numpy','gpiozero','smbus2','usb','serial']})\"",
    "gpio_libre": "pinctrl get 2-27 2>&1 | head -30",
}


def _diag() -> dict:
    out = {}
    for nombre, cmd in _DIAG.items():
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            out[nombre] = (r.stdout + r.stderr).strip()[:1500]
        except subprocess.TimeoutExpired:
            out[nombre] = "(tardó más de 10 s)"
    return out


def _fuente() -> dict:
    """El código que está corriendo, para que el cerebro edite exactamente lo instalado."""
    out = {}
    for f in sorted(HERE.iterdir()):
        if f.is_file() and f.suffix in (".py", ".json", ".txt", ".md") and f.stat().st_size < 120_000:
            out[f.name] = f.read_text(encoding="utf-8", errors="replace")
    return out


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
    _probar_antes_de_activar(tmp)

    anterior = CURRENT.resolve().name if CURRENT.exists() else HERE.name
    if anterior != version and (RELEASES / anterior / "bichod.py").exists():
        _PRUEBA.write_text(json.dumps({"nueva": version, "anterior": anterior, "arranques": 0}), encoding="utf-8")

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


def _probar_antes_de_activar(nuevo: Path) -> None:
    """Si el código nuevo no compila o sus módulos no cargan, no se instala: se queda la versión actual."""
    for f in sorted(nuevo.glob("*.py")):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(f)], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise ValueError(f"{f.name} no compila: {(r.stderr or r.stdout).strip()[-500:]}")
    prueba = (
        "import sys, json; sys.path.insert(0, sys.argv[1]); import comandos, sensores; "
        "d = sensores.leer(); assert isinstance(d, dict), 'sensores.leer() debe devolver un dict'; json.dumps(d); "
        "r = comandos.manejar({'cmd': 'hola'}); assert r is None or isinstance(r, str), 'manejar() debe devolver str o None'"
    )
    env = {**os.environ, "BICHO_SIMULAR": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        r = subprocess.run([sys.executable, "-c", prueba, str(nuevo)], capture_output=True, text=True, timeout=30, env=env)
    except subprocess.TimeoutExpired:
        raise ValueError("cargar comandos.py y sensores.py tardó más de 30 s: algo bloquea al importar")
    if r.returncode != 0:
        raise ValueError(f"los módulos nuevos fallan al cargar: {(r.stderr or r.stdout).strip()[-700:]}")


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
# Relé: el bicho sale a conectarse a la web publicada, para que lo vean desde cualquier red
# ---------------------------------------------------------------------------
#
# El bicho no tiene dirección pública, así que no se le puede "llamar" desde internet. En vez de eso
# abre él una conexión al relé (rele/servidor.mjs) y la deja abierta; la web habla con el relé.
# Se configura en $BICHO_HOME/rele.json → {"url": "https://<relé>", "token": "<secreto>"}
# o con las variables BICHO_RELE_URL y BICHO_RELE_TOKEN. Sin configuración, no se usa.


class WebSocketCliente(WebSocket):
    """Lado cliente: las tramas que salen van enmascaradas (RFC 6455)."""

    @staticmethod
    def frame(opcode: int, payload: bytes) -> bytes:
        n = len(payload)
        head = bytes([0x80 | opcode])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + n.to_bytes(2, "big")
        else:
            head += bytes([0x80 | 127]) + n.to_bytes(8, "big")
        mask = os.urandom(4)
        if n:
            largo = mask * (n // 4 + 1)
            payload = (int.from_bytes(payload, "big") ^ int.from_bytes(largo[:n], "big")).to_bytes(n, "big")
        return head + mask + payload


rele_ws: WebSocketCliente | None = None


def _rele_cfg() -> tuple[str, str] | None:
    url, token = os.environ.get("BICHO_RELE_URL", ""), os.environ.get("BICHO_RELE_TOKEN", "")
    try:
        cfg = json.loads((HOME / "rele.json").read_text(encoding="utf-8"))
        url, token = url or str(cfg.get("url", "")), token or str(cfg.get("token", ""))
    except (OSError, ValueError):
        pass
    url = url.strip().rstrip("/")
    if not url:
        return None
    if url.startswith("http"):  # se acepta la dirección tal cual: https://relé → wss://relé/bicho
        url = "ws" + url[4:]
    if not url.endswith("/bicho"):
        url += "/bicho"
    return url, token.strip()


async def _rele_sesion(url: str, token: str) -> None:
    global rele_ws
    m = re.match(r"^(wss?)://([^/:]+)(?::(\d+))?(/.*)?$", url)
    if not m:
        raise ValueError(f"dirección del relé inválida: {url}")
    seguro, host = m.group(1) == "wss", m.group(2)
    port = int(m.group(3) or (443 if seguro else 80))
    path = m.group(4) or "/bicho"
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=ssl.create_default_context() if seguro else None, server_hostname=host if seguro else None),
        timeout=15,
    )
    ws: WebSocketCliente | None = None
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        writer.write(
            (
                f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nAuthorization: Bearer {token}\r\n"
                f"User-Agent: bichod/{META['version']}\r\n\r\n"
            ).encode()
        )
        await writer.drain()
        head = (await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)).decode("latin-1")
        estado = head.split("\r\n")[0]
        if " 101 " not in estado:
            raise ConnectionError(f"el relé respondió: {estado}")
        ws = WebSocketCliente(reader, writer)
        ws.max_msg = MAX_PACKAGE * 2  # los paquetes de actualización llegan en base64
        rele_ws = ws
        log(f"conectado al relé {host}")
        confirmar_version()
        await ws.send(json.dumps(info(), ensure_ascii=False))
        while True:
            # el relé manda un latido cada 20 s: si pasa un minuto sin nada, la conexión está muerta
            msg = await asyncio.wait_for(ws.recv(), timeout=60)
            if msg is None:
                break
            for line in msg.split("\n"):
                if line.strip():
                    await _rele_linea(line.strip(), ws)
    finally:
        rele_ws = None
        clients.discard(ws)
        try:
            writer.close()
        except Exception:
            pass


async def _rele_linea(line: str, ws: WebSocketCliente) -> None:
    try:
        c = json.loads(line)
    except ValueError:
        c = None
    cmd = c.get("cmd") if isinstance(c, dict) else None
    if cmd == "_espectadores":
        # los sensores solo viajan mientras alguien mira la web
        if int(c.get("n", 0) or 0) > 0:
            clients.add(ws)
        else:
            clients.discard(ws)
    elif cmd == "_update":
        await _rele_update(c, ws)
    else:
        await handle_cmd(line, ws)


async def _rele_update(c: dict, ws: WebSocketCliente) -> None:
    def responder(ok: bool, msg: str) -> str:
        return json.dumps({"t": "_update", "id": c.get("id"), "ok": ok, "msg": msg}, ensure_ascii=False)

    try:
        data = base64.b64decode(c.get("b64", ""), validate=True)
        if not data or len(data) > MAX_PACKAGE:
            raise ValueError("paquete vacío o demasiado grande")
        await send_log(f"recibiendo actualización por el relé ({len(data) // 1024} KB)")
        version = await asyncio.get_running_loop().run_in_executor(None, install_release, data)
    except Exception as e:
        await send_log(f"no se pudo instalar: {e}", "error")
        await ws.send(responder(False, f"FALLO: {e}"))
        return
    await send_log(f"v{version} instalada, reiniciando")
    await ws.send(responder(True, f"OK, reiniciando con v{version}"))
    asyncio.get_running_loop().call_later(0.6, restart)


async def rele_loop() -> None:
    cfg = _rele_cfg()
    if not cfg:
        log("relé sin configurar (rele.json o BICHO_RELE_URL): solo se atiende la red local")
        return
    url, token = cfg
    espera, ultimo = 1.0, ""
    while True:
        t0 = time.monotonic()
        try:
            await _rele_sesion(url, token)
            err = "el relé cerró la conexión"
        except Exception as e:
            err = str(e) or type(e).__name__
        if time.monotonic() - t0 > 30:
            espera, ultimo = 1.0, ""
        if err != ultimo:  # el mismo error no se repite en el registro
            log(f"relé: {err}; reintentando")
            ultimo = err
        await asyncio.sleep(espera)
        espera = min(espera * 2, 15)


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


_confirmada = False


def confirmar_version() -> None:
    """La versión nueva demostró que funciona: deja de estar a prueba."""
    global _confirmada
    _confirmada = True
    try:
        _PRUEBA.unlink()
    except OSError:
        pass


def _vigilar_version() -> None:
    """Hilo aparte (por si el código nuevo bloquea el bucle principal): a los 60 s sin confirmar, vuelta atrás."""
    if not _a_prueba():
        return
    con_rele = _rele_cfg() is not None

    def revisar() -> None:
        if _confirmada or not _a_prueba():
            return
        if con_rele:
            volver_atras("la versión nueva no logró conectarse al relé en 60 s")
        else:
            confirmar_version()  # sin relé, basta con haber durado un minuto arriba

    t = threading.Timer(60, revisar)
    t.daemon = True
    t.start()


async def salida_loop() -> None:
    """Reparte lo que los módulos emiten con salida.emitir() (imágenes de la cámara, etc.)."""
    while True:
        await asyncio.sleep(0.05)
        salida._marcar_publico(bool(clients))
        for m in salida._recoger():
            if isinstance(m, dict) and isinstance(m.get("t"), str) and not m["t"].startswith("_"):
                await broadcast(m)


async def oido_loop() -> None:
    """Recoge las frases que escuchó el ReSpeaker. El audio va solo al relé, que lo transcribe."""
    oido.partir()
    n = 0
    while True:
        await asyncio.sleep(0.2)
        for f in oido.frases():
            n += 1
            base = {"id": f"{int(START)}-{n}", "angulo": f["angulo"], "dur": f["dur"]}
            log(f"oí una frase de {f['dur']} s desde {f['angulo']}°")
            aviso = json.dumps({"t": "oido", **base}, ensure_ascii=False)
            for ws in list(clients):  # conexiones directas: saben que se oyó algo, sin transcripción
                if ws is not rele_ws:
                    try:
                        await ws.send(aviso)
                    except Exception:
                        clients.discard(ws)
            if rele_ws:
                try:
                    await rele_ws.send(json.dumps({"t": "_voz", **base, "fmt": f["fmt"], "b64": base64.b64encode(f["audio"]).decode()}))
                except Exception:
                    pass


async def info_loop() -> None:
    while True:
        await asyncio.sleep(10)
        await broadcast(info())
        if rele_ws and rele_ws not in clients:  # el relé guarda la última info aunque nadie esté mirando
            try:
                await rele_ws.send(json.dumps(info(), ensure_ascii=False))
            except Exception:
                pass


async def main() -> None:
    _vigilar_version()
    server = await asyncio.start_server(handle_conn, host="0.0.0.0", port=PORT, reuse_address=True)
    log(f"v{META['version']} escuchando en http://{_ip()}:{PORT} (WebSocket en /ws) · releases en {RELEASES}")
    async with server:
        await asyncio.gather(server.serve_forever(), sensor_loop(), info_loop(), rele_loop(), oido_loop(), salida_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
