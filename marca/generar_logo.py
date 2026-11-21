#!/usr/bin/env python3
"""Genera los logos de Bicho en marca/logo/ (SVG). Solo usa la librería estándar.

El ojo es el anillo de 24 LEDs con la cámara al medio, como en el robot, con una curita
que parcha el anillo: el bicho que se parcha solo. La palabra está dibujada a mano con
trazos de punta redonda; la «o» lleva el mismo lente que el ojo.

Uso: python3 marca/generar_logo.py   (después, marca/exportar_png.sh para los PNG)
"""
import math
from pathlib import Path

# Colores de «Cristal claro», el estilo de bicho·dev.
CARBON = "#1D1D1F"   # tinta de bicho·dev
MENTA = "#8FDCC4"    # piezas impresas del robot: la pupila
SALMON = "#F4996F"   # parachoques del robot, y el color de una curita
PAD = "#FFD4BF"      # gasa de la curita
LUZ = "#FFF4E0"      # luz del anillo en reposo
BLANCO = "#FFFFFF"
BANANA = ("#FFE46B", "#FFC700", "#FFAD00")  # el degradé del ícono de bicho·dev
FONDO_CRISTAL = ("#FDF4EC", "#F8F1F2", "#EEF2FB")  # el fondo de pantalla de bicho·dev
MANCHAS = (  # las manchas de color del fondo: color, centro y radios en un cuadro de 1000 × 1000
    ("#FFC6A0", 150, 70, 310, 270), ("#FFE57A", 530, 20, 230, 200), ("#B4DBFF", 910, 330, 270, 250),
    ("#D8C8FF", 300, 570, 280, 230), ("#FFD9BD", 730, 530, 170, 150),
)

SALIDA = Path(__file__).parent / "logo"

# Colores según el fondo. Fondo claro es el principal (vidrio y crema de bicho·dev);
# fondo oscuro queda para pantallas negras. La curita se despega del anillo con un borde
# del color del fondo.
TEMAS = {
    "fondo-oscuro": {"fondo": CARBON, "puntos": MENTA, "lente": MENTA, "pupila": CARBON, "brillo": LUZ, "letras": LUZ},
    "fondo-claro": {"fondo": BLANCO, "puntos": CARBON, "lente": CARBON, "pupila": MENTA, "brillo": BLANCO, "letras": CARBON},
}


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


# ---------- El ojo parchado (240 × 240) ----------

def ojo(t, borde=None, simple=False):
    """Isotipo centrado en (120, 120). `borde` es el color que separa la curita del anillo.
    `simple` dibuja el anillo continuo, para tamaños de 32 px o menos (favicon)."""
    c, R, r_led = 120, 86, 8.2
    partes = []
    if simple:
        partes.append(f'<circle cx="{c}" cy="{c}" r="{R}" fill="none" stroke="{t["puntos"]}" stroke-width="20"/>')
    for i in range(0 if simple else 24):
        a = math.radians(-90 + i * 15)
        partes.append(f'<circle cx="{f(c + R * math.cos(a))}" cy="{f(c + R * math.sin(a))}" r="{r_led}" fill="{t["puntos"]}"/>')
    partes.append(lente(c, c, 1.0, t))
    partes.append(curita(c + R * math.cos(math.radians(-45)), c + R * math.sin(math.radians(-45)), 45, 1.0, borde or t["fondo"]))
    return "\n  ".join(partes)


def lente(x, y, s, t):
    return (
        f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(34 * s)}" fill="{t["lente"]}"/>'
        f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(15 * s)}" fill="{t["pupila"]}"/>'
        f'<circle cx="{f(x + 6.5 * s)}" cy="{f(y - 6.5 * s)}" r="{f(5 * s)}" fill="{t["brillo"]}"/>'
    )


