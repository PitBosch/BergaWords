"""Validazione della fase 2: output in analisi/fase2/ (CSV, mappe, risultati.md).

    python3 build/validazione.py            # tutto
    python3 build/validazione.py semi cv    # solo alcune parti: semi, cv, bym2, mappe, report

  semi   la stima cambia se cambiano i seed? (seed 0-9 contro 100-109)
  cv     validazione incrociata a 5 blocchi sulle risposte: punteggio logaritmico per risposta
         lasciata fuori, per varie scelte di k, banda massima, alpha, e per i modelli di confronto
  bym2   modello BYM2 per comune su tutte le parole (livello lessema) e confronto col kernel;
         sulle parole di PAROLE_CV_BYM2 anche la validazione incrociata
  mappe  mappe di controllo su esagoni e confronto kernel / BYM2
"""
import json
import sqlite3
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from scipy import sparse

import h3
from bym2 import grafo, scala, stima_bym2
from carica import ROOT
from db import DB, GEOJSON, PARAMETRI, _anelli, _km, slug, stima
from esagoni import PARAMETRI_H3, Campionatore, griglia, kernel, matrice_risposte

OUT = ROOT / "analisi" / "fase2"
BLOCCHI = 5
SEED_CV = 3
PAROLE_CV_BYM2 = ["Roncola", "Sasso", "Pop Corn", "Libellula"]
CONFIGURAZIONI = {  # variazioni attorno ai parametri scelti, una alla volta
    "base": {},
    "k=15": {"k_vicini": 15, "k_vicini_poche": 15},
    "k=50": {"k_vicini": 50, "k_vicini_poche": 50},
    "banda max 6 km": {"banda_max_km": 6.0},
    "banda max 20 km": {"banda_max_km": 20.0},
    "alpha=1": {"alpha_prior": 1.0},
    "alpha=20": {"alpha_prior": 20.0},
}


class Contesto:
    def __init__(self, con):
        self.con = con
        self.esa, self.pezzi, self.maschera = griglia()
        self.attivi = self.esa[self.esa.abitato].reset_index(drop=True)
        self.centri = self.attivi[["x_km", "y_km"]].values
        self.camp = Campionatore(self.pezzi, PARAMETRI_H3)
        self.comuni = pd.read_sql("select * from silver_comuni", con)
        self.nomi = self.comuni.comune.tolist()
        self.var = pd.read_sql("select * from silver_varianti", con)
        self.pop = pd.read_csv(ROOT / "data" / "popolazione_comuni.csv", dtype={"istat": str}) \
            .set_index("istat").popolazione.reindex(self.comuni.istat).values.astype(float)
        # matrice comuni x esagoni: media pesata per popolazione (o area) dei pezzi di ogni comune
        pos = pd.Series(np.arange(len(self.attivi)), index=self.attivi.h3)
        p = self.pezzi[self.pezzi.h3.isin(pos.index)].copy()
        p["w"] = np.where(p.groupby("comune").popolazione.transform("sum") > 0, p.popolazione, p.area_km2)
        p["w"] /= p.groupby("comune").w.transform("sum")
        ci = {c: i for i, c in enumerate(self.nomi)}
        self.A = sparse.csr_matrix((p.w, (p.comune.map(ci), pos[p.h3].values)),
                                   shape=(len(self.nomi), len(self.attivi)))
        self.ci = ci

    def dati(self, parola, livello="lessema"):
        g = self.var[self.var.parola == parola]
        comuni, varianti, Y = matrice_risposte(g, livello)
        return comuni, varianti, Y

    def kernel_comune(self, comuni, Y, par, seeds):
        """Stima su esagoni (media sui seed) aggregata ai comuni."""
        k = par["k_vicini_poche"] if self.parola in par["parole_poche"] else par["k_vicini"]
        prior = Y.sum(0) / Y.sum()
        acc = 0
        for s in seeds:
            pts = self.camp.punti(comuni, np.random.default_rng(s))
            acc = acc + kernel(pts, Y, self.centri, prior, par, k)[0]
        return self.A @ (acc / len(seeds))


