"""
Herramientas de software del bicho: saber qué comandos tiene, buscar en su propio código,
ver qué programas y módulos hay instalados, y crear notas de texto que sobreviven a las versiones.

Todo es liviano y acotado a propósito:
  - Lo de buscar/ver/archivos/herramientas es de SOLO LECTURA y se limita a la carpeta del código
    (lo mismo que ya entrega el comando "fuente" de bichod.py) y a las notas.
  - Lo de crear se limita a notas de texto en <casa del bicho>/notas (nombre simple, tamaño y
    cantidad con tope). No ejecuta nada, no instala nada, no toca el sistema ni necesita root.
  - Nada corre al importar, nada deja hilos ni procesos andando, y no se usa subprocess.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

_SUFIJOS = (".py", ".json", ".txt", ".md")
_MAX_ARCHIVO = 300_000  # bytes: archivos más grandes no se leen
_MAX_SALIDA = 1800  # caracteres por respuesta en la consola

_NOTA_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_MAX_NOTA = 20_000  # bytes por nota
_MAX_NOTAS = 100

_NOMBRE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]{0,39}$")
_PROGRAMAS = (
    "python3", "pip3", "git", "curl", "wget", "ffmpeg", "rpicam-still", "rpicam-jpeg", "v4l2-ctl",
    "pinctrl", "aplay", "arecord", "i2cdetect", "nmcli", "gcc", "make", "node", "espeak-ng", "sox",
)
_MODULOS = (
    "picamera2", "cv2", "PIL", "numpy", "gpiozero", "smbus2", "spidev", "usb", "serial", "lgpio",
    "RPi", "pigpio", "requests", "scipy", "yaml",
)

# Qué comandos existen. Al aprender un comando nuevo, agregarlo aquí para que "ayuda" lo cuente.
AYUDA = {
    "hola": '{"cmd":"hola"}  saluda',
    "info": '{"cmd":"info"}  versión, placa, IP y red (lo resuelve bichod)',
    "rate": '{"cmd":"rate","hz":20}  cuántas veces por segundo manda sensores (bichod)',
    "reboot": '{"cmd":"reboot"}  reinicia el agente (bichod)',
    "luz": '{"cmd":"luz","on":true|false}  ·  "blink":5,"t":0.5   luz del GPIO 17',
    "verde": '{"cmd":"verde"}  ·  "on":true|false  ·  "blink":5,"t":0.5   luz verde (GPIO 27)',
    "rojo": '{"cmd":"rojo"}  ·  "on":true|false  ·  "blink":5,"t":0.5   luz roja (GPIO 22)',
    "si": '{"cmd":"si"}  responde sí con la luz verde ("seg": cuánto dura)',
    "no": '{"cmd":"no"}  responde no con la luz roja ("seg": cuánto dura)',
    "responder": '{"cmd":"responder","r":"si"|"no"}  igual que si / no',
    "luces": '{"cmd":"luces"}  cómo están  ·  "on":false apaga verde y roja',
    "camara": '{"cmd":"camara"}  estado  ·  "on":true manda una imagen por segundo a Vista  ·  "on":false',
    "foto": '{"cmd":"foto"}  una sola foto a Vista',
    "flujo": '{"cmd":"flujo"}  una lectura del ADNS-3080 (spidev0.0)  ·  "on":true|false  ·  "reset":true',
    "flujo2": '{"cmd":"flujo2"}  segundo ADNS-3080 (spidev0.1)  ·  "on"  ·  "reset"  ·  "pines":true',
    "flujos": '{"cmd":"flujos"}  los dos sensores de flujo a la vez  ·  "on"  ·  "reset"',
    "ayuda": '{"cmd":"ayuda"}  lista de comandos  ·  "de":"camara" cómo se usa uno',
    "archivos": '{"cmd":"archivos"}  qué archivos de código tiene el bicho (tamaño y líneas)',
    "buscar": '{"cmd":"buscar","q":"GPIO"}  busca un texto en su código y sus notas  ·  "en":"luz.py" o "en":"notas"  ·  "max":20',
    "ver": '{"cmd":"ver","archivo":"luz.py","desde":1,"n":20}  muestra líneas de un archivo de su código',
    "herramientas": '{"cmd":"herramientas"}  programas y módulos de Python disponibles  ·  "q":"git" pregunta por uno',
    "nota": '{"cmd":"nota","nombre":"ideas","texto":"..."}  crea o reemplaza  ·  "agregar":true añade  ·  sin texto la lee  ·  "borrar":true',
    "notas": '{"cmd":"notas"}  lista las notas guardadas',
}

COMANDOS = ("ayuda", "archivos", "buscar", "ver", "herramientas", "nota", "notas")


def _cortar(txt: str, n: int = _MAX_SALIDA) -> str:
    return txt if len(txt) <= n else txt[: n - 20].rstrip() + "\n… (cortado)"


def _entero(v, defecto: int, lo: int, hi: int) -> int:
    try:
        x = int(float(v))
    except (TypeError, ValueError, OverflowError):
        x = defecto
    return max(lo, min(x, hi))


# ── ayuda ─────────────────────────────────────────────────────────────────────


def ayuda(de=None) -> str:
    if de:
        k = str(de).strip().lower()
        k = {"sí": "si", "roja": "rojo"}.get(k, k)
        if k in AYUDA:
            return f"{k}: {AYUDA[k]}"
        return f"ayuda: no conozco el comando {k[:40]!r}. Comandos: " + ", ".join(AYUDA)
    return 'comandos: ' + ", ".join(AYUDA) + '. Detalle de uno: {"cmd":"ayuda","de":"buscar"}'


# ── código propio: archivos, ver, buscar (solo lectura) ───────────────────────


def _codigo() -> list[Path]:
    out = []
    try:
        for f in sorted(HERE.iterdir()):
            if f.is_file() and f.suffix in _SUFIJOS and not f.name.startswith("."):
                out.append(f)
    except OSError:
        pass
    return out


def _leer(f: Path) -> str | None:
    try:
        if f.stat().st_size > _MAX_ARCHIVO:
            return None
        return f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def archivos() -> str:
    partes = []
    for f in _codigo():
        txt = _leer(f)
        try:
            kb = f.stat().st_size / 1024
        except OSError:
            continue
        lineas = f"{txt.count(chr(10)) + 1} líneas" if txt is not None else "muy grande"
        partes.append(f"{f.name} ({kb:.1f} KB, {lineas})")
    return _cortar(f"{len(partes)} archivos en {HERE.name}: " + ", ".join(partes))


def _archivo_propio(nombre) -> Path | None:
    nombre = str(nombre or "").strip()
    if not nombre or Path(nombre).name != nombre or nombre.startswith("."):
        return None
    f = HERE / nombre
    return f if f.is_file() and f.suffix in _SUFIJOS else None


def ver(nombre, desde=1, n=20) -> str:
    f = _archivo_propio(nombre)
    if f is None:
        return "ver: ese archivo no está en mi código. Disponibles: " + ", ".join(p.name for p in _codigo())
    txt = _leer(f)
    if txt is None:
        return f"ver: {f.name} es muy grande o no se pudo leer"
    lineas = txt.splitlines()
    desde = _entero(desde, 1, 1, max(1, len(lineas)))
    n = _entero(n, 20, 1, 60)
    trozo = lineas[desde - 1 : desde - 1 + n]
    cuerpo = "\n".join(f"{desde + i:4d}  {l[:160]}" for i, l in enumerate(trozo))
    return _cortar(f"{f.name} líneas {desde}-{desde + len(trozo) - 1} de {len(lineas)}:\n{cuerpo}", 3000)


def buscar(q, en=None, maximo=12) -> str:
    q = str(q or "").strip()
    if len(q) < 2:
        return 'buscar: dime qué buscar, por ejemplo {"cmd":"buscar","q":"GPIO"} (mínimo 2 letras)'
    q = q[:80]
    maximo = _entero(maximo, 12, 1, 30)
    en = str(en or "").strip()

    fuentes: list[tuple[str, Path]] = []
    if en == "notas":
        fuentes = [(f"nota:{f.stem}", f) for f in _notas()]
    elif en:
        f = _archivo_propio(en)
        if f is None:
            return f'buscar: "{en[:40]}" no es un archivo de mi código (usa "en":"notas" para las notas)'
        fuentes = [(f.name, f)]
    else:
        fuentes = [(f.name, f) for f in _codigo()] + [(f"nota:{f.stem}", f) for f in _notas()]

    ql = q.lower()
    total, hallados, donde = 0, [], set()
    for etiqueta, f in fuentes:
        txt = _leer(f)
        if txt is None or ql not in txt.lower():
            continue
        for i, linea in enumerate(txt.splitlines(), 1):
            if ql in linea.lower():
                total += 1
                donde.add(etiqueta)
                if len(hallados) < maximo:
                    hallados.append(f"{etiqueta}:{i}: {linea.strip()[:110]}")
    if not total:
        return f'buscar "{q}": nada en {len(fuentes)} archivos'
    cab = f'buscar "{q}": {total} líneas en {len(donde)} archivos'
    if total > len(hallados):
        cab += f" (muestro {len(hallados)})"
    return _cortar(cab + ":\n" + "\n".join(hallados), 3000)


# ── qué hay instalado (solo mira, no ejecuta nada) ────────────────────────────


def _hay_modulo(nombre: str) -> bool:
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def herramientas(q=None) -> str:
    if q:
        nombre = str(q).strip()
        if not _NOMBRE_RE.match(nombre):
            return "herramientas: el nombre solo puede tener letras, números, guion, punto y guion bajo"
        ruta = shutil.which(nombre)
        partes = [f"programa {nombre}: {ruta or 'no está'}"]
        if nombre.isidentifier():  # solo módulos de primer nivel: find_spec no importa nada
            partes.append(f"módulo de Python {nombre}: {'sí' if _hay_modulo(nombre) else 'no'}")
        return " · ".join(partes)
    si_p = [p for p in _PROGRAMAS if shutil.which(p)]
    no_p = [p for p in _PROGRAMAS if p not in si_p]
    si_m = [m for m in _MODULOS if _hay_modulo(m)]
    no_m = [m for m in _MODULOS if m not in si_m]
    return _cortar(
        "programas: " + (", ".join(si_p) or "ninguno")
        + " | no están: " + (", ".join(no_p) or "ninguno")
        + " || módulos de Python: " + (", ".join(si_m) or "ninguno")
        + " | no están: " + (", ".join(no_m) or "ninguno")
        + ' || para otro: {"cmd":"herramientas","q":"nombre"}'
    )


# ── notas: lo único que este módulo crea ──────────────────────────────────────


def _casa() -> Path:
    """La misma casa que usa bichod.py (ahí viven releases/): las notas no se pierden al actualizar."""
    if os.environ.get("BICHO_HOME"):
        return Path(os.environ["BICHO_HOME"])
    opt = Path("/opt/bicho")
    return opt if opt.exists() and os.access(opt, os.W_OK) else Path.home() / ".bicho"


def _dir_notas() -> Path:
    return _casa() / "notas"


def _notas() -> list[Path]:
    try:
        return sorted(f for f in _dir_notas().iterdir() if f.is_file() and f.suffix == ".txt" and _NOTA_RE.match(f.stem))
    except OSError:
        return []


def notas() -> str:
    fs = _notas()
    if not fs:
        return 'no tengo notas. Para crear una: {"cmd":"nota","nombre":"ideas","texto":"..."}'
    partes = []
    for f in fs:
        try:
            st = f.stat()
            partes.append(f"{f.stem} ({st.st_size} B, {time.strftime('%d-%m %H:%M', time.localtime(st.st_mtime))})")
        except OSError:
            pass
    return _cortar(f"{len(partes)} notas en {_dir_notas()}: " + ", ".join(partes))


def nota(nombre, texto=None, agregar=False, borrar=False) -> str:
    nombre = str(nombre or "").strip().lower()
    if not _NOTA_RE.match(nombre):
        return "nota: el nombre va en minúsculas, con letras sin tilde, números, guion o guion bajo (máximo 40)"
    f = _dir_notas() / f"{nombre}.txt"

    if borrar:
        try:
            f.unlink()
            return f"nota {nombre} borrada"
        except FileNotFoundError:
            return f"nota: no existe {nombre}"
        except OSError as e:
            return f"nota: no pude borrar {nombre}: {e}"

    if texto is None:
        if not f.is_file():
            return f"nota: no existe {nombre}"
        txt = _leer(f)
        return f"nota: no pude leer {nombre}" if txt is None else _cortar(f"nota {nombre}:\n{txt}", 3000)

    if not isinstance(texto, str):
        return 'nota: "texto" tiene que ser un texto'
    existe = f.is_file()
    if agregar and existe:
        previo = _leer(f) or ""
        texto = previo + ("" if previo.endswith("\n") or not previo else "\n") + texto
    if len(texto.encode("utf-8")) > _MAX_NOTA:
        return f"nota: no la guardé, quedaría de más de {_MAX_NOTA // 1000} KB"
    if not existe and len(_notas()) >= _MAX_NOTAS:
        return f"nota: ya hay {_MAX_NOTAS} notas; borra alguna antes de crear otra"
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f".{nombre}.tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, f)
    except OSError as e:
        return f"nota: no pude guardar {nombre}: {e}"
    return f"nota {nombre} {'actualizada' if existe else 'creada'} ({len(texto.encode('utf-8'))} B) en {f.parent}"


# ── entrada desde comandos.py ─────────────────────────────────────────────────


def manejar(c: dict) -> str | None:
    cmd = c.get("cmd")
    if cmd == "ayuda":
        return ayuda(c.get("de"))
    if cmd == "archivos":
        return archivos()
    if cmd == "buscar":
        return buscar(c.get("q"), c.get("en"), c.get("max", 12))
    if cmd == "ver":
        return ver(c.get("archivo"), c.get("desde", 1), c.get("n", 20))
    if cmd == "herramientas":
        return herramientas(c.get("q"))
    if cmd == "notas":
        return notas()
    if cmd == "nota":
        return nota(c.get("nombre"), c.get("texto"), bool(c.get("agregar")), c.get("borrar") is True)
    return None
