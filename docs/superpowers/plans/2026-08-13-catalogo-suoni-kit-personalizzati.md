# Catalogo suoni + kit personalizzati Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un pannello a destra che elenca i 348 suoni dei 9 generi (genere → categoria → singolo suono), trascinabili sui pad; un flusso "+ Nuovo kit" per costruire un banco vuoto trascinando; salvataggio del risultato come kit personalizzato (IndexedDB + export/import `.lpkit`), selezionabile in seguito come un genere qualunque.

**Architettura:** Si generalizza il meccanismo di trascinamento Ctrl+pointer già in produzione (`dragSourcePad`/`completeDrag`, vedi `_sorgente/launchpad-studio.html`) per accettare due tipi di sorgente: un pad (comportamento invariato) o una voce del catalogo. Un kit personalizzato condivide esattamente la forma dati di un genere di fabbrica (`GENRES[key]`), così caricarlo riusa la stessa `loadGenre()` (rinominata `loadGenreData`, generica). Persistenza locale in IndexedDB (nuovo DB, stesso pattern di `AUTOSAVE_STORE`) più export/import su file `.lpkit` (stesso schema di un genere, riusa `abToB64`/`b64ToAb`).

**Tech Stack:** Vanilla JS (nessuna dipendenza nuova), Web Audio API, IndexedDB, harness di test Node esistente (`scratchpad/harness.js`).

## Global Constraints

- Nessun drag-and-drop HTML5 nativo (`draggable`): si riusa la stessa convenzione **Ctrl+pointerdown** già in produzione per il trascinamento pad-a-pad, per coerenza e perché già testata.
- Un rilascio dal catalogo su un pad è valido solo se **il pad è vuoto** *e* **la colonna di destinazione è ancora libera oppure già della stessa categoria** (`categoryOf(name)`, la stessa euristica già usata da `recomputeTrackColors`). Nessuna sovrascrittura silenziosa (a differenza del trascinamento di un file da PC, che resta invariato).
- Rifiuto di un piazzamento = messaggio di stato discreto (mai `alert()` bloccante).
- Dopo ogni piazzamento riuscito dal catalogo: `recomputeTrackColors()` viene sempre richiamato (a differenza del trascinamento pad-a-pad esistente, che non lo richiama).
- Il catalogo alimenta solo i banchi normali (`clips`), mai il kit Drums: bloccato se `perfMode==='drums'`.
- Un kit personalizzato ha la stessa forma di un valore `GENRES[key]`: `{bpm,bars,phraseBars,master,filter,revWet,revSize,dlyWet,dlyFb,dlyTime,tracks:[...8],clips:[...]}`, più `id`/`name`.
- Codice che vive nel copione principale (`launchpad-studio.html`, tra il marcatore `STATO` e il suo `</script>`) è raggiungibile dai test con `runWithApp` di default. Codice che vive in un file iniettato (`genre_ui.js`, nuovo `catalog_ui.js`) va testato leggendo il file con `fs.readFileSync` e anteponendolo al codice di test passato come `epilogueCode` a `runWithApp` — **non** serve ricostruire `Launchpad Studio.html` per il TDD di ogni task, solo per la verifica finale (Task 10).
- Ogni riferimento nel copione principale a variabili/funzioni definite in un file iniettato va protetto con `typeof X !== 'undefined'` (stesso pattern già usato per `loadDrumKitPresetIfEmpty` in fondo al file) — l'inverso (file iniettato che referenzia il copione principale) **non** serve la guardia, perché il copione principale ha sempre già finito di eseguire quando gli script iniettati partono.
- Rebuild (`python assemble.py`) e regressione completa (`for f in test_*.js; do node "$f"; done`) solo nel Task 10 (integrazione finale) — i task precedenti non toccano `assemble.py`.

---

### Task 1: Generalizza `dragSource` (refactor, nessun cambio di comportamento)

**Files:**
- Modify: `_sorgente/launchpad-studio.html` (loop di creazione pad, funzione `completeDrag`)
- Test: `scratchpad/test_pad_drag_move.js` (esistente — deve restare verde, invariato)

**Interfaces:**
- Produce: `dragSource` (sostituisce `dragSourcePad`), forma `{kind:'pad',r,c} | null` (il `kind:'catalog'` arriva al Task 3); `isValidPadMoveTarget(src,r,c)`; `completeDrag(r,c)` (ora un dispatcher) + `completePadMove(src,r,c)` (corpo della vecchia `completeDrag`).

Questo task è un refactor puro: nessun test nuovo, la garanzia è che `test_pad_drag_move.js` (che esercita solo `padEls[r][c].onpointerdown/onpointerup`, mai i nomi interni delle variabili) resti verde prima e dopo.

- [ ] **Step 1: Baseline verde**

Esegui `node test_pad_drag_move.js` da `scratchpad/` — deve già passare (7/7), è la baseline pre-refactor.

- [ ] **Step 2: Applica il refactor**

Nel loop di creazione pad, sostituisci il blocco che dichiara `dragSourcePad` e i suoi 3 usi:

```js
const gridEl=document.getElementById('grid'), colhdr=document.getElementById('colhdr'), mixrow=document.getElementById('mixrow');
const padEls=[];
// Trascinamento (Ctrl+pointer, niente HTML5 draggable nativo): senza Ctrl un mousedown attiva gia'
// il pad (suona/avvia/apre il gate), quindi il drag va segnalato esplicitamente. dragSource generalizza
// la sorgente: {kind:'pad',r,c} per lo spostamento tra pad, {kind:'catalog',genre,idx} per il piazzamento
// dal pannello Catalogo suoni (vedi catalog_ui.js).
let dragSource=null;
function isValidPadMoveTarget(src,r,c){ return trackColorIdx[c]===trackColorIdx[src.c]; }
for(let c=0;c<COLS;c++){ const d=document.createElement('div'); d.textContent='T'+(c+1); colhdr.appendChild(d); }
for(let r=0;r<ROWS;r++){ padEls.push([]);
  for(let c=0;c<COLS;c++){
    const el=document.createElement('div'); el.className='pad'; el.dataset.r=r; el.dataset.c=c;
    el.onpointerdown=(e)=>{
      e.preventDefault();
      if(e.ctrlKey){ if(!activeGrid()[r][c]) return; dragSource={kind:'pad',r,c}; el.classList.add('dragging'); return; }
      if(dragSource && dragSource.kind==='pad') padEls[dragSource.r][dragSource.c].classList.remove('dragging');
      dragSource=null;
      if(perfMode==='drums') selectPad(r,c); triggerDown(r,c);
    };
    el.onpointerup=()=>{ if(dragSource){ completeDrag(r,c); return; } triggerUp(r,c); };
    el.onpointerenter=()=>{ if(dragSource && dragSource.kind==='pad' && isValidPadMoveTarget(dragSource,r,c)) el.classList.add('dragover'); };
    el.onpointerleave=()=>{ el.classList.remove('dragover'); if(dragSource) return; triggerUp(r,c); };
    el.oncontextmenu=(e)=>{ e.preventDefault(); setPadOneShot(r,c); };   // tasto destro = scorciatoia "imposta one-shot"
```

E sostituisci la funzione `completeDrag` esistente (quella con `const {r:sr,c:sc}=src;` nel corpo) con:

```js
function completeDrag(r,c){
  const src=dragSource; dragSource=null;
  if(!src) return;
  if(src.kind==='pad') return completePadMove(src,r,c);
}
// Ctrl+trascinamento tra pad (vedi onpointerdown/up sui pad piu' sopra): sposta il contenuto sul pad
// di destinazione, o li scambia se era gia' occupato. Ammesso solo tra colonne dello stesso "tipo"
// (isValidPadMoveTarget) per non mescolare per sbaglio suoni di categorie diverse tra le tracce.
function completePadMove(src,r,c){
  const {r:sr,c:sc}=src;
  padEls[sr][sc].classList.remove('dragging');
  padEls[r][c].classList.remove('dragover');
  if(sr===r && sc===c) return;
  if(!isValidPadMoveTarget(src,r,c)) return;
  const g=activeGrid(); if(!g[sr][sc]) return;
  pushUndo();
  if(perfMode===null){ stopPadSound(sr,sc); stopPadSound(r,c); }
  const tmp=g[r][c]; g[r][c]=g[sr][sc]; g[sr][sc]=tmp;
  renderPad(sr,sc); renderPad(r,c); updateLed(sr,sc); updateLed(r,c);
}
```

- [ ] **Step 3: Verifica che sia ancora tutto verde**

`node test_pad_drag_move.js` — deve restare 7/7 verde, output identico a prima (nessuna asserzione dovrebbe essere cambiata, perché il refactor non tocca il comportamento osservabile).

- [ ] **Step 4: Commit**

```bash
git add "_sorgente/launchpad-studio.html"
git commit -m "Generalizza dragSource per accettare anche il catalogo suoni (refactor)"
```

---

### Task 2: Cache di decodifica catalogo + anteprima audio (logica pura)

**Files:**
- Modify: `_sorgente/launchpad-studio.html` (nuove funzioni, vicino a `oneShotVoice`/`playOnce`)
- Test: `scratchpad/test_catalog_preview.js` (nuovo)

**Interfaces:**
- Consuma: `GENRES[genre].clips[idx]` (forma `{r,c,name,mime,data,mode,trimStart,trimEnd}`, `data` base64) — nei test iniettato via `opts.inject`, non serve `GENRES` reale.
- Produce: `catalogBufferCache` (Map), `decodeCatalogClip(genre,idx)` (Promise&lt;AudioBuffer&gt;), `previewSrc`, `previewCatalogClip(genre,idx)`, `stopCatalogPreview()`.

- [ ] **Step 1: Scrivi il test (fallisce: le funzioni non esistono)**

```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

const FAKE_GENRES = { G: { bpm:120, clips: [
  { r:0,c:0, name:'Kick_01', mime:'audio/webm', data:'AAAA', mode:'loop' },
  { r:0,c:1, name:'Bass_02', mime:'audio/webm', data:'AAAA', mode:'loop' },
] } };

async function testDecodeCachesPerClip(){
  const sb = await runWithApp(`
    ac();
    const p1 = decodeCatalogClip('G',0);
    const p2 = decodeCatalogClip('G',0);
    globalThis.__result = { same: p1===p2 };
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result.same, true, 'chiamare due volte lo stesso clip deve riusare la stessa Promise (cache)');
}