def punteggio(p_comune, ci, comuni, Y):
    """Log-score medio per risposta: sum_k peso_k * log p_k nel comune della risposta."""
    P = p_comune[[ci[c] for c in comuni]]
    return float((Y * np.log(np.clip(P, 1e-9, 1))).sum() / Y.sum())


def blocchi(n, seed=0):
    return np.random.default_rng(seed).integers(0, BLOCCHI, n)


# ---------------------------------------------------------------- parti

def semi(ctx):
    righe = []
    for parola in ["Roncola", "Sasso", "l'Asso di Coppe", "Pop Corn", "ciabatta"]:
        ctx.parola = parola
        for livello in ("lessema", "pronuncia"):
            comuni, varianti, Y = ctx.dati(parola, livello)
            k = PARAMETRI_H3["k_vicini_poche"] if parola in PARAMETRI_H3["parole_poche"] else PARAMETRI_H3["k_vicini"]
            prior = Y.sum(0) / Y.sum()
            stime = {}
            for nome, seeds in {"A": range(0, 10), "B": range(100, 110), "1": [200]}.items():
                acc = 0
                for s in seeds:
                    acc = acc + kernel(ctx.camp.punti(comuni, np.random.default_rng(s)), Y, ctx.centri,
                                       prior, PARAMETRI_H3, k)[0]
                stime[nome] = acc / len(seeds)
            w = ctx.attivi.popolazione.values / ctx.attivi.popolazione.sum()
            diff = lambda a, b: float(((stime[a].argmax(1) != stime[b].argmax(1)) * w).sum())
            righe.append({"parola": parola, "livello": livello,
                          "dominante_diversa_10_vs_10": round(diff("A", "B"), 4),
                          "dominante_diversa_1_vs_10": round(diff("1", "A"), 4),
                          "max_diff_prob_10_vs_10": round(float(np.abs(stime["A"] - stime["B"]).max()), 4)})
            print("  semi", parola, livello)
    df = pd.DataFrame(righe)
    df.to_csv(OUT / "semi.csv", index=False)
    return df


def cv(ctx):
    righe = []
    coord = _km(ctx.comuni.lon.values, ctx.comuni.lat.values)
    for parola in ctx.var.parola.unique():
        ctx.parola = parola
        comuni, varianti, Y = ctx.dati(parola)
        f = blocchi(len(Y))
        for b in range(BLOCCHI):
            tr, te = f != b, f == b
            prior = Y[tr].sum(0) / Y[tr].sum()
            r = {"parola": parola, "blocco": b, "n_test": int(te.sum())}
            r["solo prior provinciale"] = punteggio(np.tile(prior, (len(ctx.nomi), 1)), ctx.ci, comuni[te], Y[te])
            # quote osservate nel comune, con lo stesso prior di Dirichlet (nessuno smoothing spaziale)
            N = np.zeros((len(ctx.nomi), Y.shape[1]))
            np.add.at(N, [ctx.ci[c] for c in comuni[tr]], Y[tr])
            a = PARAMETRI_H3["alpha_prior"]
            r["comune senza smoothing"] = punteggio((N + a * prior) / (N.sum(1, keepdims=True) + a),
                                                    ctx.ci, comuni[te], Y[te])
            r["kernel sui centroidi (fase 1)"] = punteggio(stima(N, coord, N.sum(0), PARAMETRI)[0],
                                                           ctx.ci, comuni[te], Y[te])
            for nome, mod in CONFIGURAZIONI.items():
                par = {**PARAMETRI_H3, **mod}
                p = ctx.kernel_comune(comuni[tr], Y[tr], par, range(SEED_CV))
                r[f"esagoni: {nome}"] = punteggio(p, ctx.ci, comuni[te], Y[te])
            righe.append(r)
        print("  cv", parola)
    df = pd.DataFrame(righe)
    df.to_csv(OUT / "cv_blocchi.csv", index=False)
    return df


