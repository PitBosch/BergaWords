# ANALISI — "An Extremely Detailed Map of New York City Neighborhoods" (NYT Upshot, 2023)

> **Fonte di questa analisi.** Da questa sessione non riesco a raggiungere nytimes.com né web.archive.org, perché la rete li blocca.
> Ho scritto il documento a memoria, da quello che so del pezzo e dello stack interattivo del NYT.
> I punti marcati **[da verificare]** vanno confermati con screenshot o con l'accesso alla pagina.
> La sezione 6 adatta tutto ai dati di BergaWords.

---

## 1. Layout

### Desktop
- **Testata e titolo.** In alto c'è la testata dell'Upshot, poi il titolo grande in serif (Cheltenham), il sommario in serif più leggero, la firma e la data. Il blocco testo è stretto, centrato, sui 600 px.
- **Mappa protagonista.** Subito sotto l'intro c'è la mappa a larghezza piena, alta quasi quanto la finestra. Si apre su tutta la città con un leggero tilt a nord **[da verificare]**.
- **Ricerca.** Il campo "Search for an address" si sovrappone alla mappa, in alto a sinistra, con un autocomplete a tendina.
- **Controlli.** Lo zoom +/− sta in un angolo, in piccolo e con lo stile sobrio del NYT. I controlli di Mapbox sono nascosti.
- **Legenda.** È ridotta al minimo. I nomi dei quartieri sono scritti direttamente sulla mappa e fanno da legenda. Una piccola chiave spiega l'intensità: colore pieno vuol dire "most agree", colore sbiadito "less agreement" **[da verificare la forma esatta]**.
- **Sotto la mappa.** L'articolo prosegue con sezioni di approfondimento sui casi contesi (confini dibattuti, nomi nuovi o di marketing, nomi in disuso). Ogni sezione ha una mappa piccola e statica centrata sulla zona e cita commenti dei lettori. In fondo c'è la nota di metodo.

### Mobile
- Titolo e intro sono impilati, poi viene la mappa a tutta larghezza e alta circa 70–80% dello schermo.
- La ricerca resta sopra la mappa, a tutta larghezza.
- Il pannello dei dettagli appare come foglio in basso (bottom sheet) che copre una parte della mappa. Su desktop è un tooltip o una card flottante.
- La mappa usa il pan con due dita, così lo scroll della pagina con un dito resta libero **[da verificare]**.
- Le mappe delle sezioni di approfondimento diventano immagini statiche a tutta larghezza.

---

## 2. Stile visivo

### Base map
- È una base chiarissima e quasi monocroma: fondo bianco caldo o grigio chiarissimo, acqua grigio-azzurro tenue.
- Le strade sono sottili, in grigio chiaro, e alle scale alte compaiono solo le principali.
- I parchi sono appena accennati, in verde-grigio molto desaturato.
- Restano nascosti POI, icone, numeri civici, nomi delle strade minori e la maggior parte delle etichette di base. Restano i nomi di strade principali e acque solo agli zoom alti.
- I confini amministrativi (borough) sono assenti o appena tratteggiati.
- Lo scopo è lasciare tutto il contrasto ai colori dei quartieri.

### Palette dei quartieri
- È categorica, con circa 8–12 tinte medie e pastello: verdi, arancio, viola, azzurri, gialli, rosa.
- I colori sono assegnati in modo che quartieri adiacenti abbiano tinte diverse, come in una colorazione di grafo.
- Il colore dice *quale* nome domina. La saturazione o l'opacità dice *quanto* domina.

### Consenso e contesa
- **Consenso alto.** Dove quasi tutti concordano, il colore è pieno.
- **Contesa.** Dove i nomi si dividono il colore si schiarisce verso il fondo, quindi le zone contese appaiono come fasce chiare tra due macchie.
- **Confini.** Mancano linee di contorno nette, e il confine emerge come una sfumatura tra due tinte. Gli effetti di sfumatura e "nebbia" sono il tratto distintivo della mappa.
- **Poche risposte.** Gli isolati con troppe poche risposte restano trasparenti o grigi.

### Etichette e font
- I nomi dei quartieri sono in sans (NYT Franklin), in grassetto medio e grigio scuro, con alone bianco. Sono posizionati al centro di massa dell'area dominante e diventano più numerosi con lo zoom (prima i quartieri grandi, poi quelli piccoli).
- La UI (ricerca, pannello, percentuali) usa NYT Franklin.
- Titoli e corpo testo usano NYT Cheltenham e NYT Imperial.
- Le ombre sono quasi assenti. Il pannello e la ricerca hanno un'ombra leggera (circa `0 2px 8px rgba(0,0,0,.15)`) e un bordo grigio di 1 px.

---

## 3. Interazioni

| Azione | Effetto |
|---|---|
| **Hover** (desktop) | Un tooltip vicino al cursore mostra i nomi più votati in quel punto, con percentuale e barra orizzontale colorata nel colore del quartiere. |
| **Click / tap** | Fissa il pannello sul punto e piazza un marker. Su mobile apre il bottom sheet. **[da verificare]** Selezionare un nome potrebbe evidenziare l'estensione di quel quartiere su tutta la mappa, come gradiente di "quanti lo chiamano così". |
| **Zoom** | Funziona con rotella, pinch e pulsanti. Con lo zoom aumentano le etichette e la base map mostra più strade. La griglia dei dati resta la stessa (isolati). |
| **Ricerca indirizzo** | L'autocomplete propone indirizzi. Alla selezione la mappa vola al punto (flyTo), piazza il marker e apre il pannello. |

