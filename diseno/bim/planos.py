# Planos de fabricación por pieza, versionados como un modelo BIM.
# Lee diseno/bim/registro.json y, por cada pieza con STL, dibuja un plano SVG (A4 apaisado, primer diedro ISO E):
# elevación, planta y lateral con aristas visibles (continuas) y ocultas (segmentadas), cotas generales,
# agujeros acotados (Ø), rótulo y cuadro de revisiones. Salida: diseno/bim/planos/<ID>_rev<R>.svg
# Uso (necesita numpy; viene con el Python de Blender):
#   /Applications/Blender.app/Contents/Resources/4.2/python/bin/python3.11 -I diseno/bim/planos.py
import json, os, sys
import numpy as np

BIM = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(BIM))
REG = json.load(open(os.path.join(BIM, "registro.json"), encoding="utf-8"))
OUT = os.path.join(BIM, "planos")
os.makedirs(OUT, exist_ok=True)

W, H = 297.0, 210.0                       # hoja A4 apaisada, mm
FONT = "font-family='Helvetica, Arial, sans-serif'"
INK, HID, DIM, ACC = "#111", "#666", "#1c4fae", "#e9a400"


def load_stl(path):
    d = open(path, "rb").read(); n = int.from_bytes(d[80:84], "little")
    a = np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return a["v"].reshape(-1, 3, 3).astype(np.float64)


def feature_edges(tris, ang=25.0):
    v = np.round(tris.reshape(-1, 3), 3)
    uniq, inv = np.unique(v, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1); ok = ln > 1e-12
    f, nrm = f[ok], nrm[ok] / ln[ok, None]
    edges = {}
    for i, (a, b, c) in enumerate(f):
        for e in ((a, b), (b, c), (c, a)):
            edges.setdefault((min(e), max(e)), []).append(i)
    out, cosa = [], np.cos(np.radians(ang))
    for (a, b), fs in edges.items():
        if len(fs) != 2 or np.dot(nrm[fs[0]], nrm[fs[1]]) < cosa:
            out.append((uniq[a], uniq[b]))
    return np.array(out), uniq


# vistas: (nombre, eje u, eje v, dirección hacia el observador)
VIEWS = {
    "Elevación": (np.array([1, 0, 0]), np.array([0, 0, 1]), np.array([0, -1, 0])),
    "Planta":    (np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])),
    "Lateral":   (np.array([0, 1, 0]), np.array([0, 0, 1]), np.array([1, 0, 0])),
}


def zbuffer(tris, U, V, D, res):
    p = np.stack([tris @ U, tris @ V, tris @ D], axis=-1)          # (n,3,3) -> u,v,d
    umin, vmin = p[..., 0].min(), p[..., 1].min()
    nx = int((p[..., 0].max() - umin) / res) + 3; ny = int((p[..., 1].max() - vmin) / res) + 3
    zb = np.full((ny, nx), -1e9)
    for t in p:
        x = (t[:, 0] - umin) / res; y = (t[:, 1] - vmin) / res
        x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max())) + 1
        y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max())) + 1
        gx, gy = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
        (ax, ay), (bx, by), (cx, cy) = zip(x, y)
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9: continue
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-3) & (w1 >= -1e-3) & (w2 >= -1e-3)
        if not m.any(): continue
        z = w0 * t[0, 2] + w1 * t[1, 2] + w2 * t[2, 2]
        sub = zb[y0:y1, x0:x1]
        sub[m] = np.maximum(sub[m], z[m])
    return zb, umin, vmin


def project(edges, tris, U, V, D):
    res = 0.12
    zb, umin, vmin = zbuffer(tris, U, V, D, res)
    vis, hid = [], []
    for a, b in edges:
        L = np.linalg.norm(b - a); n = max(2, int(L / 0.25))
        t = np.linspace(0, 1, n)[:, None]; P = a + (b - a) * t
        u, v, d = P @ U, P @ V, P @ D
        ix = np.clip(((u - umin) / res).astype(int), 0, zb.shape[1] - 1)
        iy = np.clip(((v - vmin) / res).astype(int), 0, zb.shape[0] - 1)
        # visible si ninguna superficie está delante del punto (tolerancia de 0,2 mm)
        ok = d >= zb[iy, ix] - 0.2
        # runs
        start = 0
        for i in range(1, n + 1):
            if i == n or ok[i] != ok[start]:
                seg = (u[start], v[start], u[min(i, n - 1)], v[min(i, n - 1)])
                (vis if ok[start] else hid).append(seg)
                start = i
    return vis, hid