def _bym2_input(ctx, comuni, Y, varianti, soglia=0.02):
    """Matrice comuni x varianti; le varianti sotto il 2% finiscono in un'unica categoria."""
    q = Y.sum(0) / Y.sum()
    tieni = np.flatnonzero(q >= soglia)
    resto = np.flatnonzero(q < soglia)
    M = np.column_stack([Y[:, tieni]] + ([Y[:, resto].sum(1)] if len(resto) else []))
    N = np.zeros((len(ctx.nomi), M.shape[1]))
    np.add.at(N, [ctx.ci[c] for c in comuni], M)
    nomi = [varianti[i] for i in tieni] + (["(altre)"] if len(resto) else [])
    return N, nomi, tieni, resto


def _riduci(P, tieni, resto):
    return np.column_stack([P[:, tieni]] + ([P[:, resto].sum(1)] if len(resto) else []))


def bym2(ctx):
    adiacenze = list(pd.read_sql("select * from silver_adiacenze", ctx.con).itertuples(index=False, name=None))
    archi = grafo(ctx.comuni, adiacenze)
    s = scala(len(ctx.nomi), archi)
    w = ctx.pop / ctx.pop.sum()
    righe, cvr, stime = [], [], {}
    for parola in ctx.var.parola.unique():
        ctx.parola = parola
        comuni, varianti, Y = ctx.dati(parola)
        N, nomi, tieni, resto = _bym2_input(ctx, comuni, Y, varianti)
        t = time.time()
        pb, info = stima_bym2(N, archi, s)
        pk = _riduci(ctx.kernel_comune(comuni, Y, PARAMETRI_H3, range(PARAMETRI_H3["seed"])), tieni, resto)
        stime[parola] = {"varianti": nomi, "bym2": pb.round(4).tolist(), "kernel": pk.round(4).tolist()}
        osservati = N.sum(1) > 0
        righe.append({"parola": parola, "categorie": len(nomi),
                      "dominante_uguale_pop": round(float(((pb.argmax(1) == pk.argmax(1)) * w).sum()), 4),
                      "dominante_uguale_comuni": round(float((pb.argmax(1) == pk.argmax(1)).mean()), 4),
                      "diff_media_prob": round(float(np.abs(pb - pk).sum(1).mean() / 2), 4),
                      "corr_prob": round(float(np.corrcoef(pb.ravel(), pk.ravel())[0, 1]), 4),
                      "comuni_osservati": int(osservati.sum()),
                      "rho_medio": round(float(np.mean(info["rho"])), 3),
                      "sigma_medio": round(float(np.mean(info["sigma"])), 3),
                      "divergenze": info["divergenze"], "rhat_max": round(info.get("rhat_max", np.nan), 3),
                      "secondi": round(time.time() - t)})
        print("  bym2", parola, righe[-1]["dominante_uguale_pop"])
        if parola in PAROLE_CV_BYM2:
            f = blocchi(len(Y))
            for b in range(BLOCCHI):
                tr, te = f != b, f == b
                # stesse categorie del modello completo
                Ntr = np.zeros_like(N)
                np.add.at(Ntr, [ctx.ci[c] for c in comuni[tr]], _riduci(Y[tr], tieni, resto))
                Yte = _riduci(Y[te], tieni, resto)
                pbt, _ = stima_bym2(Ntr, archi, s, seed=b)
                pkt = _riduci(ctx.kernel_comune(comuni[tr], Y[tr], PARAMETRI_H3, range(SEED_CV)), tieni, resto)
                cvr.append({"parola": parola, "blocco": b,
                            "bym2": punteggio(pbt, ctx.ci, comuni[te], Yte),
                            "kernel esagoni": punteggio(pkt, ctx.ci, comuni[te], Yte)})
            print("  cv bym2", parola)
    df = pd.DataFrame(righe)
    df.to_csv(OUT / "bym2_confronto.csv", index=False)
    pd.DataFrame(cvr).to_csv(OUT / "bym2_cv.csv", index=False)
    (OUT / "bym2_stime.json").write_text(json.dumps({"comuni": ctx.nomi, "parole": stime}, ensure_ascii=False))
    return df


