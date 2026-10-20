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
La stima attuale è per comune; la griglia H3 della fase 2 si aggiungerà come nuove tabelle gold.