def circles(edges, U, V, D):
    """Agujeros: cadenas cerradas de aristas paralelas al plano de la vista, con radio constante."""
    adj = {}
    for a, b in edges:
        if abs(np.dot(b - a, D)) > 1e-3: continue
        ka, kb = tuple(np.round(a, 3)), tuple(np.round(b, 3))
        adj.setdefault(ka, []).append(kb); adj.setdefault(kb, []).append(ka)
    seen, out = set(), []
    for k in list(adj):
        if k in seen: continue
        comp, st = [], [k]
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); st.extend(adj[x])
        if len(comp) < 10 or any(len(adj[x]) != 2 for x in comp): continue
        P = np.array(comp); u, v = P @ U, P @ V
        A = np.c_[2 * u, 2 * v, np.ones_like(u)]
        sol, *_ = np.linalg.lstsq(A, u * u + v * v, rcond=None)
        cu, cv = sol[0], sol[1]; r = np.sqrt(sol[2] + cu * cu + cv * cv)
        if r > 20 or np.abs(np.hypot(u - cu, v - cv) - r).max() > 0.08 * r + 0.03: continue
        if not any(abs(cu - o[0]) < .2 and abs(cv - o[1]) < .2 and abs(r - o[2]) < .05 for o in out):
            out.append((cu, cv, r))
    return out


def fmt(x):
    return (f"{x:.1f}".rstrip("0").rstrip(".")).replace(".", ",")


def plano(p):
    stl = os.path.join(REPO, p["stl"])
    tris = load_stl(stl)
    tris -= tris.reshape(-1, 3).min(0)
    edges, verts = feature_edges(tris)
    ext = tris.reshape(-1, 3).max(0)
    # escala normalizada que deja caber las 3 vistas
    ax, ay, az = ext
    need_w, need_h = ax + ay + 40, az + ay + 40
    escala = next(s for s in (5, 4, 3, 2, 1.5, 1, 0.75, 0.5, 0.4, 0.25) if need_w * s <= 250 and need_h * s <= 150)
    s = escala
    ox, oy = 18.0, 14.0                                    # origen de la zona de dibujo
    gap = 22.0 / s * s
    place = {"Elevación": (ox, oy), "Planta": (ox, oy + az * s + gap), "Lateral": (ox + ax * s + gap, oy)}
    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' width='{W}mm' height='{H}mm' {FONT}>",
           f"<rect width='{W}' height='{H}' fill='#fff'/>",
           f"<rect x='6' y='6' width='{W-12}' height='{H-12}' fill='none' stroke='{INK}' stroke-width='.5'/>"]
    for name, (U, V, D) in VIEWS.items():
        X0, Y0 = place[name]
        vis, hid = project(edges, tris, U, V, D)
        umax = (tris.reshape(-1, 3) @ U).max(); vmax = (tris.reshape(-1, 3) @ V).max()
        tx = lambda u: X0 + u * s
        ty = lambda v: Y0 + (vmax - v) * s                    # v hacia arriba
        if name == "Planta":
            ty = lambda v: Y0 + v * s                          # planta bajo la elevación, mirando desde arriba (primer diedro)
        g = [f"<g stroke-linecap='round'>"]
        for (u0, v0, u1, v1) in hid:
            g.append(f"<line x1='{tx(u0):.2f}' y1='{ty(v0):.2f}' x2='{tx(u1):.2f}' y2='{ty(v1):.2f}' stroke='{HID}' stroke-width='.18' stroke-dasharray='1.2 .8'/>")
        for (u0, v0, u1, v1) in vis:
            g.append(f"<line x1='{tx(u0):.2f}' y1='{ty(v0):.2f}' x2='{tx(u1):.2f}' y2='{ty(v1):.2f}' stroke='{INK}' stroke-width='.35'/>")
        g.append("</g>")
        svg += g
        # cotas generales
        w_, h_ = umax, vmax
        yb = max(ty(0), ty(vmax)) + 6
        svg.append(dim_h(tx(0), tx(w_), yb, fmt(w_)))
        xr = tx(w_) + 6
        svg.append(dim_v(xr, min(ty(0), ty(vmax)), max(ty(0), ty(vmax)), fmt(h_)))
        svg.append(f"<text x='{X0:.1f}' y='{min(ty(0), ty(vmax)) - 3:.1f}' font-size='3.2' font-weight='700' fill='{INK}'>{name.upper()}</text>")
        # agujeros
        holes = circles(edges, U, V, D)
        groups = {}
        for (cu, cv, r) in holes: groups.setdefault(round(2 * r, 1), []).append((cu, cv))
        for k, (d, pts) in enumerate(sorted(groups.items())):
            cu, cv = pts[0]
            x, y = tx(cu), ty(cv)
            lx, ly = x + 8 + 3 * k, y - 7 - 4 * k
            svg.append(f"<circle cx='{x:.2f}' cy='{y:.2f}' r='.5' fill='{DIM}'/>")
            svg.append(f"<polyline points='{x:.2f},{y:.2f} {lx:.2f},{ly:.2f} {lx+10:.2f},{ly:.2f}' fill='none' stroke='{DIM}' stroke-width='.2'/>")
            lab = f"{len(pts)}× Ø{fmt(d)}" if len(pts) > 1 else f"Ø{fmt(d)}"
            svg.append(f"<text x='{lx+0.5:.2f}' y='{ly-0.8:.2f}' font-size='2.6' fill='{DIM}'>{lab}</text>")
    svg += rotulo(p, escala, tris)
    svg.append("</svg>")
    fn = os.path.join(OUT, f"{p['id']}_rev{p['rev']}.svg")
    open(fn, "w", encoding="utf-8").write("\n".join(svg))
    return fn


