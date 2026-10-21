"""Scarica in data/istat/ le sezioni di censimento 2021 della Lombardia (shapefile, ~60 MB).

    python3 build/scarica_istat.py

Richiede che www.istat.it sia raggiungibile. In alternativa si può scaricare a mano R03_21.zip
dalla pagina "Basi territoriali e variabili censuarie" dell'ISTAT ed estrarne la cartella SHP
in data/istat/. Lo shapefile 2021 ha già la popolazione residente per sezione (POP21).
"""
import io
import sys
import time
import urllib.request
import zipfile

from esagoni import ISTAT

URL = "https://www.istat.it/storage/cartografia/basi_territoriali/2021/R03_21.zip"


def scarica(url, tentativi=4):
    for i in range(tentativi):
        try:
            return urllib.request.urlopen(url, timeout=300).read()
        except Exception as e:
            if i == tentativi - 1:
                sys.exit(f"non raggiungibile ({e}): scarica il file a mano ed estrailo in {ISTAT}")
            time.sleep(2 ** (i + 1))


def main():
    ISTAT.mkdir(parents=True, exist_ok=True)
    print("scarico", URL)
    with zipfile.ZipFile(io.BytesIO(scarica(URL))) as z:
        for nome in z.namelist():
            if nome.startswith("SHP/") and not nome.endswith("/"):
                (ISTAT / nome.split("/")[-1]).write_bytes(z.read(nome))
    print("ok:", sorted(p.name for p in ISTAT.iterdir()))


if __name__ == "__main__":
    main()
