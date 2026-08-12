# Catalogo suoni + kit personalizzati (pannello destro)

## Contesto

Su schermi larghi resta libero circa mezzo pannello a destra di `.grid-box` (griglia+mixer) e `.panel` (Connessione/Transport/Suoni & Set) — il layout `.wrap` è un flex `wrap` senza terzo elemento. I 348 clip dei 9 generi di fabbrica (`GENRES`, incorporati a build-time da `assemble.py`/`genres.json`) sono oggi raggiungibili solo tutti-o-niente tramite "▶ Carica genere" (`genre_ui.js`): non c'è modo di prendere un singolo suono da un genere e metterlo su un pad scelto, né di costruire un banco "su misura" pescando da generi diversi.

Obiettivo: un pannello che elenca tutto il catalogo (genere → categoria → singolo suono), trascinabile sui pad; un flusso per creare un banco vuoto e riempirlo trascinando; salvataggio del risultato come "kit" personale, selezionabile in seguito come un genere qualunque.

## Stato globale nuovo

```js
let dragSource = null;   // generalizza l'attuale dragSourcePad: {kind:'pad', r, c} | {kind:'catalog', genre, clip}
```
`dragSource` sostituisce `dragSourcePad` (stesso ruolo, stessa gestione "autopulizia al prossimo pointerdown" già esistente per il trascinamento pad-a-pad). `clip` nel caso `'catalog'` è l'oggetto grezzo `GENRES[genre].clips[i]` (contiene `r,c,name,mime,data,mode,trimStart,trimEnd` — `r,c` qui sono le coordinate *nel genere di origine*, ignorate per il piazzamento).

```js
let customKits = [];   // {id, name, ...stessa forma di un valore di GENRES} caricati da IndexedDB all'avvio
let previewSrc = null;   // {src, key} — l'anteprima da catalogo attualmente in corso (key = "genere|indice"), monofonica
```

## Helper "categoria di colonna" (nuovo, indipendente da `trackColorIdx`)

`trackColorIdx` esiste per i colori e viene ricalcolato solo in alcuni momenti (cambio banco, caricamento genere/set) — non è affidabile come fonte di verità per la *validità* di un piazzamento appena dopo "+ Nuovo kit" (griglia svuotata, colori non ancora ricalcolati). Nuovo helper puro, usato solo per le regole di validità:

```js
function columnCategoryOf(grid, c){
  for(let r=0;r<ROWS;r++){ if(grid[r][c]) return categoryOf(grid[r][c].name); }
  return null;   // colonna vuota: nessun tipo assegnato ancora
}
```

## Regole di piazzamento catalogo → pad

Un rilascio (Ctrl+trascinamento da catalogo) su `(r,c)` del banco attivo è valido se e solo se:
1. `clips[r][c]` è vuoto (mai sovrascrittura silenziosa di un suono già presente — a differenza del drop di un file da PC su `ondrop`, che resta invariato e continua a sovrascrivere sempre: è un'azione esplicita e mirata dell'utente, non un piazzamento "auto-organizzato");
2. `columnCategoryOf(clips, c)` è `null` (colonna ancora libera, se ne appropria) **oppure** coincide con `categoryOf(clip.name)` del suono trascinato.

Da queste due regole segue da sé il comportamento "scala fino a T8 poi blocca" descritto dall'utente: quando la colonna del tipo è piena, il prossimo trascinamento dello stesso tipo va su una colonna ancora libera (che se ne appropria); quando anche l'ultima colonna libera si esaurisce, ogni pad valido per quel tipo è o pieno o di un altro tipo → il rilascio fallisce ovunque.

