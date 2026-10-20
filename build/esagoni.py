"""Fase 2: stima su griglia H3 (risoluzione 8) e nuove tabelle gold per esagoni.

    python3 build/esagoni.py        # griglia, stima di tutte le parole, export JSON

Passi:
  1. griglia H3 sulla provincia, divisa in "pezzi" esagono x comune con area e popolazione;
  2. maschera dell'abitato: sezioni di censimento ISTAT 2021 con popolazione > 0 se presenti
     in data/istat/ (vedi scarica_istat.py), altrimenti maschera provvisoria con la
     popolazione del comune spalmata in modo uniforme sulla sua superficie;
  3. per ogni seed, ogni risposta diventa un punto casuale in un pezzo del suo comune,
     scelto con probabilità proporzionale alla popolazione;
  4. per ogni esagono, kernel gaussiano con banda = distanza del k-esimo punto
     (tra banda_min e banda_max) + prior di Dirichlet sulle quote provinciali;
  5. media sui seed; sotto n_eff_min l'esagono è sbiadito.
"""
import json
import sqlite3
from datetime import datetime, timezone

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from carica import ROOT
from db import DB, EXPORT, GEOJSON, LIVELLI, scrivi, slug

ISTAT = ROOT / "data" / "istat"  # sezioni di censimento (scarica_istat.py), fuori dal repository
POP_COMUNI = ROOT / "data" / "popolazione_comuni.csv"
CRS = 32632  # UTM 32N, metri

PARAMETRI_H3 = {
    "risoluzione": 8,
    "seed": 10,
    "k_vicini": 30,
    "k_vicini_poche": 20,
    "parole_poche": ["Pop Corn", "Libellula", "talpa"],
    "banda_min_km": 1.5,
    "banda_max_km": 10.0,   # oltre questa distanza i dati non vengono più cercati: decide il prior
    "alpha_prior": 5.0,
    "n_eff_min": 8.0,       # sotto: esagono sbiadito
    "taglio_kernel": 3.0,   # pesi nulli oltre 3 bande
    "jitter_km": 0.35,      # raggio del punto casuale attorno al centro del pezzo
    # differenza di probabilità tra esagoni confinanti (centri a ~0,8 km) per un'isoglossa netta:
    # ~5% dei confini con la maschera provvisoria, da ricalibrare con le sezioni ISTAT
    "salto_netto": 0.05,
}


# ---------------------------------------------------------------- griglia e maschera

def _esagono(c):
    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)])


def sezioni():
    """Sezioni di censimento della provincia con la popolazione in P1, o None se mancano i file."""
    shp = sorted(ISTAT.glob("*.shp")) if ISTAT.exists() else []
    if not shp:
        return None
    sez = gpd.read_file(shp[0])
    sez = sez[sez.COD_PROV.astype(int) == 16]
    chiave = next(c for c in sez.columns if c in ("SEZ21_ID", "SEZ2011", "SEZ21", "SEZ_ID"))
    pop = next((c for c in sez.columns if c in ("P1", "POP21", "POP_2021")), None)
    if pop is None:
        csv = sorted(ISTAT.glob("*indicatori*.csv"))
        if not csv:
            return None
        ind = pd.read_csv(csv[0], sep=None, engine="python", encoding="latin-1")
        ind = ind[[chiave, "P1"]]
        sez = sez.merge(ind, on=chiave, how="left")
        pop = "P1"
    sez["P1"] = pd.to_numeric(sez[pop], errors="coerce").fillna(0)
    return sez[["P1", "geometry"]]


