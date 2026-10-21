"""Database BergaWords a tre livelli (medallion) in data/bergawords.sqlite.

  bronze_*  dati così come arrivano dall'Excel, tutto testo, nessuna correzione
  silver_*  dati puliti: comuni allineati, varianti normalizzate con varianti.yaml,
            duplicati ed esclusioni segnati, geometria dei comuni
  gold_*    tabelle pronte per il frontend: stime per comune, colori, isoglosse,
            indice delle parole, commenti; esportate anche in public/data/gold/

    python3 build/db.py            # ricostruisce tutto
    python3 build/db.py silver     # solo un livello (e i successivi)

Il gold ha due stime: per comune (kernel gaussiano a k vicini sui centroidi + prior di
Dirichlet) e per esagono H3 (build/esagoni.py, fase 2).
"""
import hashlib
import json
import math
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from carica import ROOT, XLSX
from normalizza import ALTRE, Regole, normalizza

DB = ROOT / "data" / "bergawords.sqlite"
GEOJSON = ROOT / "data" / "BergamoGiusto.geojson"
EXPORT = ROOT / "public" / "data" / "gold"

PARAMETRI = {
    "k_vicini": 30,         # banda = distanza del k-esimo rispondente
    "banda_min_km": 3.0,    # evita bande nulle dove un comune ha più di k risposte
    "alpha_prior": 5.0,     # forza del prior di Dirichlet, in risposte equivalenti
    "banda_alta_km": 6.0,   # affidabilità alta se bastano 6 km per raccogliere k risposte
    "banda_media_km": 12.0,
    "banda_sbiadito_km": 15.0,  # oltre: colore sbiadito verso il grigio
    "salto_netto": 0.2,     # differenza di probabilità per un'isoglossa netta (~10% dei confini)
    "top_varianti": 5,
}
PALETTE = ["#3d6b99", "#c9733f", "#5e9c76", "#b8506a", "#d6a737",
           "#7a68a6", "#4f9eb0", "#a0745a", "#8aa04a", "#c47fa8"]
GRIGIO = "#b9b5ad"
LIVELLI = ("lessema", "pronuncia")


