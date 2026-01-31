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