def griglia(par=PARAMETRI_H3):
    """Restituisce (esagoni, pezzi, maschera). pezzi = intersezioni esagono x comune con area e popolazione."""
    com = gpd.read_file(GEOJSON)[["name", "com_istat_code", "geometry"]].rename(
        columns={"name": "comune", "com_istat_code": "istat"})
    celle = set()
    for geom in com.geometry:
        celle |= set(h3.geo_to_cells(geom, par["risoluzione"]))
        p = geom.representative_point()  # anche i comuni più piccoli di un esagono hanno la loro cella
        celle.add(h3.latlng_to_cell(p.y, p.x, par["risoluzione"]))
    celle = sorted(celle)
    esa = gpd.GeoDataFrame({"h3": celle}, geometry=[_esagono(c) for c in celle], crs=4326)
    com_m, esa_m = com.to_crs(CRS), esa.to_crs(CRS)
    com_m["area_comune"] = com_m.area
    pezzi = gpd.overlay(esa_m, com_m, how="intersection", keep_geom_type=True)
    pezzi["area_km2"] = pezzi.area / 1e6
    pezzi = pezzi[pezzi.area_km2 > 1e-4]

    sez = sezioni()
    if sez is not None:
        maschera = "sezioni di censimento ISTAT con popolazione > 0"
        sez = sez.to_crs(CRS)
        sez = sez[sez.P1 > 0]
        sez["area_sez"] = sez.area
        x = gpd.overlay(pezzi[["h3", "comune", "geometry"]], sez, how="intersection", keep_geom_type=True)
        x["pop"] = x.P1 * x.area / x.area_sez
        pop = x.groupby(["h3", "comune"])["pop"].sum()
        pezzi["popolazione"] = pd.MultiIndex.from_frame(pezzi[["h3", "comune"]]).map(pop).fillna(0).values
    else:
        maschera = "provvisoria: popolazione comunale uniforme sulla superficie (sezioni ISTAT non disponibili)"
        popc = pd.read_csv(POP_COMUNI, dtype={"istat": str}).set_index("istat").popolazione
        pezzi["popolazione"] = pezzi.istat.map(popc).values * pezzi.area / pezzi.area_comune
    c = pezzi.geometry.centroid
    pezzi["x_km"], pezzi["y_km"] = c.x / 1e3, c.y / 1e3
    pezzi = pd.DataFrame(pezzi[["h3", "comune", "area_km2", "popolazione", "x_km", "y_km"]]).reset_index(drop=True)

    g = pezzi.groupby("h3")
    esa = esa.set_index("h3")
    esa["comune"] = pezzi.loc[g.popolazione.idxmax() if pezzi.popolazione.sum() else g.area_km2.idxmax()] \
        .set_index("h3").comune
    esa["popolazione"] = g.popolazione.sum()
    esa["area_km2"] = g.area_km2.sum()
    esa = esa[esa.comune.notna()].reset_index()
    esa["abitato"] = esa.popolazione > 0
    cm = esa.to_crs(CRS).geometry.centroid
    esa["x_km"], esa["y_km"] = cm.x / 1e3, cm.y / 1e3
    esa["lat"], esa["lon"] = zip(*esa.h3.map(h3.cell_to_latlng))
    return esa, pezzi, maschera


# ---------------------------------------------------------------- stima

def matrice_risposte(g, livello):
    """Una riga per risposta valida: comune e vettore delle varianti (le multiple valgono 1/k)."""
    tab = g.pivot_table(index=["id_risposta", "comune"], columns=livello, values="peso",
                        aggfunc="sum", fill_value=0)
    return tab.index.get_level_values("comune").values, tab.columns.tolist(), tab.values.astype(float)


class Campionatore:
    """Estrae un punto per risposta dentro i pezzi abitati del suo comune, pesati per popolazione."""

    def __init__(self, pezzi, par):
        self.par = par
        abit = pezzi[pezzi.popolazione > 0]
        self.gruppi = {}
        for c, g in pezzi.groupby("comune"):
            a = abit[abit.comune == c]
            g = a if len(a) else g  # comune senza sezioni abitate: si usa tutta la superficie
            w = (g.popolazione if len(a) else g.area_km2).values
            self.gruppi[c] = (g[["x_km", "y_km"]].values, w / w.sum())

    def punti(self, comuni, rng):
        out = np.empty((len(comuni), 2))
        for c in np.unique(comuni):
            sel = np.flatnonzero(comuni == c)
            xy, w = self.gruppi[c]
            out[sel] = xy[rng.choice(len(w), size=len(sel), p=w)]
        r = self.par["jitter_km"] * np.sqrt(rng.random(len(out)))
        t = 2 * np.pi * rng.random(len(out))
        return out + np.column_stack([r * np.cos(t), r * np.sin(t)])


def kernel(punti, Y, centri, prior, par, k):
    """Kernel gaussiano a banda adattiva + prior di Dirichlet. Restituisce prob, n_eff, banda."""
    d = np.sqrt(((centri[:, None, :] - punti[None, :, :]) ** 2).sum(-1))
    kk = min(k, len(punti)) - 1
    h = np.clip(np.partition(d, kk, axis=1)[:, kk], par["banda_min_km"], par["banda_max_km"])
    w = np.exp(-0.5 * (d / h[:, None]) ** 2)
    w[d > par["taglio_kernel"] * h[:, None]] = 0
    s = w @ Y
    n_eff = s.sum(1)
    prob = (s + par["alpha_prior"] * prior) / (n_eff + par["alpha_prior"])[:, None]
    return prob, n_eff, h