def curita(x, y, giro, s, borde):
    """Curita centrada en (x, y), girada `giro` grados. El borde la despega del anillo."""
    largo, alto = 120 * s, 42 * s
    hoyos = []
    for dx in (-44, -34, 34, 44):
        for dy in (-7, 7):
            hoyos.append(f'<circle cx="{f(dx * s)}" cy="{f(dy * s)}" r="{f(2.3 * s)}" fill="{CARBON}" fill-opacity=".28"/>')
    return (
        f'<g transform="translate({f(x)} {f(y)}) rotate({giro})">'
        f'<rect x="{f(-largo / 2)}" y="{f(-alto / 2)}" width="{f(largo)}" height="{f(alto)}" rx="{f(alto / 2)}" '
        f'fill="{SALMON}" stroke="{borde}" stroke-width="{f(7 * s)}" paint-order="stroke"/>'
        f'<rect x="{f(-20 * s)}" y="{f(-14 * s)}" width="{f(40 * s)}" height="{f(28 * s)}" rx="{f(6 * s)}" fill="{PAD}"/>'
        + "".join(hoyos)
        + "</g>"
    )


# ---------- La palabra «bicho» ----------
# Altura x = 100 (y de 0 a 100), trazo de 22 con punta redonda, panzas de radio 39.
# Ascendente hasta y = -60; «bicho» no tiene descendentes.

S, R, H = 22, 39, 11  # trazo, radio de las panzas, medio trazo
POS = {"b": 0, "i": 120, "c": 162, "h": 267, "o": 387}
ANCHO_PALABRA = 487


def palabra(t, con_lente=True):
    trazos = []
    x = POS["b"]
    trazos.append(f"M{f(x + H)} {-60 + H}V{100 - H}")
    trazos.append(circulo(x + 50, 50))
    x = POS["i"]
    trazos.append(f"M{f(x + H)} {H}V{100 - H}")
    x = POS["c"]
    k = R * math.cos(math.radians(45))
    trazos.append(f"M{f(x + 50 + k)} {f(50 - k)}A{R} {R} 0 1 0 {f(x + 50 + k)} {f(50 + k)}")
    x = POS["h"]
    trazos.append(f"M{f(x + H)} {-60 + H}V{100 - H}")
    trazos.append(f"M{f(x + H)} 50A{R} {R} 0 0 1 {f(x + 100 - H)} 50V{100 - H}")
    x = POS["o"]
    trazos.append(circulo(x + 50, 50))
    d = "".join(trazos)
    svg = f'<path d="{d}" fill="none" stroke="{t["letras"]}" stroke-width="{S}" stroke-linecap="round" stroke-linejoin="round"/>'
    # El punto de la «i».
    svg += f'<circle cx="{POS["i"] + H}" cy="-38" r="12.5" fill="{t["letras"]}"/>'
    if con_lente:
        # La «o» es el ojo: lleva el lente al medio.
        svg += f'<circle cx="{POS["o"] + 50}" cy="50" r="13" fill="{SALMON}"/>'
    return svg


def circulo(cx, cy):
    return f"M{f(cx - R)} {f(cy)}a{R} {R} 0 1 0 {2 * R} 0a{R} {R} 0 1 0 {-2 * R} 0"


# ---------- Armados ----------

def doc(ancho, alto, cuerpo, vb=None, titulo="Bicho"):
    vb = vb or f"0 0 {ancho} {alto}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{ancho}" height="{alto}" role="img" aria-label="{titulo}">\n'
        f"  <title>{titulo}</title>\n  {cuerpo}\n</svg>\n"
    )


def icono(simple=False, sufijo="i"):
    """Cuadrado redondeado de 240 con el degradé banana de bicho·dev y el ojo encima."""
    t = TEMAS["fondo-claro"]
    esc = 0.86 if simple else 0.8
    corrida = (240 - 240 * esc) / 2
    return (
        f'<defs><linearGradient id="banana-{sufijo}" x1="0.33" y1="0" x2="0.67" y2="1">'
        f'<stop offset="0" stop-color="{BANANA[0]}"/><stop offset="0.52" stop-color="{BANANA[1]}"/>'
        f'<stop offset="1" stop-color="{BANANA[2]}"/></linearGradient></defs>'
        f'<rect width="240" height="240" rx="54" fill="url(#banana-{sufijo})"/>'
        f'<rect x="1.5" y="1.5" width="237" height="237" rx="52.5" fill="none" stroke="{BLANCO}" stroke-opacity=".55" stroke-width="3"/>'
        f'<g transform="translate({f(corrida - 6)} {f(corrida + 6)}) scale({esc})">{ojo(t, simple=simple)}</g>'
    )


