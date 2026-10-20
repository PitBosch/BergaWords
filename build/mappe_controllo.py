"""Mappe statiche di controllo dalle tabelle gold: analisi/controllo_<slug>_<livello>.svg/.png

    python3 build/mappe_controllo.py Roncola:lessema ciabatta:pronuncia Sasso:lessema
"""
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

from db import DB, GEOJSON, _anelli
from carica import ROOT

CHROME = next(iter(sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))), None)


def mappa(con, parola, livello, out):
    dom = pd.read_sql("select * from gold_dominanti_comune where parola=? and livello=?", con, params=(parola, livello))
    var = pd.read_sql("select * from gold_varianti where parola=? and livello=?", con, params=(parola, livello))
    iso = pd.read_sql("select * from gold_isoglosse where parola=? and livello=?", con, params=(parola, livello))
    colore = dict(zip(var.variante, var.colore))
    d = dom.set_index("comune")
    gj = json.loads(GEOJSON.read_text())
    pts = [(x, y) for f in gj["features"] for poly in _anelli(f["geometry"]) for ring in poly for x, y in ring]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    W, kx = 760, 0.7
    H = W * (y1 - y0) / ((x1 - x0) * kx)
    sx = lambda x: (x - x0) / (x1 - x0) * W
    sy = lambda y: (y1 - y) / (y1 - y0) * H
    parti = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H + 40 + 22 * len(var):.0f}" '
             f'font-family="Georgia, serif" font-size="13"><rect width="100%" height="100%" fill="#fbfaf7"/>',
             f'<text x="20" y="28" font-size="22" fill="#222">{parola} — {livello}</text>']
    for f in gj["features"]:
        r = d.loc[f["properties"]["name"]]
        op = 0.15 + 0.85 * max(0, (r.consenso - 0.3) / 0.7)
        if r.sbiadito:
            op *= 0.5
        path = " ".join("M" + " L".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in ring) + "Z"
                        for poly in _anelli(f["geometry"]) for ring in poly)
        parti.append(f'<path d="{path}" fill="{colore[r.dominante]}" fill-opacity="{op:.2f}" '
                     f'stroke="#ffffff" stroke-width="0.5"><title>{r.name}: {r.dominante} {r.consenso:.0%}</title></path>')
    for i, v in enumerate(var.itertuples()):
        y = H + 30 + 22 * i
        parti.append(f'<rect x="20" y="{y - 12:.0f}" width="14" height="14" fill="{v.colore}"/>'
                     f'<text x="42" y="{y:.0f}" fill="#333">{v.variante} — {v.quota_provincia:.0%}</text>')
    parti.append("</svg>")
    out.with_suffix(".svg").write_text("\n".join(parti))
    if CHROME:
        subprocess.run([str(CHROME), "--headless=new", "--no-sandbox", f"--screenshot={out.with_suffix('.png')}",
                        f"--window-size={W},{int(H + 40 + 22 * len(var))}", out.with_suffix(".svg").as_uri()],
                       capture_output=True, check=False)


def main():
    from db import slug
    with sqlite3.connect(DB) as con:
        for arg in sys.argv[1:]:
            parola, livello = arg.split(":")
            mappa(con, parola, livello, ROOT / "analisi" / f"controllo_{slug(parola)}_{livello}")


if __name__ == "__main__":
    main()