Feedback sul fallimento: messaggio di stato discreto (stesso trattamento testuale dell'indicatore autosave), non un `alert()` bloccante — es. *"Nessun posto libero per «Drums»"*. Nessuna eccezione, nessun blocco dell'interazione.

Al completamento di un piazzamento valido: `pushUndo()`, decodifica audio (`decodeAudioData`, asincrona — vedi cache sotto), scrittura in `clips[r][c]`, `recomputeTrackColors()` (a differenza del trascinamento pad-a-pad e del caricamento file, qui *sì* che si ricalcola: è il cuore dell'"auto-organizzazione per tipo" richiesta, l'utente deve vederla riflessa live), `renderPad`, `updateLed`.

Bloccato se `perfMode==='drums'` (il catalogo alimenta solo i banchi, non il kit Drums — fuori scope, vedi sotto) — stesso trattamento inerte già usato da `setPadOneShot`.

## Cache di decodifica

```js
const catalogBufferCache = new Map();   // "genere|indice" -> Promise<AudioBuffer>
function decodeCatalogClip(genre, idx){
  const key=genre+'|'+idx;
  if(!catalogBufferCache.has(key)){
    const cl=GENRES[genre].clips[idx];
    catalogBufferCache.set(key, ac().decodeAudioData(b64ToAb(cl.data).slice(0)));
  }
  return catalogBufferCache.get(key);
}
```
Evita di ridecodificare lo stesso clip a ogni anteprima/trascinamento ripetuto (348 clip al massimo, decodifica solo on-demand — mai tutto il catalogo insieme, footprint di memoria limitato al realmente usato in sessione).

## Pannello "🗂️ Catalogo suoni" (nuovo, terzo box in `.wrap`)

Un `<details>` per genere (chiuso di default), dentro raggruppato per `categoryOf(name)`; ogni suono è una riga:
- **click** (senza Ctrl) → `previewCatalogClip(genre, idx)`: ferma un'eventuale anteprima precedente (stessa dissolvenza 6ms già usata da `oneShotVoice`/`drumVoice`), decodifica (cache), riproduce una volta a volume fisso, tracciata in `previewSrc`; ri-cliccare la *stessa* riga mentre suona la ferma invece di ripartire (comodo per un ascolto rapido senza dover aspettare la fine).
- **Ctrl+pointerdown** → `dragSource={kind:'catalog', genre, clip:GENRES[genre].clips[idx]}` (ferma anche un'eventuale anteprima in corso, stesso principio già applicato al trascinamento pad-a-pad: il gesto di trascinamento non deve avere effetti collaterali audio).
- Evidenziazione del pad valido sotto al cursore riusa `pointerenter`/`.dragover` già presenti sui pad, generalizzando la verifica di validità (oggi confronta `trackColorIdx`, diventa: pad vuoto + `columnCategoryOf` compatibile).

## "+ Nuovo kit" e libreria kit personalizzati

Pulsante dedicato accanto al menu Genere esistente (`genre_ui.js`):
- click → `prompt('Nome del kit:')`; se annullato/vuoto, nessuna azione; altrimenti `pushUndo()`, svuota `clips` del banco attivo (`for r,c: clips[r][c]=null`), `recomputeTrackColors()`, `renderAll()`, `refreshAllLeds()` — stesso trattamento "punto di partenza pulito" del caricamento di un genere, ma senza toccare bpm/mixer/FX (restano quelli correnti, l'utente li aggiusta come vuole mentre costruisce). Il nome scelto viene tenuto in una variabile di sessione (`draftKitName`) finché non si salva esplicitamente.
- Il `<select>` "🎚️ Genere" elenca, dopo i 9 di fabbrica, un separatore e poi `customKits` (per nome) — selezionarne uno e premere "▶ Carica genere" richiama la stessa `loadGenre()`-like logic (vedi sotto), a prescindere che la sorgente sia `GENRES[key]` o un elemento di `customKits`.
- **💾 Salva come kit**: sempre visibile vicino al menu Genere; serializza banco attivo + bpm/mixer/FX correnti nella stessa forma di un valore `GENRES[key]` (vedi Persistenza), usando `draftKitName` come nome proposto (modificabile), scrive su IndexedDB, aggiunge/aggiorna la voce in `customKits` e nel `<select>`.
- **🗑️ Elimina kit**: visibile solo quando il genere selezionato nel `<select>` è un kit personalizzato (non uno dei 9 di fabbrica, che restano intoccabili); cancella da IndexedDB e da `customKits`/`<select>`.
- **📂 Esporta kit** / **📥 Importa kit**: bottoni vicini, stessa meccanica di `saveBtn`/`openBtn` ma per un singolo kit invece dell'intera sessione — scaricano/leggono un file `.lpkit` (JSON, stesso schema di un valore `GENRES[key]`, `data` in base64 come già fa `.lpstudio`). Importare un `.lpkit` lo aggiunge a `customKits` (e IndexedDB) col nome contenuto nel file, senza toccare il banco attivo finché non viene esplicitamente caricato dal `<select>`.

## Persistenza

**IndexedDB** — nuovo database `lpstudioCustomKits`, store `kits`, chiave = `id` (stringa generata, es. timestamp+random). Valore:
```
{ id, name, bpm, bars, phraseBars, master, filter, revWet, revSize, dlyWet, dlyFb, dlyTime,
  tracks:[...8, stessa forma di GENRES[key].tracks],
  clips:[ {r,c,name,mime,mode,trimStart,trimEnd,sourceBpm,raw:ArrayBuffer}, ... ] }
```
(`raw` come `ArrayBuffer` diretto in IndexedDB — stesso trattamento di `AUTOSAVE_STORE`, niente base64 se non all'esportazione file). Caricati tutti in `customKits` all'avvio (dopo `checkAutosaveOnStartup()`, stesso punto di innesto già usato da `loadDrumKitPresetIfEmpty()`).

**File `.lpkit`** — stesso schema ma `clips[].data` in base64 (`abToB64`) al posto di `raw`, più `version:1` in testa; import/export riusano `abToB64`/`b64ToAb` già esistenti.

`customKits`/il banco "in costruzione" **non** entrano nell'Undo/Redo oltre a quanto già copre `clips` (le singole modifiche pad-per-pad sono già coperte da `pushUndo()` a ogni piazzamento/svuotamento, come per qualunque altra modifica ai pad). Il salvataggio esplicito su IndexedDB/file non è annullabile (come già `saveBtn`/l'autosave non lo sono).

## UI a schermo — riepilogo elementi nuovi

- Box `.catalog-box` (terzo elemento di `.wrap`, stesso stile visivo di `.panel`): titolo "🗂️ Catalogo suoni", lista `<details>` per genere.
- Messaggio di stato per rilascio rifiutato, vicino alla griglia (stesso trattamento dell'indicatore autosave).
- Barra genere (`genre_ui.js`) estesa con: bottone "+ Nuovo kit", bottone "💾 Salva come kit", bottone "🗑️ Elimina kit" (visibile solo su selezione di un kit personalizzato), bottone "📂 Esporta kit", bottone "📥 Importa kit" (+ relativo `<input type=file>` nascosto).

## Testing (TDD, harness esistente)

Nuovi test in `scratchpad/test_catalog_*.js` (harness da estendere: `prompt()` non è ancora stubbato, va aggiunto a `buildSandbox()` come già `confirm()`):
1. `columnCategoryOf`: colonna vuota → `null`; colonna con contenuto → categoria del primo clip trovato.
2. Piazzamento valido su colonna vuota; su colonna dello stesso tipo con posto libero; rifiutato su pad occupato; rifiutato su colonna di tipo diverso.
3. "Scala fino a T8 poi blocca": riempire 8 pad dello stesso tipo su una colonna, il 9° va sulla prossima colonna libera; ripetere finché tutte le colonne sono sature di tipi diversi → il piazzamento successivo fallisce ovunque e produce il messaggio di stato, senza toccare la griglia.
4. Ctrl+pointerdown su una riga catalogo imposta `dragSource` col `kind:'catalog'` corretto; un click semplice (senza Ctrl) avvia/ferma un'anteprima invece di avviare un trascinamento.
5. Anteprima monofonica: cliccare un secondo suono ferma il primo (stessa dissolvenza già testata per `oneShotVoice`/`drumVoice`); ricliccare lo stesso in corso lo ferma.
6. "+ Nuovo kit": svuota solo il banco attivo, annullabile, non tocca gli altri 3 banchi né bpm/mixer/FX correnti.
7. Salva come kit → round-trip IndexedDB (nome, bpm, tracks, clips) → appare in `customKits` e nel `<select>`; caricarlo popola la griglia come un genere di fabbrica.
8. Esporta/Importa `.lpkit`: round-trip file → stesso contenuto; import aggiunge senza toccare il banco attivo.
9. Elimina kit: rimuove da IndexedDB e dal `<select>`; non è disponibile quando il genere selezionato è uno dei 9 di fabbrica.

Rebuild (`assemble.py`) e verifica byte-identica sorgente/generato dopo ogni fix, come da prassi del progetto.

## Fuori scope (esplicitamente escluso per ora)

- Il catalogo non alimenta il kit Drums (`perfMode==='drums'`), solo i banchi normali — il kit Drums resta gestito dal proprio preset di fabbrica + editing manuale esistente.
- Rinominare un kit già salvato (si elimina e si risalva con nome diverso).
- Ricerca/filtro testuale nel pannello catalogo.
- Drag-and-drop nativo HTML5 (`draggable`): si riusa la stessa meccanica Ctrl+pointer già in produzione per il trascinamento pad-a-pad, per coerenza e perché già testata.
- Sincronizzazione dei kit personalizzati tra browser/dispositivi diversi (solo IndexedDB locale + export/import manuale via file).