def arrow(x, y, ang):
    import math
    a1, a2 = ang + 2.7, ang - 2.7
    return f"<path d='M{x:.2f},{y:.2f} l{1.8*math.cos(a1):.2f},{1.8*math.sin(a1):.2f} l{1.8*math.cos(a2)-1.8*math.cos(a1):.2f},{1.8*math.sin(a2)-1.8*math.sin(a1):.2f} z' fill='{DIM}'/>"


def dim_h(x0, x1, y, txt):
    return (f"<g stroke='{DIM}' stroke-width='.2'><line x1='{x0:.2f}' y1='{y-4:.2f}' x2='{x0:.2f}' y2='{y+1:.2f}'/>"
            f"<line x1='{x1:.2f}' y1='{y-4:.2f}' x2='{x1:.2f}' y2='{y+1:.2f}'/><line x1='{x0:.2f}' y1='{y:.2f}' x2='{x1:.2f}' y2='{y:.2f}'/></g>"
            + arrow(x0, y, 0) + arrow(x1, y, 3.14159) +
            f"<text x='{(x0+x1)/2:.2f}' y='{y-1:.2f}' font-size='2.8' text-anchor='middle' fill='{DIM}'>{txt}</text>")


def dim_v(x, y0, y1, txt):
    return (f"<g stroke='{DIM}' stroke-width='.2'><line x1='{x-4:.2f}' y1='{y0:.2f}' x2='{x+1:.2f}' y2='{y0:.2f}'/>"
            f"<line x1='{x-4:.2f}' y1='{y1:.2f}' x2='{x+1:.2f}' y2='{y1:.2f}'/><line x1='{x:.2f}' y1='{y0:.2f}' x2='{x:.2f}' y2='{y1:.2f}'/></g>"
            + arrow(x, y0, 1.5708) + arrow(x, y1, -1.5708) +
            f"<text x='{x+1.5:.2f}' y='{(y0+y1)/2+1:.2f}' font-size='2.8' fill='{DIM}'>{txt}</text>")


def rotulo(p, escala, tris):
    x0, y0, w, h = W - 6 - 118, H - 6 - 52, 118, 52
    esc = f"{fmt(escala)}:1" if escala >= 1 else f"1:{fmt(1/escala)}"
    rows = [("PIEZA", f"{p['id']} · {p['nombre']}"), ("PROYECTO", REG["proyecto"]),
            ("MATERIAL", f"{p['material']} · {p.get('relleno','')}"), ("IMPRESIÓN", p.get("orientacion", "")),
            ("ESTADO", p["estado"]), ("ESCALA", f"{esc} · mm · primer diedro (ISO E)")]
    out = [f"<rect x='{x0}' y='{y0}' width='{w}' height='{h}' fill='#fff' stroke='{INK}' stroke-width='.5'/>"]
    for i, (k, v) in enumerate(rows):
        y = y0 + 6 + i * 6.2
        out.append(f"<text x='{x0+2}' y='{y}' font-size='2.2' fill='{HID}'>{k}</text>")
        out.append(f"<text x='{x0+22}' y='{y}' font-size='2.9' fill='{INK}'>{esc_xml(v)}</text>")
    yr = y0 + 6 + len(rows) * 6.2
    out.append(f"<line x1='{x0}' y1='{yr-3.5}' x2='{x0+w}' y2='{yr-3.5}' stroke='{INK}' stroke-width='.3'/>")
    out.append(f"<text x='{x0+2}' y='{yr}' font-size='2.2' fill='{HID}'>REV · FECHA · CAMBIO</text>")
    for j, hst in enumerate(p.get("historial", [])[-3:]):
        out.append(f"<text x='{x0+2}' y='{yr+3.4+j*3.2:.1f}' font-size='2.3' fill='{INK}'>{esc_xml(hst['rev'] + ' · ' + hst['fecha'] + ' · ' + hst['cambio'])[:92]}</text>")
    out.append(f"<rect x='{x0+w-26}' y='{y0}' width='26' height='12' fill='{ACC}'/>")
    out.append(f"<text x='{x0+w-13}' y='{y0+5}' font-size='2.4' text-anchor='middle' fill='#231800'>REV</text>")
    out.append(f"<text x='{x0+w-13}' y='{y0+10.5}' font-size='5.5' font-weight='700' text-anchor='middle' fill='#231800'>{p['rev']}</text>")
    out.append(f"<text x='10' y='{H-9}' font-size='2.4' fill='{HID}'>Generado desde {esc_xml(p['stl'])} · bicho · CRBRC · Platanus Hack 26. Cotas en mm. No medir sobre el dibujo.</text>")
    return out


def esc_xml(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    solo = sys.argv[1:]
    for p in REG["piezas"]:
        if not p.get("stl") or (solo and p["id"] not in solo): continue
        print(plano(p))
