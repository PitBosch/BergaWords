# BergaWords - Come si dice...?

Una webapp interattiva per esplorare le varianti dialettali nella provincia di Bergamo.

## Stack Tecnologico

- **Astro** - Framework per siti statici
- **Tailwind CSS** - Styling moderno e responsivo
- **D3.js** - Visualizzazioni interattive delle mappe
- **TypeScript** - Type safety

## Sviluppo locale

```bash
# Installa le dipendenze
npm install

# Avvia il server di sviluppo
npm run dev

# Build per produzione
npm run build
```

## Struttura del progetto

```
src/
  components/     # Componenti Astro (BergamoMap, WordCard)
  data/          # Dati delle parole (words.ts)
  layouts/       # Layout principale
  pages/         # Pagine (index, [word])

public/
  data/          # Dati JSON per le mappe
    bergamo.geojson   # GeoJSON dei 243 comuni
    words/            # Dati varianti per ogni parola
```

## Deploy

Il progetto è configurato per Vercel. Basta collegare il repository e deployare.

## Crediti

- GeoJSON provincia di Bergamo: [guglielmo](https://github.com/guglielmo)
- Made with love by AverageBerghemGuy

Seguici su Instagram: [@averageberghemguy](https://www.instagram.com/averageberghemguy/)

## Database (bronze / silver / gold)

Tutti i dati stanno in `data/bergawords.sqlite`, un file SQLite apribile con qualsiasi client (es. DB Browser for SQLite, `sqlite3`, pandas). Si rigenera con:

```bash
python3 build/db.py          # bronze -> silver -> gold + export JSON
python3 build/db.py silver   # riparte da silver (es. dopo aver cambiato varianti.yaml)
python3 build/db.py gold     # solo gold (es. dopo aver cambiato i parametri)
```

| Livello | Tabella | Contenuto |
|---|---|---|
| bronze | `bronze_risposte` | una riga per risposta, esattamente come nell'Excel (foglio, riga, ora, paese, domanda, risposta) |
| bronze | `bronze_caricamenti` | file caricato, impronta sha256, data |
| silver | `silver_risposte` | risposte con comune allineato, parola, tipo (`singola`, `multipla`, `altra`, `esclusa`, `commento`, `duplicato`) |
| silver | `silver_varianti` | assegnazione a lessema e pronuncia secondo `varianti.yaml`, con peso (le multiple valgono 1/k) |
| silver | `silver_comuni`, `silver_adiacenze` | centroidi e confini in comune dei 243 comuni |
| gold | `gold_parole` | indice delle parole con divisività (informazione mutua luogo-variante, in bit) |
| gold | `gold_varianti` | varianti per parola e livello, quota provinciale, colore |
| gold | `gold_dominanti_comune` | per comune: variante dominante, consenso, n effettivo, banda, affidabilità |
| gold | `gold_stima_comune` | per comune: le 5 varianti più probabili |
| gold | `gold_isoglosse` | confini tra comuni con dominante diversa, netti o sfumati |
| gold | `gold_commenti` | risposte esplicative, mostrate con il solo comune |
| gold | `gold_meta` | data di generazione, metodo, parametri |

Il frontend legge l'export statico del gold in `public/data/gold/` (`indice.json`, `commenti.json`, `parole/<slug>.json`).

### Stima su esagoni (fase 2)

```bash
python3 build/esagoni.py        # griglia H3, stima di tutte le parole, export JSON (~3 minuti)
python3 build/validazione.py    # validazione: seed, validazione incrociata, BYM2, mappe (analisi/fase2/)
python3 build/scarica_istat.py  # sezioni di censimento ISTAT 2021 in data/istat/ (serve www.istat.it, da lanciare prima di esagoni.py)
```

`python3 build/db.py` esegue anche `esagoni.py` dopo il gold per comune. Il metodo e i risultati della validazione sono in `VALIDAZIONE.md`.

| Livello | Tabella | Contenuto |
|---|---|---|
| gold | `gold_esagoni` | celle H3 risoluzione 8: comune prevalente, popolazione, area, abitato, centro |
| gold | `gold_stima_esagono` | per parola, livello ed esagono: dominante, consenso, seconda variante, n effettivo, banda, sbiadito, stabilità tra i seed |
| gold | `gold_isoglosse_esagono` | coppie di esagoni confinanti con dominante diversa, nette o sfumate |
| gold | `gold_parole_esagoni` | divisività calcolata sugli esagoni e pesata per popolazione, quota di confini netti, quota sbiadita |

Export per il frontend: `public/data/gold/esagoni.geojson` (geometria, un esagono per feature con `id` progressivo) e `public/data/gold/esagoni/<slug>.json`, dove `celle[i]` si riferisce alla feature `i` e vale `[dominante, consenso, seconda, prob_seconda, n_eff, sbiadito, stabilità]` (le varianti sono indici nella lista `varianti`, con i colori). `isoglosse` elenca `[i, j, netta]`. `quote[i]` dà la probabilità di ogni variante nell'esagono `i`, in millesimi e nell'ordine di `varianti`.

La maschera dell'abitato usa le sezioni di censimento ISTAT 2021 con popolazione residente > 0 (`POP21` dello shapefile della Lombardia, 6.466 sezioni abitate su 11.154 in provincia, 1.102.997 residenti) se sono in `data/istat/` (cartella esclusa dal repository, si ricrea con `scarica_istat.py`). Senza, usa una maschera provvisoria: la popolazione di ogni comune (`data/popolazione_comuni.csv`, censimento ISTAT 2011 da [comuni-json](https://github.com/matteocontrini/comuni-json)) spalmata uniformemente sulla sua superficie. La maschera in uso è scritta in `gold_meta` e in `esagoni.geojson`.