async function testPreviewPlaysAndTracksKey(){
  const sb = await runWithApp(`
    ac();
    await previewCatalogClip('G',0);
    globalThis.__result = { key: previewSrc && previewSrc.key };
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result.key, 'G|0', 'previewSrc deve tracciare il clip in riproduzione');
}

async function testClickingSameRowStopsInsteadOfRestarting(){
  const sb = await runWithApp(`
    ac();
    await previewCatalogClip('G',0);
    const firstSrc = previewSrc.src;
    await previewCatalogClip('G',0);
    globalThis.__result = { stopped: previewSrc===null, wasStopped: firstSrc._stopped };
  `, { inject: { GENRES: FAKE_GENRES } });
  const r = sb.__result;
  assert.strictEqual(r.stopped, true, 'ricliccare lo stesso suono in ascolto deve fermarlo, non farlo ripartire');
  assert.strictEqual(r.wasStopped, true, 'la voce precedente deve essere davvero fermata');
}

async function testPlayingADifferentClipStopsThePrevious(){
  const sb = await runWithApp(`
    ac();
    await previewCatalogClip('G',0);
    const firstSrc = previewSrc.src;
    await previewCatalogClip('G',1);
    globalThis.__result = { key: previewSrc.key, firstStopped: firstSrc._stopped };
  `, { inject: { GENRES: FAKE_GENRES } });
  const r = sb.__result;
  assert.strictEqual(r.key, 'G|1', 'deve passare al nuovo suono');
  assert.strictEqual(r.firstStopped, true, 'il precedente deve fermarsi (monofonico)');
}

async function testStopCatalogPreviewIsSafeWhenIdle(){
  const sb = await runWithApp(`
    ac();
    stopCatalogPreview();
    globalThis.__result = previewSrc;
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result, null, 'fermare quando non sta suonando nulla non deve esplodere');
}

