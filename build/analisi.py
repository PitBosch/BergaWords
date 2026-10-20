"""Fase 1: analisi esplorativa di comesidice.xlsx.

Genera in analisi/:
  - copertura_comuni.svg      risposte per comune (somma su tutte le parole)
  - copertura_per_parola.csv  risposte per comune e parola
  - varianti_proposte.yaml    proposte di accorpamento da approvare
  - riepilogo.json            numeri usati in ANALISI.md

Usa solo pandas e la libreria standard, così gira anche senza dipendenze geo.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from carica import ROOT, carica_risposte

OUT = ROOT / "analisi"
GEOJSON = ROOT / "data" / "BergamoGiusto.geojson"

# Risposte che citano più forme: "Poia o Galina", "Sia sàss che plòch", "Porsèl/Sunì"
SEPARATORI = re.compile(r"\s*(?:/|\\|,|;|\be/o\b|\boppure\b|\bo\b|\be\b|\bsia\b|\bche\b|\bma anche\b)\s*", re.I)
MULTI = re.compile(r"/|\\|\be/o\b|\boppure\b|\bsia\b.+\bche\b|\b(o|e)\b", re.I)
RUMORE = re.compile(r"non (lo )?so|so m[iì]a|al so mia|boh|sconosciut|nessun|non saprei|non si dice|non lo dico", re.I)
ARTICOLI = re.compile(r"^(?:(?:ol|la|il|el|lo|al)\s+|l['’]\s*)", re.I)


def chiave(s):
    """Chiave di confronto grafico: minuscole, senza accenti/dieresi, senza doppie e articoli."""
    s = str(s).strip().lower()
    s = re.sub(r"\(.*?\)|[!?.😂🤣💀😁😀😜]", "", s).strip()
    s = ARTICOLI.sub("", s)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def chiave_fonetica(s):
    """Come chiave() ma conserva ö/ü, che in bergamasco sono suoni distinti da o/u."""
    s = str(s).strip().lower().replace("ô", "ö").replace("ë", "e")
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s).strip()
    s = ARTICOLI.sub("", s)
    keep = {"ö", "ü"}
    s = "".join(c for c in s if c in keep or unicodedata.category(c) != "Mn")
    s = "".join(c if c in keep else unicodedata.normalize("NFD", c)[0] for c in s)
    s = re.sub(r"[^a-zöü]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def classifica(valore, principali):
    v = str(valore).strip()
    parole = len(v.split())
    if not v or RUMORE.search(v):
        return "rumore"
    if MULTI.search(v) and parole <= 8:
        pezzi = [p for p in SEPARATORI.split(v) if p and chiave(p)]
        if len(pezzi) >= 2 and any(chiave(p) in principali for p in pezzi):
            return "multipla"
    if parole > 5:
        return "commento"
    return "singola"


def proposte(g):
    """Raggruppa le grafie di una parola e propone un canonico per gruppo."""
    vc = g["variante_grezza"].astype(str).str.strip().value_counts()
    totale = vc.sum()
    # le opzioni del modulo sono le forme con almeno l'1% delle risposte
    principali = {chiave(k): k for k, n in vc.items() if n >= max(5, 0.01 * totale)}
    gruppi = defaultdict(Counter)
    esclusi, multiple, commenti = Counter(), Counter(), Counter()
    for forma, n in vc.items():
        tipo = classifica(forma, principali)
        if tipo == "rumore":
            esclusi[forma] += n
            continue
        if tipo == "multipla":
            multiple[forma] += n
            continue
        if tipo == "commento":
            commenti[forma] += n
            continue
        k = chiave(forma)
        if k in principali:
            gruppi[principali[k]][forma] += n
            continue
        # forma rara: si aggancia alla principale più simile se molto vicina
        best, score = None, 0
        for kp, canon in principali.items():
            r = SequenceMatcher(None, k, kp).ratio()
            if r > score:
                best, score = canon, r
        if best and score >= 0.8:
            gruppi[best][forma] += n
        else:
            gruppi[forma][forma] += n
    return gruppi, multiple, commenti, esclusi, totale


def svg_copertura(conteggi, path):
    gj = json.loads(GEOJSON.read_text())
    xs, ys = [], []
    for f in gj["features"]:
        for ring in _anelli(f["geometry"]):
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    kx = 0.7  # cos(45.7°) per non schiacciare la provincia
    W = 760
    H = W * (y1 - y0) / ((x1 - x0) * kx)
    sx = lambda x: (x - x0) * kx / ((x1 - x0) * kx) * W
    sy = lambda y: (y1 - y) / (y1 - y0) * H
    classi = [(0, "#f2d4cf", "0"), (1, "#e7ecef", "1–9"), (10, "#b9cdda", "10–49"),
              (50, "#7fa3bd", "50–199"), (200, "#3f6f94", "200–999"), (1000, "#1d3f5c", "≥1000")]

    def colore(n):
        return [c for soglia, c, _ in classi if n >= soglia][-1]

    parti = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H + 70:.0f}" '
             f'font-family="Libre Franklin, Helvetica, Arial, sans-serif" font-size="11">',
             f'<rect width="100%" height="100%" fill="#fbfaf7"/>']
    for f in gj["features"]:
        nome = f["properties"]["name"]
        n = conteggi.get(nome, 0)
        d = " ".join("M" + " L".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in r) + "Z"
                     for r in _anelli(f["geometry"]))
        parti.append(f'<path d="{d}" fill="{colore(n)}" stroke="#ffffff" stroke-width="0.6">'
                     f'<title>{nome}: {n}</title></path>')
    for i, (_, c, lab) in enumerate(classi):
        x = 20 + i * 110
        parti.append(f'<rect x="{x}" y="{H + 25:.0f}" width="14" height="14" fill="{c}"/>'
                     f'<text x="{x + 20}" y="{H + 36:.0f}" fill="#444">{lab}</text>')
    parti.append(f'<text x="20" y="{H + 60:.0f}" fill="#777">Risposte per comune, somma delle 29 parole</text></svg>')
    path.write_text("\n".join(parti))


def _anelli(geom):
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    return [r for poly in geom["coordinates"] for r in poly]


def yaml_str(s):
    return json.dumps(s, ensure_ascii=False)


def main():
    OUT.mkdir(exist_ok=True)
    d = carica_risposte()
    d["comune"] = d["comune_grezzo"].astype(str).str.strip().replace({"Villa d'Almè": "Villa d'Alme", "Almè": "Alme"})
    comuni = pd.read_csv(ROOT / "data" / "ComuniFinal.csv")["Comune"].tolist()

    per_comune = d.groupby("comune").size().reindex(comuni, fill_value=0)
    tab = d.pivot_table(index="comune", columns="parola", values="modulo", aggfunc="size", fill_value=0)
    tab = tab.reindex(comuni, fill_value=0)
    tab.to_csv(OUT / "copertura_per_parola.csv")
    svg_copertura(per_comune.to_dict(), OUT / "copertura_comuni.svg")

    # moduli raccolti insieme (stesse marche temporali): probabile stesso rispondente
    firme = d.groupby("modulo")["timestamp"].apply(lambda s: tuple(s.sort_values().head(20)))
    gemelli = defaultdict(list)
    for m, f in firme.items():
        gemelli[f].append(m)

    riepilogo = {"risposte": len(d), "parole": d.parola.nunique(), "comuni_lista": len(comuni),
                 "comuni_con_risposte": int((per_comune > 0).sum()),
                 "moduli_gemelli": [sorted(v) for v in gemelli.values() if len(v) > 1],
                 "comuni_scoperti_per_parola": (tab == 0).sum().to_dict(),
                 "comuni_sotto_5_per_parola": (tab < 5).sum().to_dict(),
                 "mediana_per_comune_per_parola": tab.median().to_dict(),
                 "top_comuni": per_comune.sort_values(ascending=False).head(10).to_dict(),
                 "parole": {}}

    righe = ["# Proposte di normalizzazione generate da build/analisi.py.",
             "# Per ogni parola: canonico -> grafie da unire. Correggi qui e rinomina in varianti.yaml.",
             "# 'multiple' vengono divise tra le varianti citate; 'commenti' finiscono nel tab Commenti;",
             "# 'escluse' non entrano nella stima.", ""]
    for parola, g in d.groupby("parola", sort=False):
        gruppi, multiple, commenti, esclusi, totale = proposte(g)
        ordinati = sorted(gruppi.items(), key=lambda kv: -sum(kv[1].values()))
        principali = [(c, sum(v.values())) for c, v in ordinati if sum(v.values()) >= max(5, 0.01 * totale)]
        rare = [(c, sum(v.values())) for c, v in ordinati if sum(v.values()) < max(5, 0.01 * totale)]
        # forme principali che differiscono solo per accenti/dieresi/doppie: da decidere
        dubbi = defaultdict(list)
        for c, n in principali:
            dubbi[chiave(c)].append(c)
        riepilogo["parole"][parola] = {
            "risposte": int(totale), "grafie_distinte": int(g.variante_grezza.astype(str).str.strip().nunique()),
            "principali": principali, "rare": len(rare), "rare_risposte": sum(n for _, n in rare),
            "multiple": sum(multiple.values()), "commenti": sum(commenti.values()), "escluse": sum(esclusi.values()),
            "coppie_dubbie": [v for v in dubbi.values() if len(v) > 1],
            "comuni": int(g.comune.nunique()),
        }
        righe.append(f"{yaml_str(parola)}:")
        righe.append("  varianti:")
        for canon, forme in ordinati:
            n = sum(forme.values())
            righe.append(f"    {yaml_str(canon)}:  # {n} risposte" + ("  (rara)" if n < max(5, 0.01 * totale) else ""))
            for forma, k in forme.most_common():
                righe.append(f"      - {yaml_str(forma)}  # {k}")
        for nome, cnt in (("multiple", multiple), ("commenti", commenti), ("escluse", esclusi)):
            if cnt:
                righe.append(f"  {nome}:")
                righe += [f"    - {yaml_str(f)}  # {k}" for f, k in cnt.most_common()]
        righe.append("")
    (OUT / "varianti_proposte.yaml").write_text("\n".join(righe))
    (OUT / "riepilogo.json").write_text(json.dumps(riepilogo, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: v for k, v in riepilogo.items() if k != "parole"}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
