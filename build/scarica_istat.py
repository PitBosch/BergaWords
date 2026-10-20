"""Scarica in data/istat/ le basi territoriali e la popolazione per sezione di censimento (Lombardia).

    python3 build/scarica_istat.py

Richiede che www.istat.it sia raggiungibile. In alternativa si possono scaricare a mano i due zip
dalla pagina "Basi territoriali e variabili censuarie" dell'ISTAT ed estrarli in data/istat/:
esagoni.py cerca lì uno shapefile di sezioni e, se non ha già una colonna di popolazione,
un CSV di indicatori con le colonne SEZ21_ID (o SEZ2011) e P1.
"""
import io
import sys
import urllib.request
import zipfile

from esagoni import ISTAT

URL = [
    "https://www.istat.it/storage/cartografia/basi_territoriali/WGS_84_UTM/2021/R03_21.zip",
    "https://www.istat.it/storage/cartografia/variabili-censuarie/dati-cpa_2021/R03_indicatori_2021_sezioni.zip",
]


def main():
    ISTAT.mkdir(parents=True, exist_ok=True)
    for url in URL:
        print("scarico", url)
        try:
            dati = urllib.request.urlopen(url, timeout=120).read()
        except Exception as e:
            sys.exit(f"non raggiungibile ({e}): scarica il file a mano ed estrailo in {ISTAT}")
        with zipfile.ZipFile(io.BytesIO(dati)) as z:
            for nome in z.namelist():
                if not nome.endswith("/"):
                    (ISTAT / nome.split("/")[-1]).write_bytes(z.read(nome))
    print("ok:", sorted(p.name for p in ISTAT.iterdir()))


if __name__ == "__main__":
    main()