def slug(s):
    s = unicodedata.normalize("NFD", s.lower().replace("'", "-"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def scrivi(con, nome, df):
    df.to_sql(nome, con, if_exists="replace", index=False)


# ---------------------------------------------------------------- bronze

def bronze(con):
    righe = []
    for foglio in pd.ExcelFile(XLSX).sheet_names:
        df = pd.read_excel(XLSX, sheet_name=foglio, dtype=str)
        domanda = next(c for c in df.columns if c.startswith("Come dici"))
        righe.append(pd.DataFrame({
            "foglio": foglio,
            "riga_excel": df.index + 2,
            "informazioni_cronologiche": df["Informazioni cronologiche"],
            "di_che_paese_sei": df["Di che paese sei?"],
            "domanda": domanda,
            "risposta": df[domanda],
        }))
    # la colonna "Indirizzo email" del modulo 11 è vuota e resta fuori dal repository pubblico
    scrivi(con, "bronze_risposte", pd.concat(righe, ignore_index=True))
    scrivi(con, "bronze_caricamenti", pd.DataFrame([{
        "file": XLSX.name,
        "sha256": hashlib.sha256(XLSX.read_bytes()).hexdigest(),
        "caricato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }]))


# ---------------------------------------------------------------- silver

def _anelli(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return polys


def _centroide(geom):
    """Centroide del poligono esterno più grande, in gradi."""
    best, area_best = None, -1
    for poly in _anelli(geom):
        xs, ys = np.array(poly[0]).T
        a = 0.5 * np.sum(xs[:-1] * ys[1:] - xs[1:] * ys[:-1])
        if abs(a) > area_best:
            cx = np.sum((xs[:-1] + xs[1:]) * (xs[:-1] * ys[1:] - xs[1:] * ys[:-1])) / (6 * a)
            cy = np.sum((ys[:-1] + ys[1:]) * (xs[:-1] * ys[1:] - xs[1:] * ys[:-1])) / (6 * a)
            best, area_best = (cx, cy), abs(a)
    return best


def silver(con):
    gj = json.loads(GEOJSON.read_text())
    comuni, vertici = [], {}
    for f in gj["features"]:
        p = f["properties"]
        lon, lat = _centroide(f["geometry"])
        comuni.append({"comune": p["name"], "istat": p["com_istat_code"], "lon": lon, "lat": lat})
        vertici[p["name"]] = {(round(x, 5), round(y, 5)) for poly in _anelli(f["geometry"])
                              for ring in poly for x, y in ring}
    scrivi(con, "silver_comuni", pd.DataFrame(comuni))
    nomi = list(vertici)
    adiacenze = [(a, b) for i, a in enumerate(nomi) for b in nomi[i + 1:]
                 if len(vertici[a] & vertici[b]) >= 2]
    scrivi(con, "silver_adiacenze", pd.DataFrame(adiacenze, columns=["comune_a", "comune_b"]))

    b = pd.read_sql("select * from bronze_risposte", con)
    d = pd.DataFrame({
        "id_risposta": b.index + 1,
        "modulo": b.foglio.str.extract(r"(\d+)$")[0].astype(int),
        "riga_excel": b.riga_excel,
        "timestamp": pd.to_datetime(b.informazioni_cronologiche, errors="coerce"),
        "comune_grezzo": b.di_che_paese_sei,
        "parola": b.domanda.str.replace(r"^Come dici\s+|\?\s*$", "", regex=True).str.strip(),
        "variante_grezza": b.risposta,
    })
    d, lungo = normalizza(d, Regole())
    d["timestamp"] = d["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    scrivi(con, "silver_risposte", d[["id_risposta", "modulo", "riga_excel", "timestamp", "parola", "comune",
                                      "variante_grezza", "tipo", "duplicato"]])
    lungo["id_risposta"] = d.loc[lungo.risposta, "id_risposta"].values
    scrivi(con, "silver_varianti", lungo[["id_risposta", "parola", "comune", "lessema", "pronuncia", "peso"]])


# ---------------------------------------------------------------- gold

def _km(lon, lat):
    lat0 = math.radians(45.7)
    return np.column_stack([lon * 111.32 * math.cos(lat0), lat * 110.57])


def stima(conteggi, coord, totale_prov, par):
    """conteggi: matrice comuni x varianti (risposte pesate). Restituisce prob, n_eff e banda per comune."""
    dist = np.linalg.norm(coord[:, None, :] - coord[None, :, :], axis=2)
    n_comune = conteggi.sum(1)
    prior = totale_prov / totale_prov.sum()
    prob = np.zeros_like(conteggi)
    n_eff = np.zeros(len(coord))
    banda = np.zeros(len(coord))
    for i in range(len(coord)):
        ordine = np.argsort(dist[i])
        cum = np.cumsum(n_comune[ordine])
        j = min(np.searchsorted(cum, par["k_vicini"]), len(ordine) - 1)
        h = banda[i] = max(dist[i, ordine[j]], par["banda_min_km"])
        w = np.exp(-0.5 * (dist[i] / h) ** 2)
        somma = w @ conteggi
        n_eff[i] = somma.sum()
        prob[i] = (somma + par["alpha_prior"] * prior) / (n_eff[i] + par["alpha_prior"])
    return prob, n_eff, banda


def colori(varianti, quote, dominanti, adiacenze):
    """Assegna la palette in ordine di diffusione evitando colori uguali tra aree confinanti."""
    vicini = {v: set() for v in varianti}
    for a, b in adiacenze:
        va, vb = dominanti.get(a), dominanti.get(b)
        if va and vb and va != vb:
            vicini[va].add(vb)
            vicini[vb].add(va)
    out = {}
    for v in sorted(varianti, key=lambda v: -quote[v]):
        if v == ALTRE:
            out[v] = GRIGIO
            continue
        usati = {out[n] for n in vicini[v] if n in out}
        liberi = [c for c in PALETTE if c not in usati and c not in out.values()] or \
                 [c for c in PALETTE if c not in usati] or PALETTE
        out[v] = liberi[0]
    return out


def gold(con, par=PARAMETRI):
    comuni = pd.read_sql("select * from silver_comuni", con)
    adiacenze = list(pd.read_sql("select * from silver_adiacenze", con).itertuples(index=False, name=None))
    var = pd.read_sql("select * from silver_varianti", con)
    risp = pd.read_sql("select * from silver_risposte", con)
    coord = _km(comuni.lon.values, comuni.lat.values)
    nomi = comuni.comune.tolist()

    t_parole, t_var, t_top, t_dom, t_iso = [], [], [], [], []
    for parola, g in var.groupby("parola", sort=False):
        osservate = g.groupby("comune").id_risposta.nunique().reindex(nomi, fill_value=0)
        riepilogo = {}
        for livello in LIVELLI:
            tab = g.pivot_table(index="comune", columns=livello, values="peso", aggfunc="sum", fill_value=0)
            tab = tab.reindex(nomi, fill_value=0)
            varianti = tab.columns.tolist()
            totale = tab.values.sum(0)
            prob, n_eff, banda = stima(tab.values.astype(float), coord, totale, par)
            idx = prob.argmax(1)
            dominanti = {c: varianti[k] for c, k in zip(nomi, idx)}
            quote = dict(zip(varianti, totale / totale.sum()))
            col = colori(varianti, quote, dominanti, adiacenze)
            lessema_di = g.groupby(livello).lessema.first().to_dict()
            for v in sorted(varianti, key=lambda v: -quote[v]):
                t_var.append({"parola": parola, "livello": livello, "variante": v, "lessema": lessema_di[v],
                              "risposte": round(float(totale[varianti.index(v)]), 2),
                              "quota_provincia": round(float(quote[v]), 4), "colore": col[v]})
            for i, c in enumerate(nomi):
                top = np.argsort(-prob[i])[:par["top_varianti"]]
                for r, k in enumerate(top, 1):
                    t_top.append({"parola": parola, "livello": livello, "comune": c, "rango": r,
                                  "variante": varianti[k], "probabilita": round(float(prob[i, k]), 4)})
                aff = ("alta" if banda[i] <= par["banda_alta_km"] else
                       "media" if banda[i] <= par["banda_media_km"] else "bassa")
                t_dom.append({"parola": parola, "livello": livello, "comune": c, "dominante": varianti[idx[i]],
                              "consenso": round(float(prob[i, idx[i]]), 4), "n_eff": round(float(n_eff[i]), 1),
                              "banda_km": round(float(banda[i]), 1),
                              "risposte_osservate": int(osservate[c]), "affidabilita": aff,
                              "sbiadito": bool(banda[i] > par["banda_sbiadito_km"])})
            pos = {c: i for i, c in enumerate(nomi)}
            nette = 0
            for a, b in adiacenze:
                ia, ib = pos[a], pos[b]
                if idx[ia] == idx[ib]:
                    continue
                salto = 0.5 * (abs(prob[ia, idx[ia]] - prob[ib, idx[ia]]) + abs(prob[ib, idx[ib]] - prob[ia, idx[ib]]))
                tipo = "netta" if salto >= par["salto_netto"] else "sfumata"
                nette += tipo == "netta"
                t_iso.append({"parola": parola, "livello": livello, "comune_a": a, "comune_b": b,
                              "variante_a": varianti[idx[ia]], "variante_b": varianti[idx[ib]],
                              "salto": round(float(salto), 4), "tipo": tipo})
            # divisività = informazione mutua tra luogo e variante, in bit:
            # entropia provinciale meno entropia media locale. Alta se la provincia
            # è divisa in zone diverse e compatte, bassa se ovunque si dice uguale o
            # se ovunque si dice di tutto.
            p_prov = totale / totale.sum()
            h_prov = float(-(p_prov * np.log2(np.clip(p_prov, 1e-12, 1))).sum())
            h_loc = -(prob * np.log2(np.clip(prob, 1e-12, 1))).sum(1)
            diversi = sum(idx[pos[a]] != idx[pos[b]] for a, b in adiacenze) / len(adiacenze)
            riepilogo[livello] = {"entropia": h_prov, "entropia_locale": float(h_loc.mean()),
                                  "info": max(0.0, h_prov - float(h_loc.mean())),
                                  "confini": diversi, "nette": nette / len(adiacenze),
                                  "top": max(quote, key=quote.get), "quota_top": quote[max(quote, key=quote.get)],
                                  "n": len(varianti)}
        r = riepilogo["lessema"]
        t_parole.append({
            "parola": parola, "slug": slug(parola), "titolo": parola[0].upper() + parola[1:],
            "risposte": int(risp[(risp.parola == parola)].shape[0]),
            "risposte_valide": int(g.id_risposta.nunique()),
            "comuni_con_risposte": int((osservate > 0).sum()),
            "lessemi": r["n"], "pronunce": riepilogo["pronuncia"]["n"],
            "lessema_principale": r["top"], "quota_principale": round(r["quota_top"], 4),
            "entropia_provincia_bit": round(r["entropia"], 4), "entropia_locale_bit": round(r["entropia_locale"], 4),
            "quota_confini_diversi": round(r["confini"], 4), "quota_confini_netti": round(r["nette"], 4),
            "divisivita": round(r["info"], 4),
            "divisivita_pronunce": round(riepilogo["pronuncia"]["info"], 4),
        })
    parole = pd.DataFrame(t_parole).sort_values("divisivita", ascending=False)
    parole["rango_divisivita"] = range(1, len(parole) + 1)
    scrivi(con, "gold_parole", parole)
    scrivi(con, "gold_varianti", pd.DataFrame(t_var))
    scrivi(con, "gold_stima_comune", pd.DataFrame(t_top))
    scrivi(con, "gold_dominanti_comune", pd.DataFrame(t_dom))
    scrivi(con, "gold_isoglosse", pd.DataFrame(t_iso))
    comm = risp[risp.tipo == "commento"][["parola", "comune", "variante_grezza"]].rename(
        columns={"variante_grezza": "testo"})
    scrivi(con, "gold_commenti", comm)
    scrivi(con, "gold_meta", pd.DataFrame([
        {"chiave": "generato_il", "valore": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        {"chiave": "metodo", "valore": "kernel gaussiano a k vicini sui centroidi comunali + prior di Dirichlet"},
        {"chiave": "parametri", "valore": json.dumps(PARAMETRI)},
    ]))
    esporta(con)


def esporta(con):
    """JSON statici per il frontend, uno per parola più indice e commenti."""
    (EXPORT / "parole").mkdir(parents=True, exist_ok=True)
    parole = pd.read_sql("select * from gold_parole order by rango_divisivita", con)
    var = pd.read_sql("select * from gold_varianti", con)
    dom = pd.read_sql("select * from gold_dominanti_comune", con)
    top = pd.read_sql("select * from gold_stima_comune", con)
    iso = pd.read_sql("select * from gold_isoglosse", con)
    meta = dict(pd.read_sql("select * from gold_meta", con).values)
    (EXPORT / "indice.json").write_text(json.dumps(
        {"generato_il": meta["generato_il"], "parole": parole.to_dict("records")}, ensure_ascii=False, indent=1))
    for p in parole.itertuples():
        out = {"parola": p.parola, "slug": p.slug, "titolo": p.titolo, "livelli": {}}
        for livello in LIVELLI:
            v = var[(var.parola == p.parola) & (var.livello == livello)]
            d = dom[(dom.parola == p.parola) & (dom.livello == livello)]
            t = top[(top.parola == p.parola) & (top.livello == livello)]
            tops = {c: [[r.variante, r.probabilita] for r in g.itertuples()] for c, g in t.groupby("comune")}
            i = iso[(iso.parola == p.parola) & (iso.livello == livello)]
            out["livelli"][livello] = {
                "varianti": v.drop(columns=["parola", "livello"]).to_dict("records"),
                "comuni": {r.comune: {"dominante": r.dominante, "consenso": r.consenso, "n_eff": r.n_eff,
                                      "banda_km": r.banda_km,
                                      "osservate": r.risposte_osservate, "affidabilita": r.affidabilita,
                                      "sbiadito": bool(r.sbiadito), "top": tops[r.comune]}
                           for r in d.itertuples()},
                "isoglosse": i[["comune_a", "comune_b", "salto", "tipo"]].values.tolist(),
            }
        (EXPORT / "parole" / f"{p.slug}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    comm = pd.read_sql("select * from gold_commenti", con)
    by = {slug(k): g[["comune", "testo"]].to_dict("records") for k, g in comm.groupby("parola")}
    (EXPORT / "commenti.json").write_text(json.dumps(by, ensure_ascii=False, indent=1))


def main():
    from esagoni import esagoni
    livelli = {"bronze": [bronze, silver, gold, esagoni], "silver": [silver, gold, esagoni],
               "gold": [gold, esagoni], "esagoni": [esagoni]}
    passi = livelli[sys.argv[1] if len(sys.argv) > 1 else "bronze"]
    DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as con:
        for passo in passi:
            passo(con)
            print(f"{passo.__name__}: ok")
        con.commit()
        con.execute("vacuum")
        for (nome,) in con.execute("select name from sqlite_master where type='table' order by name"):
            print(f"  {nome}: {con.execute(f'select count(*) from {nome}').fetchone()[0]} righe")


if __name__ == "__main__":
    main()