### Contenuto del pannello
- In testa c'è l'indirizzo o la località.
- Seguono le righe "**Nome** — 74%", ognuna con barra orizzontale piena per la sua quota. Le righe sono ordinate per quota e mostrano fino a 4–5 nomi più "Other".
- In fondo c'è il numero di risposte che coprono quel punto, nella forma "Based on N responses" **[da verificare la dicitura]**.
- I commenti dei lettori compaiono nelle sezioni di approfondimento dell'articolo. Nel pannello della mappa principale mancano **[da verificare]**.

---

## 4. Logica dei dati

1. **Raccolta.** Ogni lettore disegnava a mano il contorno del proprio quartiere su una mappa e gli dava un nome (con suggerimenti dall'elenco, oltre al testo libero). Indicava anche CAP o indirizzo di residenza.
2. **Normalizzazione dei nomi.** Varianti e refusi vengono uniti in un nome canonico (es. "Bed Stuy" e "Bedford-Stuyvesant").
3. **Griglia fine.** Ogni poligono disegnato viene intersecato con gli isolati di censimento (census blocks).
4. **Quote.** Per ogni isolato e ogni nome:
   `quota(nome) = numero di poligoni con quel nome che coprono l'isolato / numero totale di poligoni che lo coprono`.
5. **Nome dominante.** È il nome con la quota più alta (pluralità).
6. **Poche risposte.** Sotto una soglia minima di poligoni l'isolato resta senza colore. In più si scartano disegni anomali, troppo grandi o assurdi.
7. **Confini netti o sfumati.** Dipendono dalla quota del nome dominante, che pilota l'opacità del colore. Dove le quote crollano in pochi isolati il confine appare netto; dove scendono gradualmente su molti isolati appare sfumato.
8. **Etichette.** Ogni nome viene posizionato sul punto interno dell'area dove domina, pesato per quota.

---

## 5. Stack probabile

- **Framework.** I grafici interattivi del NYT dal 2022 in poi girano sul framework interno basato su Svelte/SvelteKit, chiamato "Birdkit".
- **Mappa.** Mapbox GL JS, oppure MapLibre nelle versioni più recenti, con base map personalizzata.
- **Tiles.** Vector tiles in formato MVT/PBF servite da `static01.nyt.com`, oppure da un archivio unico tipo PMTiles. I dati dei quartieri sono probabilmente un layer vettoriale di isolati con attributi `top_name` e `top_share` più una lista di quote. Lo stile usa espressioni data-driven per colore e opacità.
- **Geocoder.** Mapbox Geocoding o un servizio interno per l'autocomplete degli indirizzi.
- **Font.** NYT Franklin, Cheltenham e Imperial, tutti proprietari.

Ogni punto di questa sezione è **[da verificare]**, perché richiede il codice sorgente della pagina.

---

## 6. Adattamento a BergaWords (proposta)

### I dati sono diversi
| NYT | BergaWords (`comesidice.xlsx`) |
|---|---|
| un poligono disegnato per risposta | il nome del paese per risposta |
| nome del quartiere | variante dialettale della parola (es. *Bagnàt*, *Trabatit*) |
| una sola mappa | 29 mappe, una per parola, con 800–1.700 risposte ciascuna |
| isolati di censimento | 243 comuni (`public/data/bergamo.geojson`) |

### Corrispondenze proposte
- **"Quartiere" → variante.** Il colore indica la variante dominante, l'intensità indica quanto domina.
- **Selettore della parola.** È l'unico elemento nuovo della UI rispetto al NYT: un menu a tendina o una barra di chip sopra la mappa.
- **Unità fine: esagoni H3 a risoluzione 8**, circa 0,7 km² e qualche decina di migliaia di celle per la provincia, ritagliati sul confine provinciale. Ogni cella riceve le quote stimate con una media pesata delle risposte dei comuni vicini, con un kernel gaussiano sulla distanza dal centroide (banda di circa 4–6 km) e un peso maggiore per il comune che contiene la cella. In questo modo si ottengono i confini sfumati tipici del NYT. Le celle restano una stima: le risposte sono per comune.
  - **Alternativa senza stima:** colore per comune, con confini netti sui limiti comunali.
- **Poche risposte.** Una cella con meno di 3 risposte pesate entro la banda resta grigia, con la scritta "dati insufficienti".
- **Pannello.** In testa il comune o l'indirizzo, poi la variante e la percentuale con barra per le prime 4 più "altre", poi la dicitura "N risposte dal comune, M nei dintorni".
- **Ricerca.** Cerca tra i comuni in locale, senza servizi esterni. La ricerca di indirizzi richiederebbe un geocoder esterno come Nominatim o Photon, che ha limiti d'uso.
- **Base map.** MapLibre GL con lo stile "positron" di OpenFreeMap, alleggerito: niente POI, solo strade principali, acqua grigio-azzurra.
- **Font liberi equivalenti.** Libre Franklin per UI ed etichette, una serif tipo Source Serif o Libre Caslon per titolo e testo.
- **Pipeline.** Lo script `build/build.py` (pandas, geopandas, h3) legge l'xlsx, normalizza le varianti (unendo per esempio "Bagnàt" e "Bagnat ", e riusando le mappature già presenti in `public/data/words/*.json`) e scrive un file per parola: un GeoJSON compresso per le celle, oppure un PMTiles se il peso supera circa 2 MB.
- **Deploy.** Consigliato GitHub Pages tramite Actions; supporta le richieste a range che servono a PMTiles.

### Decisioni che aspettano il tuo ok
1. Unità fine: H3 con interpolazione (consigliata), oppure per comune.
2. Titolo e autore: "Come si dice…?" e "AverageBerghemGuy"?
3. Va bene la sola ricerca per comune, senza indirizzi?