def stima_parola(comuni, Y, centri, camp, par, k, seed0=0):
    """Media su par['seed'] estrazioni. Restituisce prob media, n_eff, banda e stabilità della dominante."""
    prior = Y.sum(0) / Y.sum()
    probs, neffs, bande = [], [], []
    for s in range(par["seed"]):
        pts = camp.punti(comuni, np.random.default_rng(seed0 + s))
        p, n, h = kernel(pts, Y, centri, prior, par, k)
        probs.append(p), neffs.append(n), bande.append(h)
    probs = np.stack(probs)
    prob = probs.mean(0)
    dom = prob.argmax(1)
    stabile = (probs.argmax(2) == dom[None, :]).mean(0)
    dev = probs[:, np.arange(len(dom)), dom].std(0)
    return prob, np.mean(neffs, 0), np.mean(bande, 0), stabile, dev


def vicini_esagoni(celle):
    pos = {c: i for i, c in enumerate(celle)}
    coppie = set()
    for i, c in enumerate(celle):
        for n in h3.grid_ring(c, 1):
            j = pos.get(n)
            if j is not None and i < j:
                coppie.add((i, j))
    return np.array(sorted(coppie))


def per_comune(prob, esa, pezzi):
    """Aggrega le probabilità degli esagoni ai comuni, pesando i pezzi per popolazione (o area)."""
    pos = pd.Series(np.arange(len(esa)), index=esa.h3)
    p = pezzi[pezzi.h3.isin(pos.index)].copy()
    p["w"] = np.where(p.groupby("comune").popolazione.transform("sum") > 0, p.popolazione, p.area_km2)
    out = {}
    for c, g in p.groupby("comune"):
        out[c] = (prob[pos[g.h3].values] * g.w.values[:, None]).sum(0) / g.w.sum()
    return out


# ---------------------------------------------------------------- gold

