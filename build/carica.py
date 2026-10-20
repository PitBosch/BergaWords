"""Lettura di comesidice.xlsx in formato lungo: una riga per risposta."""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "comesidice.xlsx"


def carica_risposte(path=XLSX):
    righe = []
    for foglio in pd.ExcelFile(path).sheet_names:
        df = pd.read_excel(path, sheet_name=foglio)
        col_parola = next(c for c in df.columns if c.startswith("Come dici"))
        parola = re.sub(r"^Come dici\s+|\?\s*$", "", col_parola).strip()
        righe.append(pd.DataFrame({
            "modulo": int(foglio.split()[-1]),
            "timestamp": pd.to_datetime(df["Informazioni cronologiche"], errors="coerce"),
            "comune_grezzo": df["Di che paese sei?"],
            "parola": parola,
            "variante_grezza": df[col_parola],
        }))
    return pd.concat(righe, ignore_index=True)