def fondo_cristal(lado):
    """El fondo de pantalla de bicho·dev: crema con manchas de color difusas."""
    k = lado / 1000
    defs = (
        '<defs><linearGradient id="crema" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{FONDO_CRISTAL[0]}"/><stop offset="0.46" stop-color="{FONDO_CRISTAL[1]}"/>'
        f'<stop offset="1" stop-color="{FONDO_CRISTAL[2]}"/></linearGradient>'
        + "".join(
            f'<radialGradient id="mancha{i}"><stop offset="0" stop-color="{c}"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
            for i, (c, *_rest) in enumerate(MANCHAS)
        )
        + "</defs>"
    )
    manchas = "".join(
        f'<ellipse cx="{f(cx * k)}" cy="{f(cy * k)}" rx="{f(rx * k)}" ry="{f(ry * k)}" fill="url(#mancha{i})"/>'
        for i, (_c, cx, cy, rx, ry) in enumerate(MANCHAS)
    )
    return defs + f'<rect width="{lado}" height="{lado}" fill="url(#crema)"/>' + manchas


def main():
    SALIDA.mkdir(exist_ok=True)
    archivos = {}
    for nombre, t in TEMAS.items():
        # Isotipo sin fondo (la curita se despega con el color del fondo para el que está hecho).
        archivos[f"bicho-ojo-{nombre}.svg"] = doc(240, 240, ojo(t))
        # Palabra sola: de la ascendente (y = -60) a la línea base (y = 100).
        archivos[f"bicho-palabra-{nombre}.svg"] = doc(
            ANCHO_PALABRA + 40, 200, f'<g transform="translate(20 80)">{palabra(t)}</g>'
        )
        # Horizontal: el ojo (200 de alto) centrado en la altura de la palabra.
        cuerpo = (
            f'<g transform="translate(20 20) scale({f(200 / 240)})">{ojo(t)}</g>'
            f'<g transform="translate(270 100)">{palabra(t)}</g>'
        )
        archivos[f"bicho-horizontal-{nombre}.svg"] = doc(270 + ANCHO_PALABRA + 20, 240, cuerpo)

    # Ícono de app: el ojo sobre el cuadrado amarillo de bicho·dev. El favicon lleva el anillo continuo.
    archivos["bicho-icono.svg"] = doc(240, 240, icono(sufijo="i"))
    archivos["favicon.svg"] = doc(240, 240, icono(simple=True, sufijo="f"))

    # Cuadrado de 1000 × 1000 para Platanus: fondo de bicho·dev, el ícono y la palabra.
    t = TEMAS["fondo-claro"]
    lado, esc_pal, entre = 440, 1.05, 90
    arriba = (1000 - (lado + entre + 160 * esc_pal)) / 2
    ancho_pal = ANCHO_PALABRA * esc_pal
    cuerpo = (
        fondo_cristal(1000)
        + '<defs><filter id="sombra" x="-30%" y="-30%" width="160%" height="170%">'
        '<feDropShadow dx="0" dy="24" stdDeviation="28" flood-color="#E69600" flood-opacity=".35"/></filter></defs>'
        f'<g filter="url(#sombra)" transform="translate({f(500 - lado / 2)} {f(arriba)}) scale({f(lado / 240)})">{icono(sufijo="c")}</g>'
        f'<g transform="translate({f(500 - ancho_pal / 2)} {f(arriba + lado + entre + 60 * esc_pal)}) scale({esc_pal})">{palabra(t)}</g>'
    )
    archivos["bicho-cuadrado.svg"] = doc(1000, 1000, cuerpo)

    for nombre, contenido in archivos.items():
        (SALIDA / nombre).write_text(contenido)
        print("escrito", SALIDA / nombre)


if __name__ == "__main__":
    main()