# ---------------------------------------------------------------- mappe

def _opacita(consenso, sbiadito):
    op = 0.15 + 0.85 * np.clip((consenso - 0.3) / 0.7, 0, 1)
    return np.where(sbiadito, op * 0.5, op)


def _base(ax, gj):
    for f in gj["features"]:
        for poly in _anelli(f["geometry"]):
            xs, ys = np.array(poly[0]).T
            ax.plot(xs, ys, color="#ffffff", lw=0.35, alpha=0.8)
    ax.set_aspect(1 / np.cos(np.radians(45.75)))
    ax.axis("off")


def _legenda(ax, var):
    for v in var.itertuples():
        ax.scatter([], [], marker="s", s=60, color=v.colore, label=f"{v.variante} — {v.quota_provincia:.0%}")
    ax.legend(loc="lower left", frameon=False, fontsize=8)


def mappa_esagoni(con, parola, livello, colonna="consenso"):
    stima_ = pd.read_sql("select s.*, e.lon, e.lat from gold_stima_esagono s join gold_esagoni e using(h3) "
                         "where parola=? and livello=?", con, params=(parola, livello))
    var = pd.read_sql("select * from gold_varianti where parola=? and livello=?", con, params=(parola, livello))
    var = var[var.variante.isin(stima_.dominante.unique())]
    iso = pd.read_sql("select * from gold_isoglosse_esagono where parola=? and livello=? and tipo='netta'",
                      con, params=(parola, livello))
    colore = dict(zip(var.variante, var.colore))
    poligoni = [[(lng, lat) for lat, lng in h3.cell_to_boundary(c)] for c in stima_.h3]
    fig, ax = plt.subplots(figsize=(8, 8.6), facecolor="#fbfaf7")
    if colonna == "consenso":
        rgba = matplotlib.colors.to_rgba_array(stima_.dominante.map(colore))
        rgba[:, 3] = _opacita(stima_.consenso.values, stima_.sbiadito.values)
        titolo = f"{parola} — {livello}"
    else:
        rgba = plt.cm.magma_r(np.clip(1 - stima_.stabilita_seed.values, 0, 0.5) / 0.5)
        titolo = f"{parola} — {livello}: quota di seed in disaccordo con la dominante"
    ax.add_collection(PolyCollection(poligoni, facecolors=rgba, edgecolors="none"))
    gj = json.loads(GEOJSON.read_text())
    _base(ax, gj)
    ll = dict(zip(stima_.h3, zip(stima_.lon, stima_.lat)))
    for a, b in iso[["h3_a", "h3_b"]].itertuples(index=False):
        e = h3.cells_to_directed_edge(a, b) if h3.are_neighbor_cells(a, b) else None
        if e:
            (la1, lo1), (la2, lo2) = h3.directed_edge_to_boundary(e)
            ax.plot([lo1, lo2], [la1, la2], color="#222", lw=0.9)
    ax.autoscale()
    ax.set_title(titolo, family="serif", fontsize=15, loc="left")
    if colonna == "consenso":
        _legenda(ax, var)
    nome = f"esagoni_{slug(parola)}_{livello}" + ("" if colonna == "consenso" else "_stabilita")
    fig.savefig(OUT / f"{nome}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def mappa_confronto(con, parola):
    st = json.loads((OUT / "bym2_stime.json").read_text())
    s = st["parole"][parola]
    var = pd.read_sql("select variante, colore, quota_provincia from gold_varianti "
                      "where parola=? and livello='lessema'", con, params=(parola,))
    colore = {**dict(zip(var.variante, var.colore)), "(altre)": "#b9b5ad"}
    gj = json.loads(GEOJSON.read_text())
    pos = {c: i for i, c in enumerate(st["comuni"])}
    fig, axs = plt.subplots(1, 2, figsize=(14, 7.5), facecolor="#fbfaf7")
    for ax, chiave, titolo in zip(axs, ["kernel", "bym2"], ["Kernel su esagoni (aggregato per comune)", "BYM2"]):
        P = np.array(s[chiave])
        for f in gj["features"]:
            i = pos[f["properties"]["name"]]
            k = P[i].argmax()
            c = matplotlib.colors.to_rgba(colore[s["varianti"][k]], float(_opacita(P[i, k], False)))
            for poly in _anelli(f["geometry"]):
                ax.fill(*np.array(poly[0]).T, color=c, lw=0)
        _base(ax, gj)
        ax.set_title(f"{parola}: {titolo}", family="serif", fontsize=13, loc="left")
    _legenda(axs[0], var[var.variante.isin(s["varianti"])])
    fig.savefig(OUT / f"confronto_bym2_{slug(parola)}.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def mappe(ctx):
    for parola, livello in [("Roncola", "lessema"), ("Sasso", "lessema"), ("ciabatta", "pronuncia"),
                            ("tasca", "lessema"), ("maiale", "lessema"), ("Pop Corn", "lessema")]:
        mappa_esagoni(ctx.con, parola, livello)
    mappa_esagoni(ctx.con, "l'Asso di Coppe", "lessema", colonna="stabilita")
    if (OUT / "bym2_stime.json").exists():
        for parola in ["Roncola", "maiale", "Libellula"]:
            mappa_confronto(ctx.con, parola)
    print("  mappe ok")


# ---------------------------------------------------------------- report

def _md(df):
    cols = df.columns.tolist()
    righe = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        righe.append("| " + " | ".join(f"{x:.3f}" if isinstance(x, float) else str(x) for x in r) + " |")
    return "\n".join(righe)


def report(ctx):
    parti = [f"# Risultati della validazione (fase 2)\n\nGenerato da `python3 build/validazione.py`.\n\n"
             f"Maschera: {ctx.maschera}.\n"]
    if (OUT / "semi.csv").exists():
        parti += ["## Seed\n", _md(pd.read_csv(OUT / "semi.csv")), ""]
    if (OUT / "cv_blocchi.csv").exists():
        d = pd.read_csv(OUT / "cv_blocchi.csv")
        modelli = [c for c in d.columns if c not in ("parola", "blocco", "n_test")]
        # media pesata per numero di risposte di test
        tot = d.groupby("parola").apply(lambda g: pd.Series({m: np.average(g[m], weights=g.n_test) for m in modelli}),
                                        include_groups=False)
        rif = "esagoni: base"
        sintesi = pd.DataFrame({"modello": modelli,
                                "log-score medio": [tot[m].mean() for m in modelli],
                                "parole in cui batte la base": [int((tot[m] > tot[rif] + 1e-9).sum()) for m in modelli],
                                "guadagno sul prior (bit)": [(tot[m] - tot["solo prior provinciale"]).mean() / np.log(2)
                                                             for m in modelli]})
        parti += ["## Validazione incrociata (5 blocchi, livello lessema)\n",
                  "Log-score medio per risposta lasciata fuori (più alto è meglio), media sulle 29 parole.\n",
                  _md(sintesi.sort_values("log-score medio", ascending=False)), "",
                  "Per parola:\n", _md(tot.reset_index().round(4)), ""]
    if (OUT / "bym2_confronto.csv").exists():
        parti += ["## Confronto con BYM2 (livello lessema, per comune)\n",
                  _md(pd.read_csv(OUT / "bym2_confronto.csv")), ""]
        c = pd.read_csv(OUT / "bym2_cv.csv")
        if len(c):
            c = c.groupby("parola")[["bym2", "kernel esagoni"]].mean().reset_index()
            parti += ["Validazione incrociata BYM2 contro kernel (log-score medio, 5 blocchi):\n", _md(c), ""]
    (OUT / "risultati.md").write_text("\n".join(parti))
    print("  report ok")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parti = sys.argv[1:] or ["semi", "cv", "bym2", "mappe", "report"]
    with sqlite3.connect(DB) as con:
        ctx = Contesto(con)
        for p in parti:
            globals()[p](ctx)


if __name__ == "__main__":
    main()
