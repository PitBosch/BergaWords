# VALIDAZIONE — Fase 2

Stima su griglia H3 (`build/esagoni.py`) e sua validazione (`build/validazione.py`). Tabelle complete, generate dallo script, in [`analisi/fase2/risultati.md`](analisi/fase2/risultati.md); dati grezzi nei CSV della stessa cartella.

> **Maschera provvisoria.** Le sezioni di censimento ISTAT non sono scaricabili da questo ambiente: www.istat.it e Hugging Face (l'unica copia trovata) sono bloccati dalla rete. Per ora la popolazione di ogni comune (censimento 2011) è spalmata in modo uniforme sulla sua superficie. Dentro un comune, quindi, boschi e abitato pesano uguale. I numeri qui sotto vanno rifatti con le sezioni: `python3 build/scarica_istat.py && python3 build/esagoni.py && python3 build/validazione.py`.

## 1. Metodo

1. **Griglia.** 3.749 esagoni H3 di risoluzione 8 (0,74 km², centri a circa 0,8 km). Ogni esagono è diviso in "pezzi" per comune, con area e popolazione.
2. **Punti.** Per ogni risposta, un punto casuale in un pezzo del suo comune, scelto con probabilità proporzionale alla popolazione, più uno spostamento casuale entro 350 m.
3. **Kernel.** Per ogni esagono, la banda è la distanza del 15° punto più vicino, tra 1,5 e 6 km. I pesi sono gaussiani e si azzerano oltre 3 bande.
4. **Prior di Dirichlet.** Probabilità = (somma pesata + α · quote provinciali) / (n_eff + α), con α = 2. Dove i dati sono pochi la stima tende alle quote provinciali.
5. **Seed.** Media su 10 estrazioni. Sotto n_eff = 8 l'esagono è sbiadito; la stabilità tra i seed è salvata per ogni esagono.
6. **Isoglosse.** Coppie di esagoni confinanti con dominante diversa. Sono "nette" se la probabilità cambia di almeno 0,05 tra i due centri: il 15% dei confini.

## 2. Scelta dei parametri

Validazione incrociata a 5 blocchi sulle risposte, livello lessema, tutte le 29 parole. Il punteggio è il logaritmo della probabilità assegnata alla risposta lasciata fuori, nel suo comune (più alto è meglio). Si parte dai parametri proposti in `ANALISI.md` § 6 (k = 30, banda massima 10 km, α = 5).

| Modello | Log-score medio | Parole in cui batte la partenza |
|---|---:|---:|
| **k = 15, banda max 6 km, α = 2 (scelto)** | **−0,630** | **26 / 29** |
| k = 20, banda max 8 km, α = 2 | −0,634 | 26 |
| k = 15, banda max 6 km | −0,635 | 26 |
| k = 10 | −0,635 | 22 |
| k = 15 | −0,636 | 26 |
| banda max 6 km | −0,638 | 26 |
| α = 1 | −0,640 | 20 |
| partenza: k = 30, banda max 10 km, α = 5 | −0,642 | — |
| kernel sui centroidi comunali (fase 1) | −0,644 | 10 |
| k = 50 | −0,654 | 2 |
| α = 20 | −0,659 | 3 |
| quote del comune, senza smoothing | −0,681 | 1 |
| solo quote provinciali | −0,802 | 2 |

- **Lo smoothing spaziale serve.** Rispetto alle sole quote del comune, il kernel guadagna 0,05 nat per risposta. Rispetto alle quote provinciali il guadagno è di 0,25 bit.
- **Conviene una banda più stretta.** k = 15 e banda massima di 6 km battono k = 30 quasi ovunque. Le isoglosse vere sono più nette di quanto lasci vedere una banda larga.
- **Il prior va tenuto debole.** α = 2 è meglio di 5, e α = 20 è chiaramente peggio. Con k piccolo il prior pesa solo dove davvero mancano i dati.
- **Le tre parole con pochi dati non vogliono un k diverso.** Pop Corn, Libellula e talpa stanno meglio anch'esse con k = 15. Il trattamento separato (k = 20) previsto in `ANALISI.md` § 6 è stato quindi tolto.
- Il guadagno della configurazione scelta sulla partenza è piccolo (0,013 nat per risposta), ma costante: è migliore in 26 parole su 29.

## 3. Stabilità rispetto ai seed

Quota di popolazione in cui la variante dominante cambia tra due serie indipendenti di 10 seed (seed 0–9 contro 100–109), con i parametri scelti:

| Parola | Lessema | Pronuncia |
|---|---:|---:|
| Roncola | 0,9% | 2,1% |
| Sasso | 0,6% | 0,5% |
| ciabatta | 0,1% | 1,2% |
| Pop Corn | 2,3% | 2,6% |
| l'Asso di Coppe | 6,1% | 6,1% |

I cambi avvengono dove due varianti sono quasi alla pari: lì il consenso è basso e la mappa è comunque chiara. La probabilità di un esagono non si sposta mai di più di 0,08. Con un solo seed i cambi sono da due a cinque volte di più. Dieci seed bastano. Per le parole più incerte (gli assi) si può salire a 20 seed: il tempo di calcolo raddoppia, a circa 5 minuti.

Mappa della stabilità per l'Asso di Coppe: [`esagoni_l-asso-di-coppe_lessema_stabilita.png`](analisi/fase2/esagoni_l-asso-di-coppe_lessema_stabilita.png).

## 4. Confronto con il modello BYM2

`build/bym2.py`: logit multinomiale per comune con effetti spaziali BYM2, cioè un campo ICAR sul grafo delle adiacenze più un rumore indipendente, riscalati con il fattore di Riebler (s = 0,45). Stimato con NUTS in PyMC: 2 catene da 400 campioni, 0 divergenze su tutte le 29 parole. Le varianti sotto il 2% sono unite in un'unica categoria.

**Le due stime concordano.** Su 29 parole, la variante dominante per comune è la stessa per il 94% della popolazione in media (minimo 81%, per l'Asso di Ori). La differenza media tra le distribuzioni è di 0,06 e la correlazione tra le probabilità è di 0,98. Le divergenze stanno nelle stesse zone che il kernel mostra sbiadite: l'alta Val Brembana e i comuni con 1–3 risposte.

**Nella validazione incrociata, BYM2 prevede meglio**, su tutte e 4 le parole provate:

| Parola | BYM2 | Kernel su esagoni |
|---|---:|---:|
| Roncola | −0,467 | −0,496 |
| Sasso | −0,505 | −0,516 |
| Pop Corn | −0,975 | −1,014 |
| Libellula | −0,543 | −0,546 |

Ci sono due motivi. BYM2 usa i confini comunali come struttura di vicinanza, quindi non scavalca valli e crinali come fa la distanza in linea d'aria. Inoltre stima dai dati quanto lisciare (ρ è tra 0,55 e 0,97, quasi sempre vicino a 1: la variazione è soprattutto spaziale). Il confronto è fatto a livello di comune, che è il terreno di BYM2. Il kernel invece rende al meglio sulla mappa continua, dove BYM2 non arriva sotto il comune.

Mappe affiancate: [Roncola](analisi/fase2/confronto_bym2_roncola.png), [maiale](analisi/fase2/confronto_bym2_maiale.png), [Libellula](analisi/fase2/confronto_bym2_libellula.png).

## 5. Mappe di controllo

In `analisi/fase2/`: [Roncola](analisi/fase2/esagoni_roncola_lessema.png), [maiale](analisi/fase2/esagoni_maiale_lessema.png), [Sasso](analisi/fase2/esagoni_sasso_lessema.png), [tasca](analisi/fase2/esagoni_tasca_lessema.png), [Pop Corn](analisi/fase2/esagoni_pop-corn_lessema.png), [ciabatta per pronuncia](analisi/fase2/esagoni_ciabatta_pronuncia.png). Il colore è la variante dominante e l'intensità il consenso; le linee nere sono le isoglosse nette.

- **Roncola:** Pódet a nord-est, Pighèss a sud-ovest, Còrlass in Valle Imagna. L'alta Val Brembana è sbiadita, per pochi dati.
- **maiale:** Porsèl nelle valli e nella pianura occidentale, Sunì al centro, Ciù all'estremo ovest, Ròi nella bassa sud-orientale.
- **ciabatta** (pronuncia): sibra in pianura e a ovest, sébra all'estremo ovest e in una fascia al centro-nord, saàta a nord-est, söbra tra Val Cavallina e Sebino.

## 6. Divisività sugli esagoni

È l'informazione mutua tra luogo e variante, con i luoghi pesati per popolazione (`gold_parole_esagoni`). L'ordine resta quasi quello della fase 1: in testa Roncola (0,63 bit), tasca, Scapolo, maiale, Fradicio e Sasso; in fondo coperchio, l'Asso di Bastoni e Albicocca. La quota di popolazione in esagoni sbiaditi è sotto il 2% per tutte le parole tranne Pop Corn (5%) e Libellula (4%).

## 7. Decisioni che ti chiedo

- **V1** BYM2 prevede meglio a livello di comune. Propongo di usarlo per la stima per comune (vista "per comune", tooltip, divisività) e di tenere il kernel per la mappa a esagoni, che è la vista principale. In alternativa si possono tenere entrambe le stime col kernel, più semplici e coerenti tra loro. Rifare BYM2 su tutte le parole richiede circa 25 minuti per livello.
- **V2** Seed: tengo 10 seed o salgo a 20 per tutte le parole?
- **V3** Va bene la soglia delle isoglosse nette (il 15% dei confini)? Con le sezioni ISTAT la ricalibro.