def esagoni(con, par=PARAMETRI_H3):
    esa, pezzi, maschera = griglia(par)
    var = pd.read_sql("select * from silver_varianti", con)
    ordine = pd.read_sql("select parola, livello, variante, colore from gold_varianti", con)
    camp = Campionatore(pezzi, par)
    attivi = esa[esa.abitato].reset_index(drop=True)
    centri = attivi[["x_km", "y_km"]].values
    coppie = vicini_esagoni(attivi.h3.tolist())
    peso_pop = attivi.popolazione.values / attivi.popolazione.sum()

    t_stima, t_iso, t_div = [], [], []
    for parola, g in var.groupby("parola", sort=False):
        k = par["k_vicini_poche"] if parola in par["parole_poche"] else par["k_vicini"]
        for livello in LIVELLI:
            comuni, varianti, Y = matrice_risposte(g, livello)
            # stesso ordine (e quindi stessi colori) delle tabelle gold per comune
            ord_v = ordine[(ordine.parola == parola) & (ordine.livello == livello)].variante.tolist()
            perm = [varianti.index(v) for v in ord_v]
            varianti, Y = ord_v, Y[:, perm]
            prob, n_eff, banda, stabile, dev = stima_parola(comuni, Y, centri, camp, par, k)
            idx = prob.argmax(1)
            sec = np.argsort(-prob, 1)[:, 1]
            for i, c in enumerate(attivi.h3):
                t_stima.append({
                    "parola": parola, "livello": livello, "h3": c, "dominante": varianti[idx[i]],
                    "consenso": round(float(prob[i, idx[i]]), 4), "n_eff": round(float(n_eff[i]), 1),
                    "banda_km": round(float(banda[i]), 2), "sbiadito": bool(n_eff[i] < par["n_eff_min"]),
                    "seconda": varianti[sec[i]], "prob_seconda": round(float(prob[i, sec[i]]), 4),
                    "stabilita_seed": round(float(stabile[i]), 2), "dev_seed": round(float(dev[i]), 4)})
            a, b = coppie[:, 0], coppie[:, 1]
            diverse = idx[a] != idx[b]
            salto = 0.5 * (np.abs(prob[a, idx[a]] - prob[b, idx[a]]) + np.abs(prob[b, idx[b]] - prob[a, idx[b]]))
            for i, j, s in zip(a[diverse], b[diverse], salto[diverse]):
                t_iso.append({"parola": parola, "livello": livello, "h3_a": attivi.h3[i], "h3_b": attivi.h3[j],
                              "salto": round(float(s), 4),
                              "tipo": "netta" if s >= par["salto_netto"] else "sfumata"})
            # divisività: informazione mutua luogo-variante, con i luoghi pesati per popolazione
            p_prov = Y.sum(0) / Y.sum()
            h_prov = float(-(p_prov * np.log2(np.clip(p_prov, 1e-12, 1))).sum())
            h_loc = -(prob * np.log2(np.clip(prob, 1e-12, 1))).sum(1)
            t_div.append({"parola": parola, "livello": livello, "k_vicini": k,
                          "entropia_provincia_bit": round(h_prov, 4),
                          "entropia_locale_bit": round(float(h_loc @ peso_pop), 4),
                          "divisivita": round(max(0.0, h_prov - float(h_loc @ peso_pop)), 4),
                          "quota_confini_diversi": round(float(diverse.mean()), 4),
                          "quota_confini_netti": round(float((diverse & (salto >= par["salto_netto"])).mean()), 4),
                          "quota_sbiaditi": round(float((n_eff < par["n_eff_min"]) @ peso_pop), 4),
                          "stabilita_media": round(float(stabile @ peso_pop), 4)})
        print(f"  {parola}")
    scrivi(con, "gold_esagoni", pd.DataFrame(esa.drop(columns="geometry")).round(
        {"popolazione": 1, "area_km2": 4, "x_km": 3, "y_km": 3, "lon": 6, "lat": 6}))
    scrivi(con, "gold_stima_esagono", pd.DataFrame(t_stima))
    scrivi(con, "gold_isoglosse_esagono", pd.DataFrame(t_iso))
    div = pd.DataFrame(t_div)
    scrivi(con, "gold_parole_esagoni", div)
    meta = pd.read_sql("select * from gold_meta", con)
    meta = meta[~meta.chiave.str.startswith("esagoni_")]
    meta = pd.concat([meta, pd.DataFrame([
        {"chiave": "esagoni_generato_il", "valore": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        {"chiave": "esagoni_metodo", "valore": "H3 + punti casuali pesati per popolazione + kernel gaussiano "
                                                "a k vicini + prior di Dirichlet, media su seed"},
        {"chiave": "esagoni_maschera", "valore": maschera},
        {"chiave": "esagoni_parametri", "valore": json.dumps(par)},
    ])])
    scrivi(con, "gold_meta", meta)
    esporta_esagoni(con)


def esporta_esagoni(con):
    """public/data/gold/esagoni.geojson (geometria) + esagoni/<slug>.json (stima, indici sugli esagoni)."""
    esa = pd.read_sql("select * from gold_esagoni where abitato", con)
    stima = pd.read_sql("select * from gold_stima_esagono", con)
    iso = pd.read_sql("select * from gold_isoglosse_esagono", con)
    var = pd.read_sql("select * from gold_varianti", con)
    div = pd.read_sql("select * from gold_parole_esagoni", con)
    parole = pd.read_sql("select parola, slug from gold_parole", con)
    meta = dict(pd.read_sql("select * from gold_meta", con).values)
    pos = {c: i for i, c in enumerate(esa.h3)}
    feats = [{"type": "Feature", "id": i,
              "properties": {"h3": r.h3, "comune": r.comune, "popolazione": round(r.popolazione)},
              "geometry": {"type": "Polygon", "coordinates": [[[round(x, 5), round(y, 5)]
                                                                for x, y in _esagono(r.h3).exterior.coords]]}}
             for i, r in enumerate(esa.itertuples())]
    (EXPORT / "esagoni.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "maschera": meta["esagoni_maschera"], "features": feats},
        separators=(",", ":")))
    (EXPORT / "esagoni").mkdir(parents=True, exist_ok=True)
    for p in parole.itertuples():
        out = {"parola": p.parola, "slug": p.slug, "livelli": {}}
        for livello in LIVELLI:
            v = var[(var.parola == p.parola) & (var.livello == livello)]
            nomi = v.variante.tolist()
            iv = {n: i for i, n in enumerate(nomi)}
            s = stima[(stima.parola == p.parola) & (stima.livello == livello)].copy()
            s["i"] = s.h3.map(pos)
            s = s.sort_values("i")
            d = div[(div.parola == p.parola) & (div.livello == livello)].iloc[0]
            i = iso[(iso.parola == p.parola) & (iso.livello == livello)]
            out["livelli"][livello] = {
                "varianti": v[["variante", "lessema", "quota_provincia", "colore"]].to_dict("records"),
                "divisivita": float(d.divisivita),
                # una riga per esagono, nello stesso ordine di esagoni.geojson:
                # [dominante, consenso, seconda, prob. seconda, n_eff, sbiadito, stabilità tra i seed]
                "celle": [[iv[r.dominante], r.consenso, iv[r.seconda], r.prob_seconda, r.n_eff,
                           int(r.sbiadito), r.stabilita_seed] for r in s.itertuples()],
                "isoglosse": [[pos[a], pos[b], int(t == "netta")] for a, b, t in
                              i[["h3_a", "h3_b", "tipo"]].itertuples(index=False)],
            }
        (EXPORT / "esagoni" / f"{p.slug}.json").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")))


def main():
    with sqlite3.connect(DB) as con:
        esagoni(con)
        con.commit()
        con.execute("vacuum")
        for t in ("gold_esagoni", "gold_stima_esagono", "gold_isoglosse_esagono", "gold_parole_esagoni"):
            print(f"  {t}: {con.execute(f'select count(*) from {t}').fetchone()[0]} righe")


if __name__ == "__main__":
    main()