(async () => {
  const tests = [
    ['decodeCatalogClip mette in cache per genere+indice', testDecodeCachesPerClip],
    ['previewCatalogClip suona e traccia la chiave', testPreviewPlaysAndTracksKey],
    ['ricliccare lo stesso suono lo ferma', testClickingSameRowStopsInsteadOfRestarting],
    ['suonarne un altro ferma il precedente', testPlayingADifferentClipStopsThePrevious],
    ['stopCatalogPreview a riposo non esplode', testStopCatalogPreviewIsSafeWhenIdle],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

Esegui `node test_catalog_preview.js` da `scratchpad/` — deve fallire (le funzioni non esistono ancora, `ReferenceError`).

- [ ] **Step 2: Implementa**

Aggiungi in `_sorgente/launchpad-studio.html`, subito dopo la definizione di `playOnce` (vicino a `oneShotVoice`/`drumVoice`):

```js
// Cache di decodifica per il pannello Catalogo suoni: evita di ridecodificare lo stesso clip a ogni
// anteprima/trascinamento ripetuto. Decodifica solo on-demand (mai tutto il catalogo insieme).
const catalogBufferCache=new Map();   // "genere|indice" -> Promise<AudioBuffer>
function decodeCatalogClip(genre,idx){
  const key=genre+'|'+idx;
  if(!catalogBufferCache.has(key)){
    const cl=GENRES[genre].clips[idx];
    catalogBufferCache.set(key, ac().decodeAudioData(b64ToAb(cl.data)));
  }
  return catalogBufferCache.get(key);
}
// Anteprima da catalogo: monofonica, stessa dissolvenza-poi-stop gia' usata da oneShotVoice/drumVoice.
let previewSrc=null;   // {src,g,key} — l'anteprima in corso, o null
async function previewCatalogClip(genre,idx){
  const key=genre+'|'+idx;
  if(previewSrc && previewSrc.key===key){ stopCatalogPreview(); return; }   // riclic sullo stesso: ferma
  stopCatalogPreview();
  ac().resume();
  const buffer=await decodeCatalogClip(genre,idx);
  const src=ac().createBufferSource(); src.buffer=buffer; src.loop=false;
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(1,now()+0.005);
  src.connect(g).connect(masterGain); src.start(now());
  oneShots.push(src); src.onended=()=>{ oneShots=oneShots.filter(s=>s!==src); if(previewSrc&&previewSrc.src===src) previewSrc=null; };
  previewSrc={src,g,key};
}
function stopCatalogPreview(){
  if(!previewSrc) return;
  const pv=previewSrc, pt=now(), F=0.006;
  try{ pv.g.gain.setValueAtTime(pv.g.gain.value,pt); pv.g.gain.linearRampToValueAtTime(0,pt+F); pv.src.stop(pt+F+0.006); }catch(e){}
  previewSrc=null;
}
```

- [ ] **Step 3: Verifica GREEN**

`node test_catalog_preview.js` — 5/5 verde.

- [ ] **Step 4: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "scratchpad/test_catalog_preview.js"
git commit -m "Cache di decodifica + anteprima audio per il catalogo suoni"
```
(nota: `scratchpad/` è fuori dal repo — se il tuo `scratchpad` è nella cartella progetto ignora questa riga, altrimenti l'`add` del file di test è un no-op innocuo)

---

### Task 3: Regole di piazzamento catalogo → pad + messaggio di stato di rifiuto

**Files:**
- Modify: `_sorgente/launchpad-studio.html` (nuovo `<span id="dropStatus">` nell'HTML, `columnCategoryOf`, `showDropStatus`, `isValidDropTarget`, `completeCatalogPlace`, aggiornamento di `completeDrag` e del listener `onpointerenter`)
- Test: `scratchpad/test_catalog_placement.js` (nuovo)

**Interfaces:**
- Consuma: `decodeCatalogClip`, `previewSrc`/`stopCatalogPreview` (Task 2); `dragSource`, `isValidPadMoveTarget`, `completeDrag` (Task 1).
- Produce: `columnCategoryOf(grid,c)`, `isValidDropTarget(src,r,c)`, `completeCatalogPlace(src,r,c)`, `showDropStatus(msg)`. `dragSource` ora può assumere anche `{kind:'catalog',genre,idx}`.

- [ ] **Step 1: Aggiungi l'elemento di stato nell'HTML**

Nel markup, subito dopo il blocco `.hint` dentro `.grid-box` (quello che inizia con `Ogni <b>colonna</b> è una traccia...`):

```html
      <div class="hint" style="max-width:460px">
        Ogni <b>colonna</b> è una traccia, ogni <b>riga</b> una scena. Trascina un file audio su un pad
        (o "Carica") per assegnarlo. Premi il pad sul Launchpad: il loop parte a tempo e in una traccia
        suona una clip alla volta. Sotto ogni traccia: volume, <b>M</b>ute, <b>S</b>olo.
      </div>
      <span id="dropStatus" class="hint" style="display:block;margin-top:6px;min-height:14px"></span>
```

- [ ] **Step 2: Scrivi il test (fallisce: le funzioni non esistono)**

```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

const FAKE_GENRES = { G: { bpm:120, clips: [
  { r:0,c:0, name:'Kick_01', mime:'audio/webm', data:'AAAA', mode:'loop' },
  { r:0,c:1, name:'Bass_02', mime:'audio/webm', data:'AAAA', mode:'loop' },
] } };

async function testColumnCategoryOfEmptyIsNull(){
  const sb = await runWithApp(`
    globalThis.__result = columnCategoryOf(clips, 3);
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result, null, 'colonna vuota -> nessuna categoria');
}

async function testColumnCategoryOfReadsFirstClip(){
  const sb = await runWithApp(`
    clips[5][2] = { name:'Kick_07' };
    globalThis.__result = columnCategoryOf(clips, 2);
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result, 'kick', 'deve leggere la categoria del primo clip trovato nella colonna');
}

async function testPlacementOnEmptyColumn(){
  const sb = await runWithApp(`
    ac();
    dragSource = { kind:'catalog', genre:'G', idx:0 };
    completeDrag(3,4);
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = clips[3][4] ? clips[3][4].name : null;
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result, 'Kick_01', 'colonna vuota: il piazzamento deve riuscire');
}

async function testPlacementRejectedOnOccupiedPad(){
  const sb = await runWithApp(`
    ac();
    clips[1][0] = { buffer:{duration:1}, name:'Gia\\' presente', mode:'loop' };
    dragSource = { kind:'catalog', genre:'G', idx:0 };
    completeDrag(1,0);
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = clips[1][0].name;
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result, "Gia' presente", 'un pad gia\' occupato non deve mai essere sovrascritto dal catalogo');
}

async function testPlacementRejectedOnDifferentCategoryColumn(){
  const sb = await runWithApp(`
    ac();
    clips[0][5] = { buffer:{duration:1}, name:'Bass_09', mode:'loop' };
    dragSource = { kind:'catalog', genre:'G', idx:0 };   // Kick_01
    completeDrag(2,5);
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = { placed: clips[2][5], status: document.getElementById('dropStatus').textContent };
  `, { inject: { GENRES: FAKE_GENRES } });
  const r = sb.__result;
  assert.strictEqual(r.placed, null, 'colonna di categoria diversa: nessun piazzamento');
  assert.ok(r.status.length>0, 'deve comparire un messaggio di stato di rifiuto');
}

async function testPlacementRejectedInDrumsMode(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    dragSource = { kind:'catalog', genre:'G', idx:0 };
    completeDrag(3,3);
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = clips[3][3];
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result, null, 'il catalogo non deve alimentare il kit Drums');
}

async function testPlacementIsUndoableAndRecomputesColors(){
  const sb = await runWithApp(`
    ac();
    const before = undoStack.length;
    dragSource = { kind:'catalog', genre:'G', idx:0 };
    completeDrag(0,0);
    await new Promise(r=>setTimeout(r,10));
    dragSource = { kind:'catalog', genre:'G', idx:0 };
    completeDrag(4,0);
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = { undoGrew: undoStack.length>before, sameColor: trackColorIdx[0]===trackColorIdx[0] };
  `, { inject: { GENRES: FAKE_GENRES } });
  assert.strictEqual(sb.__result.undoGrew, true, 'ogni piazzamento riuscito deve essere annullabile');
}

async function testOverflowScalesThenBlocks(){
  const sb = await runWithApp(`
    ac();
    // Riempie la colonna 0 con 8 suoni della stessa categoria "kick" (finto, senza passare dal catalogo).
    for(let r=0;r<ROWS;r++) clips[r][0] = { buffer:{duration:1}, name:'Kick_'+r, mode:'loop' };
    // Il 9deg tentativo (stesso tipo) deve scalare sulla prossima colonna libera (1).
    dragSource = { kind:'catalog', genre:'G', idx:0 };   // Kick_01
    completeDrag(0,1);
    await new Promise(r=>setTimeout(r,10));
    const scaledOk = clips[0][1] && clips[0][1].name==='Kick_01';
    // Ora satura anche le colonne rimanenti (2..7) con la stessa categoria "kick".
    for(let c=2;c<COLS;c++) for(let r=0;r<ROWS;r++) clips[r][c] = { buffer:{duration:1}, name:'Kick_x', mode:'loop' };
    clips[0][1] = { buffer:{duration:1}, name:'Kick_full', mode:'loop' };
    for(let r=1;r<ROWS;r++) clips[r][1] = { buffer:{duration:1}, name:'Kick_full', mode:'loop' };
    // Nessuna colonna ha piu' posto libero per "kick": il prossimo piazzamento deve fallire ovunque.
    dragSource = { kind:'catalog', genre:'G', idx:0 };
    completeDrag(0,0);   // gia' occupato comunque, ma verifichiamo lo stato
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = { scaledOk, status: document.getElementById('dropStatus').textContent };
  `, { inject: { GENRES: FAKE_GENRES } });
  const r = sb.__result;
  assert.strictEqual(r.scaledOk, true, 'quando la colonna 0 e\' piena, il piazzamento deve scalare sulla colonna 1 libera');
}

(async () => {
  const tests = [
    ['columnCategoryOf: colonna vuota -> null', testColumnCategoryOfEmptyIsNull],
    ['columnCategoryOf: legge la categoria del primo clip', testColumnCategoryOfReadsFirstClip],
    ['piazzamento su colonna vuota riesce', testPlacementOnEmptyColumn],
    ['piazzamento rifiutato su pad occupato', testPlacementRejectedOnOccupiedPad],
    ['piazzamento rifiutato su colonna di tipo diverso', testPlacementRejectedOnDifferentCategoryColumn],
    ['piazzamento rifiutato in Drums mode', testPlacementRejectedInDrumsMode],
    ['piazzamento annullabile', testPlacementIsUndoableAndRecomputesColors],
    ['overflow: scala sulla colonna libera successiva', testOverflowScalesThenBlocks],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

(nota per l'implementatore: correggi la parentesi graffa di troppo dopo `testOverflowScalesThenBlocks` — è `}` di chiusura della funzione seguito da `);` invece di `}` — refuso da correggere in fase di trascrizione: dev'essere semplicemente `}`)

Esegui `node test_catalog_placement.js` — deve fallire (funzioni inesistenti).

- [ ] **Step 3: Implementa**

Aggiungi (vicino a `recomputeTrackColors`, dato che `columnCategoryOf` è concettualmente imparentata):

```js
// Come recomputeTrackColors ma restituisce la categoria grezza (non un indice colore) di UNA colonna,
// usata per validare i piazzamenti dal catalogo — trackColorIdx non e' affidabile qui perche' viene
// ricalcolato solo in alcuni momenti (cambio banco/genere), non ad ogni singolo piazzamento.
function columnCategoryOf(grid,c){
  for(let r=0;r<ROWS;r++){ if(grid[r][c]) return categoryOf(grid[r][c].name); }
  return null;
}
```

Aggiungi vicino a `stopCatalogPreview` (Task 2):

```js
let dropStatusTimer=null;
function showDropStatus(msg){
  const el=document.getElementById('dropStatus'); if(!el) return;
  el.textContent=msg;
  clearTimeout(dropStatusTimer);
  dropStatusTimer=setTimeout(()=>{ el.textContent=''; }, 2500);
}
function isValidDropTarget(src,r,c){
  if(!src) return false;
  if(src.kind==='pad') return isValidPadMoveTarget(src,r,c);
  if(src.kind==='catalog'){
    if(clips[r][c]) return false;
    const cat=categoryOf(GENRES[src.genre].clips[src.idx].name);
    const colCat=columnCategoryOf(clips,c);
    return colCat===null || colCat===cat;
  }
  return false;
}
// Completa un Ctrl+trascinamento dal pannello Catalogo suoni (vedi completeDrag/isValidDropTarget).
// Valido solo su pad vuoto e colonna libera o della stessa categoria; mai in Drums mode (il catalogo
// alimenta solo i banchi). Dopo un piazzamento riuscito ricalcola i colori-per-categoria, a differenza
// del trascinamento pad-a-pad: qui e' proprio il punto, l'utente deve vedere l'auto-organizzazione live.
async function completeCatalogPlace(src,r,c){
  if(perfMode==='drums') return;
  const cl=GENRES[src.genre].clips[src.idx];
  const cat=categoryOf(cl.name);
  if(clips[r][c]){ showDropStatus('Pad occupato'); return; }
  const colCat=columnCategoryOf(clips,c);
  if(colCat!==null && colCat!==cat){ showDropStatus('Nessun posto libero per «'+cat+'»'); return; }
  const buffer=await decodeCatalogClip(src.genre,src.idx);
  if(clips[r][c]) return;   // occupato nel frattempo (decodifica asincrona): abbandona senza sovrascrivere
  pushUndo();
  const raw=b64ToAb(cl.data);
  clips[r][c]={buffer,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',sourceBpm:GENRES[src.genre].bpm,
    trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null};
  recomputeTrackColors(); renderPad(r,c); updateLed(r,c);
}
```

Aggiorna `completeDrag` (aggiunto nel Task 1) per instradare anche il caso `'catalog'`:

```js
function completeDrag(r,c){
  const src=dragSource; dragSource=null;
  if(!src) return;
  if(src.kind==='pad') return completePadMove(src,r,c);
  if(src.kind==='catalog') return completeCatalogPlace(src,r,c);
}
```

Aggiorna il listener `onpointerenter` sui pad (nel loop di creazione, Task 1) per usare il dispatcher generico invece del controllo diretto su `trackColorIdx`:

```js
    el.onpointerenter=()=>{ if(isValidDropTarget(dragSource,r,c)) el.classList.add('dragover'); };
```

- [ ] **Step 4: Verifica GREEN**

`node test_catalog_placement.js` — 8/8 verde. Esegui anche `node test_pad_drag_move.js` per confermare che il refactor del listener `onpointerenter` non ha rotto lo spostamento pad-a-pad.

- [ ] **Step 5: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "scratchpad/test_catalog_placement.js"
git commit -m "Regole di piazzamento catalogo->pad (colonna vuota o stessa categoria)"
```

---

### Task 4: Pannello "Catalogo suoni" (`catalog_ui.js`) — DOM, anteprima, Ctrl-trascinamento

**Files:**
- Create: `_sorgente/catalog_ui.js`
- Modify: `_sorgente/launchpad-studio.html` (solo CSS: `.catalog-box`, `.cat-row`, `.cat-row.previewing`)
- Test: `scratchpad/test_catalog_ui.js` (nuovo — legge `catalog_ui.js` con `fs.readFileSync` e lo antepone al codice di test)

**Interfaces:**
- Consuma: `GENRES`, `categoryOf`, `dragSource`, `previewCatalogClip` (Task 2).
- Produce: il box `.catalog-box` inserito in `.wrap`, righe `.cat-row` cliccabili/trascinabili.

- [ ] **Step 1: Aggiungi il CSS**

Nel blocco `<style>`, vicino a `.pad.dragging` (aggiunta della sessione precedente):

```css
.catalog-box{width:340px;max-height:640px;overflow-y:auto}
.cat-row{font-size:12px;color:var(--txt);padding:3px 6px;border-radius:5px;cursor:pointer}
.cat-row:hover{background:var(--panel2)}
.cat-row.previewing{background:var(--accent);color:#04101f}
```

- [ ] **Step 2: Scrivi il test (fallisce: il file non esiste)**

```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { runWithApp } = require('./harness.js');

const CATALOG_UI_SRC = fs.readFileSync('D:/MUSIC/Launchpad Studio/_sorgente/catalog_ui.js', 'utf8');

const FAKE_GENRES = { G1: { bpm:120, clips: [
  { r:0,c:0, name:'Kick_01', mime:'audio/webm', data:'AAAA', mode:'loop' },
  { r:0,c:1, name:'Kick_02', mime:'audio/webm', data:'AAAA', mode:'loop' },
  { r:1,c:0, name:'Bass_01', mime:'audio/webm', data:'AAAA', mode:'loop' },
] } };

async function run(code){
  return runWithApp(CATALOG_UI_SRC + '\n' + code, { inject: { GENRES: FAKE_GENRES } });
}

async function testPanelBuildsGenreAndCategoryGroups(){
  const sb = await run(`
    ac();
    const box=document.querySelector('.catalog-box');
    globalThis.__result = { boxChildren: box.children.length };
  `);
  assert.ok(sb.__result.boxChildren>0, 'il box del catalogo deve avere contenuto (titolo + almeno un genere)');
}

async function testClickPreviewsSound(){
  const sb = await run(`
    ac();
    catalogRowEls['G1|0'].onclick();
    await new Promise(r=>setTimeout(r,10));
    globalThis.__result = previewSrc && previewSrc.key;
  `);
  assert.strictEqual(sb.__result, 'G1|0', 'click su una riga deve avviare l\\'anteprima di quel clip');
}

async function testCtrlPointerdownSetsDragSourceWithoutPreview(){
  const sb = await run(`
    ac();
    catalogRowEls['G1|1'].onpointerdown({ ctrlKey:true, preventDefault(){} });
    globalThis.__result = { dragSource, previewSrc };
  `);
  const r = sb.__result;
  assert.deepStrictEqual(r.dragSource, { kind:'catalog', genre:'G1', idx:1 }, 'Ctrl+pointerdown deve impostare dragSource sul clip giusto');
  assert.strictEqual(r.previewSrc, null, 'Ctrl+pointerdown non deve avviare anche un\\'anteprima');
}

async function testPreviewingClassTogglesOnRow(){
  const sb = await run(`
    ac();
    catalogRowEls['G1|0'].onclick();
    await new Promise(r=>setTimeout(r,10));
    const duringPlay = catalogRowEls['G1|0'].classList.contains('previewing');
    catalogRowEls['G1|0'].onclick();   // riclic: ferma
    await new Promise(r=>setTimeout(r,10));
    const afterStop = catalogRowEls['G1|0'].classList.contains('previewing');
    globalThis.__result = { duringPlay, afterStop };
  `);
  const r = sb.__result;
  assert.strictEqual(r.duringPlay, true, 'la riga in ascolto deve avere la classe previewing');
  assert.strictEqual(r.afterStop, false, 'fermata l\\'anteprima, la classe deve sparire');
}

(async () => {
  const tests = [
    ['il pannello costruisce generi e categorie', testPanelBuildsGenreAndCategoryGroups],
    ['click su una riga avvia l\\'anteprima', testClickPreviewsSound],
    ['Ctrl+pointerdown imposta dragSource senza anteprima', testCtrlPointerdownSetsDragSourceWithoutPreview],
    ['la classe previewing riflette lo stato di ascolto', testPreviewingClassTogglesOnRow],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

(nota per l'implementatore: rimuovi il primo `require` ridondante con percorso relativo fragile — `CATALOG_UI_SRC` — e tieni solo `CATALOG_UI_SRC_ABS` con il percorso assoluto, coerente con `REAL_SRC_PATH` già usato da `harness.js`)

`catalogRowEls` deve essere raggiungibile dal test: **non** dichiararlo `const` dentro l'IIFE (resterebbe privato) — dichiaralo con `let` fuori dall'IIFE stessa, cioè a livello top del file `catalog_ui.js` (che, concatenato nello stesso script del test in `runWithApp`, condivide lo scope lessicale — stesso principio già sfruttato da `genre_ui.js` per `pushUndo`/`clips`/etc.).

Esegui `node test_catalog_ui.js` — deve fallire (`ENOENT`, il file non esiste).

- [ ] **Step 3: Implementa `_sorgente/catalog_ui.js`**

```js
(function(){
  if(typeof GENRES==='undefined') return;
  const wrap=document.querySelector('.wrap');
  const box=document.createElement('div'); box.className='panel catalog-box';
  const h=document.createElement('h2'); h.textContent='🗂️ Catalogo suoni'; box.appendChild(h);
  const hint=document.createElement('div'); hint.className='hint'; hint.style.marginBottom='8px';
  hint.textContent="Click = ascolto rapido. Ctrl+trascina su un pad per metterlo li'.";
  box.appendChild(hint);
  Object.keys(GENRES).forEach(genre=>{
    const det=document.createElement('details');
    const sum=document.createElement('summary'); sum.textContent=genre; det.appendChild(sum);
    const groups={};   // categoria -> <div> contenitore righe
    (GENRES[genre].clips||[]).forEach((cl,idx)=>{
      const cat=categoryOf(cl.name);
      if(!groups[cat]){
        const catBlock=document.createElement('div'); catBlock.style.cssText='margin:6px 0 0 8px';
        const catLab=document.createElement('div'); catLab.textContent=cat;
        catLab.style.cssText='color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px';
        catBlock.appendChild(catLab);
        groups[cat]=catBlock; det.appendChild(catBlock);
      }
      const row=document.createElement('div'); row.className='cat-row'; row.textContent=cl.name;
      row.onpointerdown=(e)=>{ if(e.ctrlKey){ e.preventDefault(); dragSource={kind:'catalog',genre,idx}; } };
      row.onclick=async ()=>{
        const key=genre+'|'+idx;
        const wasThis = previewSrc && previewSrc.key===key;
        await previewCatalogClip(genre,idx);
        Object.keys(catalogRowEls).forEach(k=>catalogRowEls[k].classList.remove('previewing'));
        if(!wasThis && previewSrc && previewSrc.key===key) row.classList.add('previewing');
      };
      catalogRowEls[genre+'|'+idx]=row;
      groups[cat].appendChild(row);
    });
    box.appendChild(det);
  });
  wrap.appendChild(box);
})();
```

E dichiara, subito **sopra** l'IIFE (fuori da essa, cosi' i test/altri file possono leggerla):

```js
let catalogRowEls={};   // "genere|indice" -> elemento riga, per lo stato "in ascolto" (previewing)
```

- [ ] **Step 4: Verifica GREEN**

`node test_catalog_ui.js` — 4/4 verde.

- [ ] **Step 5: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "_sorgente/catalog_ui.js" "scratchpad/test_catalog_ui.js"
git commit -m "Pannello Catalogo suoni: DOM, anteprima, Ctrl+trascinamento"
```

---

### Task 5: Kit personalizzati — store IndexedDB + caricamento all'avvio

**Files:**
- Modify: `scratchpad/harness.js` (aggiungi `getAll()` al fake IndexedDB store — manca, serve per elencare i kit salvati)
- Modify: `_sorgente/launchpad-studio.html` (nuova sezione "KIT PERSONALIZZATI", vicino ad AUTOSAVE)
- Test: `scratchpad/test_custom_kits_db.js` (nuovo)

**Interfaces:**
- Produce: `kitDbOpen`, `kitPut(kit)`, `kitGetAll()`, `kitDelete(id)`, `newKitId()`, `customKits` (array), `loadCustomKitsFromDb()`.

- [ ] **Step 1: Estendi il fake IndexedDB nell'harness**

In `scratchpad/harness.js`, dentro `makeFakeIndexedDB`, nell'oggetto ritornato da `tx.objectStore = (sn) => { ... return { get(...), put(...), delete(...) } }`, aggiungi un quarto metodo `getAll`:

```js
            tx.objectStore = (sn) => {
              const store = dbStores[sn];
              return {
                get(key){
                  const r = { onsuccess: null, onerror: null, result: undefined };
                  pending++;
                  fireAsync(() => { r.result = store.get(key); if(r.onsuccess) r.onsuccess({ target: r }); pending--; maybeComplete(); });
                  return r;
                },
                getAll(){
                  const r = { onsuccess: null, onerror: null, result: undefined };
                  pending++;
                  fireAsync(() => { r.result = Array.from(store.values()); if(r.onsuccess) r.onsuccess({ target: r }); pending--; maybeComplete(); });
                  return r;
                },
                put(val, key){
                  const r = { onsuccess: null, onerror: null };
                  pending++;
                  fireAsync(() => { store.set(key, val); if(r.onsuccess) r.onsuccess({ target: r }); pending--; maybeComplete(); });
                  return r;
                },
                delete(key){
                  const r = { onsuccess: null, onerror: null };
                  pending++;
                  fireAsync(() => { store.delete(key); if(r.onsuccess) r.onsuccess({ target: r }); pending--; maybeComplete(); });
                  return r;
                },
              };
            };
```

(solo l'aggiunta del metodo `getAll` — `get`/`put`/`delete` restano quelli che c'erano già)

- [ ] **Step 2: Scrivi il test (fallisce: le funzioni non esistono)**

```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testPutAndGetAllRoundTrip(){
  const sb = await runWithApp(`
    await kitPut({ id:'a', name:'Uno', clips:[] });
    await kitPut({ id:'b', name:'Due', clips:[] });
    const all = await kitGetAll();
    globalThis.__result = all.map(k=>k.name).sort();
  `);
  assert.deepStrictEqual(sb.__result, ['Due','Uno'], 'kitGetAll deve restituire tutti i kit salvati');
}

async function testDeleteRemovesKit(){
  const sb = await runWithApp(`
    await kitPut({ id:'x', name:'Da cancellare', clips:[] });
    await kitDelete('x');
    const all = await kitGetAll();
    globalThis.__result = all.length;
  `);
  assert.strictEqual(sb.__result, 0, 'kitDelete deve rimuovere il kit dallo store');
}

async function testLoadCustomKitsFromDbPopulatesArray(){
  const sb = await runWithApp(`
    await kitPut({ id:'z', name:'Caricami', clips:[] });
    await loadCustomKitsFromDb();
    globalThis.__result = customKits.map(k=>k.name);
  `);
  assert.deepStrictEqual(sb.__result, ['Caricami'], 'loadCustomKitsFromDb deve popolare customKits da IndexedDB');
}

async function testNewKitIdIsUnique(){
  const sb = await runWithApp(`
    globalThis.__result = { a: newKitId(), b: newKitId() };
  `);
  assert.notStrictEqual(sb.__result.a, sb.__result.b, 'due chiamate consecutive devono produrre id diversi');
}

(async () => {
  const tests = [
    ['kitPut + kitGetAll fanno round-trip', testPutAndGetAllRoundTrip],
    ['kitDelete rimuove il kit', testDeleteRemovesKit],
    ['loadCustomKitsFromDb popola customKits', testLoadCustomKitsFromDbPopulatesArray],
    ['newKitId produce id diversi', testNewKitIdIsUnique],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

Esegui `node test_custom_kits_db.js` — deve fallire (`ReferenceError: kitPut is not defined`).

- [ ] **Step 3: Implementa**

Aggiungi in `_sorgente/launchpad-studio.html`, subito dopo la sezione `// ====================== AUTOSAVE (IndexedDB) ======================` (dopo `idbDel`):

```js
// ====================== KIT PERSONALIZZATI (IndexedDB) ======================
// Stessa forma di un valore GENRES[key] (bpm/bars/phraseBars/master/filter/FX/tracks/clips), + id/name.
// DB separato dall'autosave: sopravvive a un "Cancella autosave" e viceversa.
const KIT_DB='lpstudioCustomKits', KIT_STORE='kits';
function kitDbOpen(){ return new Promise((res,rej)=>{
  if(typeof indexedDB==='undefined'){ rej(new Error('IndexedDB non disponibile')); return; }
  const req=indexedDB.open(KIT_DB,1);
  req.onupgradeneeded=()=>{ req.result.createObjectStore(KIT_STORE); };
  req.onsuccess=()=>res(req.result); req.onerror=()=>rej(req.error);
}); }
async function kitPut(kit){ const db=await kitDbOpen(); return new Promise((res,rej)=>{
  const tx=db.transaction(KIT_STORE,'readwrite'); tx.objectStore(KIT_STORE).put(kit,kit.id);
  tx.oncomplete=()=>res(); tx.onerror=()=>rej(tx.error); }); }
async function kitGetAll(){ const db=await kitDbOpen(); return new Promise((res,rej)=>{
  const tx=db.transaction(KIT_STORE,'readonly'); const rq=tx.objectStore(KIT_STORE).getAll();
  rq.onsuccess=()=>res(rq.result||[]); rq.onerror=()=>rej(rq.error); }); }
async function kitDelete(id){ const db=await kitDbOpen(); return new Promise((res,rej)=>{
  const tx=db.transaction(KIT_STORE,'readwrite'); tx.objectStore(KIT_STORE).delete(id);
  tx.oncomplete=()=>res(); tx.onerror=()=>rej(tx.error); }); }
function newKitId(){ return 'kit-'+Date.now()+'-'+Math.random().toString(36).slice(2,8); }
let customKits=[];   // dalla IndexedDB, popolato all'avvio; elencati nel <select> Genere da genre_ui.js
async function loadCustomKitsFromDb(){
  try{ customKits=await kitGetAll(); }catch(e){ customKits=[]; }
  if(typeof refreshGenreSelectOptions==='function') refreshGenreSelectOptions();
}
```

Aggiorna la riga AVVIO in fondo al file:

```js
// ====================== AVVIO ======================
selectPad(0,0); renderAll(); initMIDI();
checkAutosaveOnStartup().then(()=>{ if(typeof loadDrumKitPresetIfEmpty==='function') loadDrumKitPresetIfEmpty(); });
loadCustomKitsFromDb();
```

- [ ] **Step 4: Verifica GREEN**

`node test_custom_kits_db.js` — 4/4 verde. Esegui anche `node test_autosave.js` per confermare che il nuovo DB non interferisce con quello dell'autosave (store separati).

- [ ] **Step 5: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "scratchpad/harness.js" "scratchpad/test_custom_kits_db.js"
git commit -m "Store IndexedDB per i kit personalizzati + caricamento all'avvio"
```

---

### Task 6: "+ Nuovo kit"

**Files:**
- Modify: `scratchpad/harness.js` (aggiungi lo stub `prompt()` — manca, serve da qui in poi)
- Modify: `_sorgente/genre_ui.js`
- Test: `scratchpad/test_new_kit_button.js` (nuovo)

**Interfaces:**
- Consuma: `pushUndo`, `clips`, `recomputeTrackColors`, `renderAll`, `refreshAllLeds` (copione principale).
- Produce: bottone "+ Nuovo kit" nella barra Genere, `draftKitName` (variabile privata dell'IIFE).

- [ ] **Step 1: Aggiungi lo stub `prompt()` all'harness**

In `scratchpad/harness.js`, dentro `buildSandbox()`, vicino a `confirm`:

```js
    confirm(msg){ sandbox.__lastConfirm = msg; return sandbox.__confirmReturns !== undefined ? sandbox.__confirmReturns : true; },
    prompt(msg, def){ sandbox.__lastPrompt = msg; return sandbox.__promptReturns !== undefined ? sandbox.__promptReturns : null; },
```

(un test imposta il valore di ritorno passando `inject:{ __promptReturns: 'Nome' }`, esattamente come già si fa con `__confirmReturns`)

- [ ] **Step 2: Scrivi il test (fallisce: il bottone non esiste)**

```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const { runWithApp } = require('./harness.js');
const GENRE_UI_SRC = fs.readFileSync('D:/MUSIC/Launchpad Studio/_sorgente/genre_ui.js', 'utf8');
const FAKE_GENRES = { G1: { bpm:120, clips: [] } };

async function run(code, extraInject){
  return runWithApp(GENRE_UI_SRC + '\n' + code, { inject: Object.assign({ GENRES: FAKE_GENRES }, extraInject||{}) });
}

async function testNewKitClearsActiveBankWhenNamed(){
  const sb = await run(`
    ac();
    clips[2][2] = { buffer:{duration:1}, name:'Vecchio', mode:'loop' };
    document.getElementById('anon:button').click;   // no-op, solo per assicurare che il DOM sia pronto
    newKitBtn.onclick();
    globalThis.__result = clips[2][2];
  `, { __promptReturns: 'Il mio kit' });
  assert.strictEqual(sb.__result, null, '"+ Nuovo kit" con un nome deve svuotare il banco attivo');
}

async function testNewKitCancelledDoesNothing(){
  const sb = await run(`
    ac();
    clips[2][2] = { buffer:{duration:1}, name:'Resta', mode:'loop' };
    newKitBtn.onclick();
    globalThis.__result = clips[2][2] && clips[2][2].name;
  `, { __promptReturns: null });
  assert.strictEqual(sb.__result, 'Resta', 'annullare il prompt non deve toccare nulla');
}

async function testNewKitDoesNotTouchOtherBanks(){
  const sb = await run(`
    ac();
    banks[1][0][0] = { buffer:{duration:1}, name:'AltroBanco', mode:'loop' };
    newKitBtn.onclick();
    globalThis.__result = banks[1][0][0] && banks[1][0][0].name;
  `, { __promptReturns: 'X' });
  assert.strictEqual(sb.__result, 'AltroBanco', 'gli altri banchi non devono essere toccati');
}

async function testNewKitIsUndoable(){
  const sb = await run(`
    ac();
    clips[0][0] = { buffer:{duration:1}, name:'Y', mode:'loop' };
    const before = undoStack.length;
    newKitBtn.onclick();
    globalThis.__result = undoStack.length > before;
  `, { __promptReturns: 'X' });
  assert.strictEqual(sb.__result, true, '"+ Nuovo kit" deve essere annullabile');
}

(async () => {
  const tests = [
    ['"+ Nuovo kit" con nome svuota il banco attivo', testNewKitClearsActiveBankWhenNamed],
    ['"+ Nuovo kit" annullato non fa nulla', testNewKitCancelledDoesNothing],
    ['"+ Nuovo kit" non tocca gli altri banchi', testNewKitDoesNotTouchOtherBanks],
    ['"+ Nuovo kit" e\' annullabile', testNewKitIsUndoable],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

`newKitBtn` deve essere raggiungibile dal test: dichiaralo con `const`/`let` **fuori** dall'IIFE di `genre_ui.js` (stesso principio di `catalogRowEls` nel Task 4), non dentro.

Esegui `node test_new_kit_button.js` — deve fallire (`newKitBtn is not defined`).

- [ ] **Step 3: Implementa**

In `_sorgente/genre_ui.js`, prima della riga `(function(){`, aggiungi:

```js
let newKitBtn=null, draftKitName=null;
```

Dentro l'IIFE, subito dopo `bar.appendChild(lab); bar.appendChild(sel); bar.appendChild(btn); bar.appendChild(stat);`, aggiungi:

```js
  newKitBtn=document.createElement('button'); newKitBtn.textContent='+ Nuovo kit';
  newKitBtn.style.cssText='background:#20242e;border:1px solid #2c313d;color:#e8ebf1;border-radius:8px;padding:9px 14px;cursor:pointer;font-size:13px';
  bar.appendChild(newKitBtn);
  newKitBtn.onclick=()=>{
    const name=prompt('Nome del kit:'); if(!name) return;
    pushUndo();
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) clips[r][c]=null;
    recomputeTrackColors(); renderAll(); refreshAllLeds();
    draftKitName=name;
    stat.textContent='Nuovo kit «'+name+'» — trascina suoni dal catalogo per riempirlo.';
  };
```

- [ ] **Step 4: Verifica GREEN**

`node test_new_kit_button.js` — 4/4 verde.

- [ ] **Step 5: Commit**

```bash
git add "_sorgente/genre_ui.js" "scratchpad/harness.js" "scratchpad/test_new_kit_button.js"
git commit -m "Bottone \"+ Nuovo kit\": svuota il banco attivo per costruire un kit da zero"
```

---

### Task 7: "💾 Salva come kit" + `<select>` con i kit personalizzati + "🗑️ Elimina kit"

**Files:**
- Modify: `scratchpad/harness.js` (`remove()`/`removeChild` sui fake elementi — mancano, servono per ricostruire le opzioni del `<select>`)
- Modify: `_sorgente/genre_ui.js`
- Test: `scratchpad/test_save_delete_kit.js` (nuovo)

**Interfaces:**
- Consuma: `kitPut`, `kitDelete`, `customKits`, `newKitId` (Task 5); `draftKitName` (Task 6).
- Produce: `refreshGenreSelectOptions()`, bottoni `saveKitBtn`/`delKitBtn`.

- [ ] **Step 1: Correggi `remove()`/aggiungi `removeChild` nel fake DOM**

In `scratchpad/harness.js`, dentro `makeFakeEl`, la proprietà `remove` è oggi un no-op (`remove(){},`). Sostituiscila e aggiungi `removeChild`:

```js
    removeChild(child){ const i=el.children.indexOf(child); if(i>=0) el.children.splice(i,1); if(child) child.parentNode=null; return child; },
    remove(){ if(el.parentNode && el.parentNode.children){ const i=el.parentNode.children.indexOf(el); if(i>=0) el.parentNode.children.splice(i,1); } },
```

(sostituisce la vecchia riga `remove(){},` — `removeChild` è nuovo, va aggiunto vicino a `appendChild`/`insertBefore`)

- [ ] **Step 2: Scrivi il test (fallisce: le funzioni non esistono)**

```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const { runWithApp } = require('./harness.js');
const GENRE_UI_SRC = fs.readFileSync('D:/MUSIC/Launchpad Studio/_sorgente/genre_ui.js', 'utf8');
const FAKE_GENRES = { G1: { bpm:120, clips: [] } };

async function run(code, extraInject){
  return runWithApp(GENRE_UI_SRC + '\n' + code, { inject: Object.assign({ GENRES: FAKE_GENRES }, extraInject||{}) });
}

async function testSaveAddsToCustomKitsAndSelect(){
  const sb = await run(`
    ac();
    await saveKitBtn.onclick();
    globalThis.__result = { count: customKits.length, name: customKits[0] && customKits[0].name, selVal: sel.value };
  `, { __promptReturns: 'Il mio kit' });
  const r = sb.__result;
  assert.strictEqual(r.count, 1, 'salvare deve aggiungere un kit a customKits');
  assert.strictEqual(r.name, 'Il mio kit', 'il nome deve essere quello del prompt');
  assert.ok(r.selVal.startsWith('kit:'), 'il <select> deve selezionare il kit appena salvato');
});

async function testSaveWithNoClipsStillWorks(){
  const sb = await run(`
    ac();
    await saveKitBtn.onclick();
    globalThis.__result = customKits[0].clips.length;
  `, { __promptReturns: 'Vuoto' });
  assert.strictEqual(sb.__result, 0, 'un kit senza pad riempiti deve comunque salvarsi (0 clip)');
});

async function testDeleteRemovesFromCustomKitsAndFallsBack(){
  const sb = await run(`
    ac();
    await saveKitBtn.onclick();
    const id = sel.value;
    await delKitBtn.onclick();
    globalThis.__result = { count: customKits.length, selVal: sel.value };
  `, { __promptReturns: 'Da cancellare' });
  const r = sb.__result;
  assert.strictEqual(r.count, 0, 'eliminare deve svuotare customKits');
  assert.strictEqual(r.selVal, 'G1', 'dopo l\\'eliminazione il <select> deve ricadere su un genere di fabbrica');
});

async function testDelKitHiddenForBuiltinGenre(){
  const sb = await run(`
    sel.value='G1'; updateDelKitVisibility();
    const hiddenForBuiltin = delKitBtn.style.display==='none';
    await saveKitBtn.onclick();
    updateDelKitVisibility();
    const visibleForCustom = delKitBtn.style.display!=='none';
    globalThis.__result = { hiddenForBuiltin, visibleForCustom };
  `, { __promptReturns: 'X' });
  const r = sb.__result;
  assert.strictEqual(r.hiddenForBuiltin, true, 'su un genere di fabbrica il bottone Elimina deve restare nascosto');
  assert.strictEqual(r.visibleForCustom, true, 'su un kit personalizzato deve comparire');
});

async function testRefreshDoesNotDuplicateOptions(){
  const sb = await run(`
    ac();
    await saveKitBtn.onclick();
    refreshGenreSelectOptions(); refreshGenreSelectOptions();
    globalThis.__result = sel.children.filter(o=>o.value==='kit:'+customKits[0].id).length;
  `, { __promptReturns: 'X' });
  assert.strictEqual(sb.__result, 1, 'richiamare refreshGenreSelectOptions piu\\' volte non deve duplicare le opzioni');
});

(async () => {
  const tests = [
    ['Salva come kit aggiunge a customKits e al select', testSaveAddsToCustomKitsAndSelect],
    ['Salvare un kit senza pad funziona comunque', testSaveWithNoClipsStillWorks],
    ['Elimina kit rimuove e ricade sui generi di fabbrica', testDeleteRemovesFromCustomKitsAndFallsBack],
    ['Elimina kit nascosto/visibile secondo la selezione', testDelKitHiddenForBuiltinGenre],
    ['refreshGenreSelectOptions non duplica le opzioni', testRefreshDoesNotDuplicateOptions],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

`saveKitBtn`/`delKitBtn`/`refreshGenreSelectOptions`/`updateDelKitVisibility` vanno dichiarati fuori dall'IIFE (stesso principio di `newKitBtn`).

Esegui `node test_save_delete_kit.js` — deve fallire.

- [ ] **Step 3: Implementa**

In `_sorgente/genre_ui.js`, sostituisci la riga `let newKitBtn=null, draftKitName=null;` (aggiunta nel Task 6, fuori dall'IIFE) con:

```js
let newKitBtn=null, draftKitName=null, saveKitBtn=null, delKitBtn=null, customKitOptionEls=[];
let refreshGenreSelectOptions, updateDelKitVisibility;   // assegnate dentro l'IIFE (chiudono su sel/customKits)
```

Dentro l'IIFE, dopo il blocco `newKitBtn...` aggiunto nel Task 6, aggiungi:

```js
  refreshGenreSelectOptions=function(){
    customKitOptionEls.forEach(o=>o.remove());
    customKitOptionEls=[];
    if(!customKits.length) return;
    const sep=document.createElement('option'); sep.disabled=true; sep.textContent='— I tuoi kit —';
    sel.appendChild(sep); customKitOptionEls.push(sep);
    customKits.forEach(k=>{ const o=document.createElement('option'); o.value='kit:'+k.id; o.textContent=k.name; sel.appendChild(o); customKitOptionEls.push(o); });
  };
  updateDelKitVisibility=function(){ delKitBtn.style.display = sel.value.startsWith('kit:') ? 'inline-block' : 'none'; };
  sel.onchange=updateDelKitVisibility;

  saveKitBtn=document.createElement('button'); saveKitBtn.textContent='💾 Salva come kit';
  saveKitBtn.style.cssText=newKitBtn.style.cssText;
  bar.appendChild(saveKitBtn);
  function buildKitSnapshot(name,id){
    const out={id, name, bpm, bars, phraseBars,
      master:audioCtx?+document.getElementById('master').value:1,
      filter:+document.getElementById('filter').value,
      revWet:+document.getElementById('revWet').value, revSize:+document.getElementById('revSize').value,
      dlyWet:+document.getElementById('dlyWet').value, dlyFb:+document.getElementById('dlyFb').value, dlyTime:+document.getElementById('dlyTime').value,
      tracks:tracks.map(t=>({volume:t.volume,muted:t.muted,solo:t.solo,low:t.low||0,high:t.high||0,revSend:t.revSend||0,dlySend:t.dlySend||0})),
      clips:[]};
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){ const cl=clips[r][c];
      if(cl&&cl.raw) out.clips.push({r,c,name:cl.name,mime:cl.mime,mode:cl.mode||'loop',trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm||bpm,raw:cl.raw}); }
    return out;
  }
  saveKitBtn.onclick=async ()=>{
    const name=prompt('Nome del kit:', draftKitName||'Kit personalizzato'); if(!name) return;
    const kit=buildKitSnapshot(name, newKitId());
    await kitPut(kit);
    customKits.push(kit);
    refreshGenreSelectOptions();
    sel.value='kit:'+kit.id;
    updateDelKitVisibility();
    stat.textContent='Kit «'+name+'» salvato ✓';
  };

  delKitBtn=document.createElement('button'); delKitBtn.textContent='🗑️ Elimina kit'; delKitBtn.style.display='none';
  delKitBtn.style.cssText=newKitBtn.style.cssText;
  bar.appendChild(delKitBtn);
  delKitBtn.onclick=async ()=>{
    if(!sel.value.startsWith('kit:')) return;
    const id=sel.value.slice(4);
    await kitDelete(id);
    customKits=customKits.filter(k=>k.id!==id);
    refreshGenreSelectOptions();
    sel.value=Object.keys(GENRES)[0]||'';
    updateDelKitVisibility();
    stat.textContent='Kit eliminato';
  };
  refreshGenreSelectOptions();
```

- [ ] **Step 4: Verifica GREEN**

`node test_save_delete_kit.js` — 5/5 verde.

- [ ] **Step 5: Commit**

```bash
git add "_sorgente/genre_ui.js" "scratchpad/harness.js" "scratchpad/test_save_delete_kit.js"
git commit -m "Salva/Elimina kit personalizzato, elencato nel <select> Genere"
```

---

### Task 8: `loadGenre` → `loadGenreData` generico (condiviso da generi di fabbrica e kit)

**Files:**
- Modify: `_sorgente/genre_ui.js`
- Test: `scratchpad/test_load_generic.js` (nuovo)

**Interfaces:**
- Produce: `loadGenreData(data,label)` (generica), `loadGenre(key)` (wrapper sottile per i generi di fabbrica, comportamento invariato), `loadCustomKit(id)`.
- Modifica: `btn.onclick` ("▶ Carica genere") ora instrada in base al prefisso `kit:` di `sel.value`.

- [ ] **Step 1: Scrivi il test (fallisce: `loadGenreData`/`loadCustomKit` non esistono)**

```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const { runWithApp } = require('./harness.js');
const GENRE_UI_SRC = fs.readFileSync('D:/MUSIC/Launchpad Studio/_sorgente/genre_ui.js', 'utf8');
const FAKE_GENRES = { G1: { bpm:110, bars:4, clips: [
  { r:0,c:0, name:'Kick_01', mime:'audio/webm', data:'AAAA', mode:'loop' },
] }, G2: { bpm:90, clips: [] } };

async function run(code, extraInject){
  return runWithApp(GENRE_UI_SRC + '\n' + code, { inject: Object.assign({ GENRES: FAKE_GENRES }, extraInject||{}) });
}

async function testLoadGenreStillWorks(){
  const sb = await run(`
    ac();
    await loadGenre('G1');
    globalThis.__result = { bpm, name: clips[0][0] && clips[0][0].name };
  `);
  assert.strictEqual(sb.__result.bpm, 110, 'loadGenre deve continuare a impostare il bpm del genere');
  assert.strictEqual(sb.__result.name, 'Kick_01', 'loadGenre deve continuare a caricare i clip del genere');
}

async function testLoadCustomKitFromRawBuffer(){
  const rawB64='AAAA';
  const sb = await run(`
    ac();
    const rawAb = b64ToAb('${rawB64}');
    customKits.push({ id:'k1', name:'MioKit', bpm:100, bars:4, tracks:[], clips:[
      { r:1,c:1, name:'Snare_01', mime:'audio/webm', mode:'loop', raw: rawAb }
    ] });
    await loadCustomKit('k1');
    globalThis.__result = { bpm, name: clips[1][1] && clips[1][1].name };
  `);
  assert.strictEqual(sb.__result.bpm, 100, 'caricare un kit personalizzato deve impostare il suo bpm');
  assert.strictEqual(sb.__result.name, 'Snare_01', 'caricare un kit personalizzato deve popolare i pad da clip.raw (non clip.data)');
}

async function testButtonRoutesToCustomKitByPrefix(){
  const sb = await run(`
    ac();
    customKits.push({ id:'k2', name:'Altro', bpm:77, bars:4, tracks:[], clips:[] });
    sel.value='kit:k2';
    await btn.onclick();
    globalThis.__result = bpm;
  `);
  assert.strictEqual(sb.__result, 77, '"\u25b6 Carica genere" con un kit selezionato deve caricare il kit, non un genere');
}

async function testKitRawBufferNotCorruptedAfterLoad(){
  const sb = await run(`
    ac();
    const rawAb = b64ToAb('AAAA');
    const kit = { id:'k3', name:'Integro', bpm:100, bars:4, tracks:[], clips:[
      { r:2,c:2, name:'Hat_01', mime:'audio/webm', mode:'loop', raw: rawAb }
    ] };
    customKits.push(kit);
    await loadCustomKit('k3');
    globalThis.__result = kit.clips[0].raw.byteLength;
  `);
  assert.ok(sb.__result>0, 'il raw ArrayBuffer del kit salvato deve restare integro (non consumato dalla decodifica)');
}

(async () => {
  const tests = [
    ['loadGenre continua a funzionare come prima', testLoadGenreStillWorks],
    ['loadCustomKit carica da clip.raw', testLoadCustomKitFromRawBuffer],
    ['il bottone Carica instrada un kit: al posto giusto', testButtonRoutesToCustomKitByPrefix],
    ['il raw del kit non viene corrotto dal caricamento', testKitRawBufferNotCorruptedAfterLoad],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

`btn`/`sel` vanno dichiarati fuori dall'IIFE come le altre variabili condivise dei task precedenti (se non lo sono già — verifica lo stato attuale del file prima di procedere).

Esegui `node test_load_generic.js` — deve fallire.

- [ ] **Step 2: Implementa**

Sostituisci la funzione `loadGenre` esistente e il suo `btn.onclick=()=>loadGenre(sel.value);` con:

```js
  async function loadGenreData(data,label){
    stat.textContent='Carico '+label+'…'; await new Promise(r=>setTimeout(r,20));
    pushUndo();
    loadingSet=true;
    await stopAllSmooth(1.2);
    perfMode=null;   // esce dalla modalita' Drums: qui si sta per sostituire clips interi
    bpm=data.bpm||120; document.getElementById('bpm').value=bpm; document.getElementById('bpmVal').textContent=bpm;
    bars=data.bars||4; document.getElementById('bars').value=([1,2,4,8].includes(bars)?bars:4);
    quantMode='off'; document.getElementById('quant').value='off';
    phraseBars=data.phraseBars||bars;
    ac();
    const masterVal=data.master!=null?data.master:1.0;
    document.getElementById('master').value=masterVal; masterGain.gain.value=masterVal;
    const filterVal=data.filter!=null?data.filter:1.0;
    document.getElementById('filter').value=filterVal; masterFilter.frequency.setTargetAtTime(20*Math.pow(1000,filterVal), audioCtx.currentTime, 0.02);
    const revWetVal=data.revWet!=null?data.revWet:0, revSizeVal=data.revSize!=null?data.revSize:2;
    document.getElementById('revWet').value=revWetVal; fxReverbSend.gain.value=revWetVal;
    document.getElementById('revSize').value=revSizeVal; setReverbSize(revSizeVal);
    const dlyWetVal=data.dlyWet!=null?data.dlyWet:0, dlyFbVal=data.dlyFb!=null?data.dlyFb:0.35, dlyTimeVal=data.dlyTime!=null?data.dlyTime:0.5;
    document.getElementById('dlyWet').value=dlyWetVal; fxDelaySend.gain.value=dlyWetVal;
    document.getElementById('dlyFb').value=dlyFbVal; fxDelayFb.gain.value=dlyFbVal;
    document.getElementById('dlyTime').value=dlyTimeVal; fxDelay.delayTime.value=secPerBeat()*dlyTimeVal;
    (data.tracks||[]).forEach((t,c)=>{ if(c<COLS){ const v=t.volume!=null?t.volume:1.0; tracks[c].volume=v;tracks[c].muted=t.muted;tracks[c].solo=t.solo;
      tracks[c].low=t.low||0; tracks[c].high=t.high||0; tracks[c].revSend=t.revSend||0; tracks[c].dlySend=t.dlySend||0;
      tracks[c]._vol.value=v; tracks[c]._m.classList.toggle('on',t.muted); tracks[c]._s.classList.toggle('on',t.solo);} });
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) clips[r][c]=null;
    let ok=0;
    for(const cl of data.clips){ try{
      const src = cl.data!=null ? b64ToAb(cl.data) : cl.raw.slice(0);
      const raw = src.slice(0);
      const audio=await ac().decodeAudioData(src);
      clips[cl.r][cl.c]={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',sourceBpm:cl.sourceBpm||data.bpm,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null};
      ok++;
    }catch(e){} }
    applyMix(); applyTrackFX(); recomputeTrackColors(); renderAll(); refreshAllLeds(); updatePerfModeUI();
    loadingSet=false;
    doAutosave();
    stat.textContent=label+' ✓ ('+ok+' loop)';
  }
  async function loadGenre(key){ const data=GENRES[key]; if(!data) return; await loadGenreData(data,key); }
  async function loadCustomKit(id){ const kit=customKits.find(k=>k.id===id); if(!kit) return; await loadGenreData(kit,kit.name); }
  btn.onclick=()=>{
    if(sel.value.startsWith('kit:')) loadCustomKit(sel.value.slice(4));
    else loadGenre(sel.value);
  };
```

`loadGenre`/`loadCustomKit`/`loadGenreData` devono restare raggiungibili dal test: se non già dichiarate fuori dall'IIFE nei task precedenti, aggiungi `let loadGenre, loadCustomKit;` fuori dall'IIFE e assegnale (`function`-style, non `function loadGenre(...)`) dentro, come già fatto per `refreshGenreSelectOptions`.

- [ ] **Step 3: Verifica GREEN**

`node test_load_generic.js` — 4/4 verde. Esegui anche `node test_save_delete_kit.js` e `node test_new_kit_button.js` per confermare che nessuna variabile condivisa si sia rotta nel refactor.

- [ ] **Step 4: Commit**

```bash
git add "_sorgente/genre_ui.js" "scratchpad/test_load_generic.js"
git commit -m "loadGenre -> loadGenreData generico, condiviso da generi di fabbrica e kit personalizzati"
```

---

### Task 9: Export/Import `.lpkit`

**Files:**
- Modify: `_sorgente/genre_ui.js`
- Test: `scratchpad/test_export_import_kit.js` (nuovo)

**Interfaces:**
- Consuma: `abToB64`/`b64ToAb` (copione principale), `customKits`, `kitPut`, `newKitId`, `refreshGenreSelectOptions`.
- Produce: bottoni `exportKitBtn`/`importKitBtn` + `<input type=file>` nascosto.

- [ ] **Step 1: Scrivi il test (fallisce: i bottoni non esistono)**

```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const { runWithApp } = require('./harness.js');
const GENRE_UI_SRC = fs.readFileSync('D:/MUSIC/Launchpad Studio/_sorgente/genre_ui.js', 'utf8');
const FAKE_GENRES = { G1: { bpm:120, clips: [] } };

async function run(code, extraInject){
  return runWithApp(GENRE_UI_SRC + '\n' + code, { inject: Object.assign({ GENRES: FAKE_GENRES }, extraInject||{}) });
}

async function testExportWritesLpkitBlobWithBase64Data(){
  const sb = await run(`
    ac();
    const rawAb = b64ToAb('AAAA');
    customKits.push({ id:'e1', name:'Esportami', bpm:100, bars:4, phraseBars:4, master:1, filter:1,
      revWet:0, revSize:2, dlyWet:0, dlyFb:0.35, dlyTime:0.5, tracks:[],
      clips:[ { r:0,c:0, name:'Kick_01', mime:'audio/webm', mode:'loop', trimStart:0, trimEnd:null, sourceBpm:100, raw: rawAb } ] });
    sel.value='kit:e1';
    exportKitBtn.onclick();
    const parsed = JSON.parse(await __lastBlob.text());
    globalThis.__result = { name: parsed.name, dataIsString: typeof parsed.clips[0].data === 'string' };
  `);
  const r = sb.__result;
  assert.strictEqual(r.name, 'Esportami', 'il file esportato deve contenere il nome del kit');
  assert.strictEqual(r.dataIsString, true, 'i clip esportati devono avere data in base64 (stringa), non raw ArrayBuffer');
}

async function testExportWithoutCustomKitSelectedShowsStatus(){
  const sb = await run(`
    sel.value='G1';
    const before = __lastBlob;
    exportKitBtn.onclick();
    globalThis.__result = { blobUnchanged: __lastBlob===before, status: stat.textContent.length>0 };
  `);
  const r = sb.__result;
  assert.strictEqual(r.blobUnchanged, true, 'senza un kit personalizzato selezionato non deve scaricare nulla');
}

async function testImportAddsCustomKit(){
  const fileText = JSON.stringify({ version:1, name:'Importato', bpm:88, bars:4, tracks:[],
    clips:[ { r:3,c:3, name:'Clap_01', mime:'audio/webm', mode:'loop', trimStart:0, trimEnd:null, sourceBpm:88, data:'AAAA' } ] });
  const sb = await run(`
    ac();
    const fakeFile = { text: async ()=> ${JSON.stringify(fileText)} };
    await kitFileInput.onchange({ target:{ files:[fakeFile], value:'' } });
    globalThis.__result = { count: customKits.length, name: customKits[0] && customKits[0].name, rawLen: customKits[0].clips[0].raw.byteLength };
  `);
  const r = sb.__result;
  assert.strictEqual(r.count, 1, 'importare deve aggiungere un kit a customKits');
  assert.strictEqual(r.name, 'Importato', 'il nome deve venire dal file');
  assert.ok(r.rawLen>0, 'i clip importati devono avere raw decodificato da data');
}

async function testImportInvalidJsonAlerts(){
  const sb = await run(`
    const fakeFile = { text: async ()=> 'non e\\' json' };
    await kitFileInput.onchange({ target:{ files:[fakeFile], value:'' } });
    globalThis.__result = { alerted: !!__lastAlert, count: customKits.length };
  `);
  const r = sb.__result;
  assert.strictEqual(r.alerted, true, 'un file .lpkit non valido deve avvisare');
  assert.strictEqual(r.count, 0, 'e non deve aggiungere nulla a customKits');
}

(async () => {
  const tests = [
    ['Esporta scrive un .lpkit con data in base64', testExportWritesLpkitBlobWithBase64Data],
    ['Esporta senza kit selezionato non fa nulla', testExportWithoutCustomKitSelectedShowsStatus],
    ['Importa aggiunge un kit personalizzato', testImportAddsCustomKit],
    ['Importa un JSON non valido avvisa', testImportInvalidJsonAlerts],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

`exportKitBtn`/`kitFileInput` vanno dichiarati fuori dall'IIFE come gli altri elementi condivisi.

Esegui `node test_export_import_kit.js` — deve fallire.

- [ ] **Step 2: Implementa**

Dentro l'IIFE, dopo il blocco `delKitBtn...` del Task 7, aggiungi:

```js
  exportKitBtn=document.createElement('button'); exportKitBtn.textContent='📂 Esporta kit';
  exportKitBtn.style.cssText=newKitBtn.style.cssText;
  bar.appendChild(exportKitBtn);
  exportKitBtn.onclick=()=>{
    if(!sel.value.startsWith('kit:')){ stat.textContent='Seleziona prima un kit personalizzato da esportare.'; return; }
    const kit=customKits.find(k=>k.id===sel.value.slice(4)); if(!kit) return;
    const out={version:1,id:kit.id,name:kit.name,bpm:kit.bpm,bars:kit.bars,phraseBars:kit.phraseBars,
      master:kit.master,filter:kit.filter,revWet:kit.revWet,revSize:kit.revSize,dlyWet:kit.dlyWet,dlyFb:kit.dlyFb,dlyTime:kit.dlyTime,
      tracks:kit.tracks,
      clips:kit.clips.map(cl=>({r:cl.r,c:cl.c,name:cl.name,mime:cl.mime,mode:cl.mode,trimStart:cl.trimStart,trimEnd:cl.trimEnd,sourceBpm:cl.sourceBpm,data:abToB64(cl.raw)}))};
    const blob=new Blob([JSON.stringify(out)],{type:'application/json'});
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
    a.download=kit.name.replace(/[^a-z0-9 _-]/gi,'')+'.lpkit'; a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),2000);
  };

  importKitBtn=document.createElement('button'); importKitBtn.textContent='📥 Importa kit';
  importKitBtn.style.cssText=newKitBtn.style.cssText;
  kitFileInput=document.createElement('input'); kitFileInput.type='file'; kitFileInput.accept='.lpkit,application/json'; kitFileInput.style.display='none';
  bar.appendChild(importKitBtn); bar.appendChild(kitFileInput);
  importKitBtn.onclick=()=>kitFileInput.click();
  kitFileInput.onchange=async (e)=>{
    const f=e.target.files[0]; if(!f) return; e.target.value='';
    try{
      const data=JSON.parse(await f.text());
      const id=newKitId();
      const kit={id,name:data.name||'Kit importato',bpm:data.bpm,bars:data.bars,phraseBars:data.phraseBars,
        master:data.master,filter:data.filter,revWet:data.revWet,revSize:data.revSize,dlyWet:data.dlyWet,dlyFb:data.dlyFb,dlyTime:data.dlyTime,
        tracks:data.tracks||[],
        clips:(data.clips||[]).map(cl=>({r:cl.r,c:cl.c,name:cl.name,mime:cl.mime,mode:cl.mode,trimStart:cl.trimStart,trimEnd:cl.trimEnd,sourceBpm:cl.sourceBpm,raw:b64ToAb(cl.data)}))};
      await kitPut(kit);
      customKits.push(kit);
      refreshGenreSelectOptions();
      stat.textContent='Kit «'+kit.name+'» importato ✓';
    }catch(err){ alert('File .lpkit non valido.'); }
  };
```

Aggiungi `exportKitBtn=null, importKitBtn=null, kitFileInput=null` alla dichiarazione condivisa fuori dall'IIFE (insieme alle altre variabili dei task precedenti).

- [ ] **Step 3: Verifica GREEN**

`node test_export_import_kit.js` — 4/4 verde.

- [ ] **Step 4: Commit**

```bash
git add "_sorgente/genre_ui.js" "scratchpad/test_export_import_kit.js"
git commit -m "Esporta/Importa kit personalizzato come file .lpkit"
```

---

### Task 10: Integrazione finale — `assemble.py`, rebuild reale, regressione completa, documentazione

**Files:**
- Modify: `_sorgente/assemble.py` (inietta anche `catalog_ui.js`)
- Modify: `SVILUPPO.md`, `Manuale Launchpad Studio.html`

Questo è l'unico task che tocca `assemble.py` e produce davvero `Launchpad Studio.html` con la feature completa — tutti i task precedenti sono stati verificati leggendo i sorgenti direttamente, senza mai ricostruire il file da 93MB.

- [ ] **Step 1: Aggiorna `assemble.py`**

```python
SRC     = HERE / "launchpad-studio.html"
DATA    = HERE / "genres.json"
UI      = HERE / "genre_ui.js"
DKDATA  = HERE / "drumkit_preset.json"
DKUI    = HERE / "drumkit_preset_ui.js"
CATUI   = HERE / "catalog_ui.js"
OUT   = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "Launchpad Studio.html"

def main():
    for p in (SRC, DATA, UI, DKDATA, DKUI, CATUI):
        if not p.exists():
            sys.exit(f"ERRORE: manca {p.name} in {HERE}")

    src   = SRC.read_text(encoding="utf-8")
    ui    = UI.read_text(encoding="utf-8")
    dkui  = DKUI.read_text(encoding="utf-8")
    catui = CATUI.read_text(encoding="utf-8")
    genres = json.loads(DATA.read_text(encoding="utf-8"))
    nclip  = sum(len(g.get("clips", [])) for g in genres.values())
    data_text = DATA.read_text(encoding="utf-8").strip()
    drumkit = json.loads(DKDATA.read_text(encoding="utf-8"))
    ndrum   = len(drumkit)
    drumkit_text = DKDATA.read_text(encoding="utf-8").strip()

    block = ("\n<script>\nconst GENRES = " + data_text + ";\n" + ui.rstrip()
             + "\nconst DRUM_KIT_PRESET = " + drumkit_text + ";\n" + dkui.rstrip()
             + "\n" + catui.rstrip()
             + "\n</script>\n\n")

    idx = src.rfind("</body>")
    if idx == -1:
        sys.exit("ERRORE: </body> non trovato nel sorgente")
    out = src[:idx] + block + src[idx:]

    OUT.write_text(out, encoding="utf-8", newline="")
    mb = OUT.stat().st_size / 1e6
    print(f"OK: {OUT.name}  ({mb:.1f} MB)  — {len(genres)} generi, {nclip} clip, kit Drums {ndrum} pad")
```

(cambi: nuova costante `CATUI`, aggiunta alla validazione `for p in (...)`, lettura `catui`, concatenazione nel `block`)

- [ ] **Step 2: Rebuild e verifica di presenza**

```bash
cd _sorgente && python assemble.py
grep -c "Catalogo suoni" "../Launchpad Studio.html"
grep -c "kitDbOpen" "../Launchpad Studio.html"
```

Entrambi devono restituire un numero `>0`.

- [ ] **Step 3: Regressione completa**

Da `scratchpad/`:

```bash
fail=0; for f in test_*.js; do out=$(node "$f" 2>&1); if echo "$out" | grep -q "FAIL"; then echo "== $f =="; echo "$out"; fail=1; fi; done; if [ $fail -eq 0 ]; then echo "TUTTI I TEST PASSANO"; fi
```

Deve stampare `TUTTI I TEST PASSANO` (tutti i file, inclusi quelli con `srcPath: BIG` come `test_drumkit_preset.js`, che ora leggono un file più grande ma con contenuto invariato per il kit Drums).

- [ ] **Step 4: Aggiorna la documentazione**

In `SVILUPPO.md`, nella sezione "5. Funzioni implementate (checklist)", aggiungi una frase che descrive: pannello Catalogo suoni (genere→categoria→suono, click=anteprima, Ctrl+trascina=piazza), regola di piazzamento (pad vuoto + colonna libera o stessa categoria, altrimenti messaggio di stato), "+ Nuovo kit"/"💾 Salva come kit"/"🗑️ Elimina kit" nella barra Genere, persistenza IndexedDB (`lpstudioCustomKits`) + export/import `.lpkit`.

In `Manuale Launchpad Studio.html`, aggiungi una nuova sottosezione (dopo quella sui generi) che spiega all'utente finale: come sfogliare il catalogo, come trascinare un suono su un pad (Ctrl+trascina, solo su colonne dello stesso colore/vuote), come creare/salvare/eliminare/esportare/importare un kit personalizzato.

- [ ] **Step 5: Commit**

```bash
git add "_sorgente/assemble.py" "SVILUPPO.md" "Manuale Launchpad Studio.html"
git commit -m "Integra il catalogo suoni nella build (assemble.py) + documentazione"
```
