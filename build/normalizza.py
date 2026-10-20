"""Applica varianti.yaml alle risposte grezze.

Ogni risposta diventa una o più righe (parola, comune, lessema, pronuncia, peso):
le risposte multiple si dividono in parti uguali, quelle escluse o di commento
restano fuori dalla stima. Genera anche analisi/assegnazioni.md per il controllo.

    python3 build/normalizza.py
"""
import re
import unicodedata
from collections import Counter, defaultdict

import pandas as pd
import yaml

from carica import ROOT, carica_risposte

VARIANTI = ROOT / "varianti.yaml"
ALTRE = "Altre forme"

ARTICOLI = re.compile(r"^(?:(?:ol|la|il|el|lo|al)\s+|l['’]\s*)", re.I)
SEPARATORI = re.compile(r"\s*(?:/|\\|,|;|:|\be/o\b|\boppure\b|\bo\b|\be\b|\bsia?\b|\bche\b|\bma anche\b|\bo anche\b)\s*", re.I)
MULTI = re.compile(r"/|\\|,|\be/o\b|\boppure\b|\bsia?\b.+\bche\b|\b(o|e)\b", re.I)
RUMORE = re.compile(r"non (lo )?so|so m[iì]a|al so mia|^boh|sconosciut|nessun|non saprei|non si dice|"
                    r"entramb|tutt[ie] e (tre|3|due)|le prime due", re.I)
ALIAS_COMUNI = {"Villa d'Almè": "Villa d'Alme", "Almè": "Alme"}
FINESTRA_DUPLICATI = 5  # secondi


def chiave(s):
    """Chiave di confronto: conserva ö e ü, toglie il resto di accenti, articoli, doppie e segni."""
    s = str(s).strip().lower().replace("ô", "ö").replace("ë", "e")
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s).strip()
    s = ARTICOLI.sub("", s)
    out = []
    for c in s:
        if c in "öü":
            out.append(c)
        else:
            base = unicodedata.normalize("NFD", c)[0]
            if "a" <= base <= "z":
                out.append(base)
    return re.sub(r"(.)\1+", r"\1", "".join(out))


def _testo(s):
    return re.sub(r"\s+", " ", str(s).strip()).casefold()


class Regole:
    def __init__(self, path=VARIANTI):
        self.parole = {}
        for parola, spec in yaml.safe_load(path.read_text()).items():
            regole = [(lessema, pron, re.compile(rx))
                      for lessema, pronunce in spec["lessemi"].items()
                      for pron, rxs in pronunce.items() for rx in rxs]
            escluse = {_testo(e) for e in spec.get("escluse") or []}
            self.parole[parola] = (regole, escluse)

    def assegna(self, parola, testo):
        """(lessema, pronuncia) per una singola forma."""
        k = chiave(testo)
        for lessema, pron, rx in self.parole[parola][0]:
            if rx.search(k):
                return lessema, pron
        return ALTRE, ALTRE

    def classifica(self, parola, valore):
        """Restituisce (tipo, [(lessema, pronuncia, peso), ...])."""
        v = str(valore).strip()
        if not v or _testo(v) in self.parole[parola][1] or RUMORE.search(v):
            return "esclusa", []
        if len(v.split()) > 5:
            return "commento", []
        if MULTI.search(v):
            pezzi = [p for p in SEPARATORI.split(v) if p and chiave(p)]
            assegnati = {self.assegna(parola, p) for p in pezzi} - {(ALTRE, ALTRE)}
            if len(assegnati) >= 2:
                return "multipla", [(l, p, 1 / len(assegnati)) for l, p in sorted(assegnati)]
        lessema, pron = self.assegna(parola, v)
        return ("altra" if lessema == ALTRE else "singola"), [(lessema, pron, 1.0)]


def segna_duplicati(d):
    d = d.sort_values("timestamp")
    dt = d.groupby(["parola", "comune", "variante_grezza"])["timestamp"].diff().dt.total_seconds()
    return dt < FINESTRA_DUPLICATI


def normalizza(d=None, regole=None):
    d = carica_risposte() if d is None else d
    regole = regole or Regole()
    d = d.copy()
    d["comune"] = d["comune_grezzo"].astype(str).str.strip().replace(ALIAS_COMUNI)
    d["duplicato"] = segna_duplicati(d).reindex(d.index).fillna(False)
    tipi, righe = [], []
    for i, r in d.iterrows():
        tipo, parti = regole.classifica(r.parola, r.variante_grezza)
        if r.duplicato:
            tipo, parti = "duplicato", []
        tipi.append(tipo)
        for lessema, pron, peso in parti:
            righe.append((i, r.parola, r.comune, lessema, pron, peso))
    d["tipo"] = tipi
    lungo = pd.DataFrame(righe, columns=["risposta", "parola", "comune", "lessema", "pronuncia", "peso"])
    return d, lungo


def report(d, lungo, path):
    righe = ["# Assegnazioni delle risposte", "",
             "Generato da `build/normalizza.py` applicando `varianti.yaml`. "
             "Per ogni parola: lessema → pronuncia → grafie grezze con il numero di risposte.", ""]
    tot = d["tipo"].value_counts()
    righe += ["| Tipo | Risposte |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in tot.items()] + [""]
    for parola, g in d.groupby("parola", sort=False):
        lg = lungo[lungo.parola == parola].merge(d[["variante_grezza"]], left_on="risposta", right_index=True)
        righe += [f"## {parola}", ""]
        per_lessema = lg.groupby("lessema")["peso"].sum().sort_values(ascending=False)
        for lessema, n in per_lessema.items():
            righe.append(f"- **{lessema}** — {n:.0f}")
            sub = lg[lg.lessema == lessema]
            for pron, m in sub.groupby("pronuncia")["peso"].sum().sort_values(ascending=False).items():
                forme = Counter(sub[sub.pronuncia == pron].variante_grezza.astype(str).str.strip())
                elenco = ", ".join(f"{f} ({c})" for f, c in forme.most_common(12))
                altro = f" … +{len(forme) - 12} grafie" if len(forme) > 12 else ""
                righe.append(f"  - {pron} — {m:.0f}: {elenco}{altro}")
        for tipo in ("esclusa", "commento", "duplicato"):
            forme = Counter(g[g.tipo == tipo].variante_grezza.astype(str).str.strip())
            if forme and tipo != "duplicato":
                righe.append(f"- _{tipo}_ ({sum(forme.values())}): " + "; ".join(f"{f} ({c})" for f, c in forme.most_common()))
            elif forme:
                righe.append(f"- _duplicati scartati_: {sum(forme.values())}")
        righe.append("")
    path.write_text("\n".join(righe))


def main():
    d, lungo = normalizza()
    (ROOT / "analisi").mkdir(exist_ok=True)
    report(d, lungo, ROOT / "analisi" / "assegnazioni.md")
    print(d["tipo"].value_counts().to_string())
    print(lungo.groupby("parola").apply(lambda g: g[g.lessema == ALTRE].peso.sum() / g.peso.sum(),
                                        include_groups=False).sort_values().round(3).to_string())


if __name__ == "__main__":
    main()
