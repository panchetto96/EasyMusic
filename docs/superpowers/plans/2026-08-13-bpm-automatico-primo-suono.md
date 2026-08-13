# BPM automatico agganciato al primo suono che parte — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Il primo pad Loop (o la prima colonna con `sourceBpm` in un lancio scena) che parte dopo uno Stop tutto/Re-sync stabilisce da solo il BPM di progetto; ogni altro suono con un BPM di origine noto — anche di generi diversi — si adatta automaticamente, senza bisogno del checkbox "Sync BPM" (che sparisce dalla UI). Aggiunge anche un campo "BPM di origine" modificabile a mano per qualunque pad e un tasto di rilevamento assistito, cosi' anche i file trascinati manualmente possono partecipare.

**Architecture:** Un'unica funzione di aggancio (`tryEstablishTempoReference`) chiamata in un solo punto del codice esistente (`scheduleClip`, gia' attraversato sia dalla pressione diretta di un pad Loop sia dal lancio scena) stabilisce `bpm` la prima volta che vede un clip con `sourceBpm` noto, poi si disattiva finche' `stopAll()`/`resyncAll()` non la resettano. `clipRate()` (gia' esistente) perde la sua dipendenza dal checkbox `syncBpm` e applica sempre il rapporto BPM quando `sourceBpm` e' noto. Il nuovo campo "BPM di origine" e il tasto "Rileva BPM" toccano solo `clip.sourceBpm` e il pannello di editing, riusando gli stessi punti di refresh (`selectPad`) e persistenza (`saveGenreOverride`/override di genere) gia' costruiti per taglio/pitch/reverse.

**Tech Stack:** JavaScript vanilla, Web Audio API, nessuna libreria esterna. Test con l'harness Node/vm esistente (`scratchpad/harness.js`, gia' presente nella directory scratchpad di sessione).

**Spec:** `docs/superpowers/specs/2026-08-13-bpm-automatico-primo-suono-design.md`

## Global Constraints

- Un solo punto di aggancio: `tryEstablishTempoReference(clip)` viene chiamato SOLO dall'inizio di `scheduleClip(r,c,when)` in `_sorgente/launchpad-studio.html` — nessun altro hook.
- Solo i pad in modalita' **Loop** possono stabilire il riferimento (passano da `scheduleClip`). One-shot (`playOnce`) e Gate (`startGate`/`triggerDrumHit`) non lo chiamano mai, ma continuano ad **adattarsi** al riferimento attivo tramite `rateFor`/`clipRate` come gia' fanno oggi.
- `stopAll()` e `resyncAll()` impostano entrambi `tempoReferenceSet=false` all'inizio della loro esecuzione.
- `clipRate(clip)` diventa `return (clip && clip.sourceBpm) ? bpm/clip.sourceBpm : 1;` — nessuna dipendenza da `syncBpm`.
- Il checkbox **"Sync BPM"** (`#syncBpm`) resta nel DOM/JS invariato (variabile, handler, serializzazione in autosave/set) ma la sua `<label>` prende `display:none` — stessa convenzione gia' usata per Gain/Choke in questo progetto (nascosto, non cancellato).
- Ogni file sorgente modificato vive in `_sorgente/`: dopo ogni task che tocca `_sorgente/launchpad-studio.html` o `_sorgente/genre_ui.js`, ricostruire il file finale con `python assemble.py` (eseguito da dentro `_sorgente/`, produce `../Launchpad Studio.html`) prima di qualunque verifica in Chrome vero.
- I test usano l'harness esistente `runWithApp` da `C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad\harness.js` (gia' presente, non va ricreato). I file di test vanno scritti in quella stessa cartella scratchpad (mai nel repository) e lanciati con `node <nome-test>.js` da li'.
- Dopo l'ultimo task, verificare in Chrome vero via Playwright (`playwright-core`, gia' installato in scratchpad con `executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'`) prima di considerare il lavoro concluso — la sospensione fake-DOM dell'harness non basta per un cambiamento che tocca sia audio (scheduling) sia UI.

---

## Task 1: Meccanismo di aggancio automatico del tempo

**Files:**
- Modify: `_sorgente/launchpad-studio.html` (righe indicate sotto si riferiscono allo stato attuale del file, prima di questo task)
- Test: `<scratchpad>/test_bpm_auto_reference.js` (nuovo)

**Interfaces:**
- Consumes: `bpm` (let globale, riga 626), `clipRate(clip)`/`rateFor(clip)` (righe 1197-1199), `scheduleClip(r,c,when)` (riga 1473), `launchScene(r)` (riga 1463), `stopAll()` (riga 1235), `resyncAll()` (riga 1261), `playOnce`/`startGate` (invariati, non toccati da questo task).
- Produces: `let tempoReferenceSet` (nuovo stato globale, letto/scritto anche dal Task 2), `function tryEstablishTempoReference(clip)` (nuova, nessun altro task la chiama direttamente ma il Task 2 la lascia intatta).

- [ ] **Step 1: Scrivi i test (RED)**

Crea `<scratchpad>/test_bpm_auto_reference.js` con questo contenuto:

```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testEstablishesReferenceOnceThenIgnoresLater(){
  const sb = await runWithApp(`
    ac();
    const clipA = { sourceBpm: 140 };
    tryEstablishTempoReference(clipA);
    const afterFirst = { bpm, tempoReferenceSet, fieldVal: document.getElementById('bpm').value };
    const clipB = { sourceBpm: 90 };
    tryEstablishTempoReference(clipB);
    globalThis.__result = { afterFirst, bpmAfterSecond: bpm };
  `);
  const r = sb.__result;
  assert.strictEqual(r.afterFirst.bpm, 140, 'il primo clip con sourceBpm deve stabilire subito il bpm di progetto');
  assert.strictEqual(r.afterFirst.tempoReferenceSet, true, 'il flag di riferimento deve accendersi');
  assert.strictEqual(String(r.afterFirst.fieldVal), '140', 'il campo BPM a schermo deve riflettere il nuovo valore');
  assert.strictEqual(r.bpmAfterSecond, 140, 'una volta stabilito il riferimento, un secondo clip non deve piu\' cambiare il bpm');
}

async function testIgnoresNullOrBpmLessClips(){
  const sb = await runWithApp(`
    ac();
    tryEstablishTempoReference(null);
    tryEstablishTempoReference({});
    globalThis.__result = { bpm, tempoReferenceSet };
  `);
  const r = sb.__result;
  assert.strictEqual(r.tempoReferenceSet, false, 'un clip nullo o senza sourceBpm non deve mai stabilire il riferimento');
  assert.strictEqual(r.bpm, 120, 'il bpm di default (120) non deve essere toccato');
}

async function testSchedulingLoopEstablishesReference(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'Loop A', mode:'loop', sourceBpm:100, trimStart:0, trimEnd:null };
    scheduleClip(0,0, now());
    globalThis.__result = { bpm, tempoReferenceSet, fieldVal: document.getElementById('bpm').value };
  `);
  const r = sb.__result;
  assert.strictEqual(r.bpm, 100, 'schedulare un loop con sourceBpm noto deve stabilire il bpm di progetto');
  assert.strictEqual(r.tempoReferenceSet, true);
  assert.strictEqual(String(r.fieldVal), '100');
}

async function testSecondLoopAdaptsWithoutChangingReference(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'A', mode:'loop', sourceBpm:100, trimStart:0, trimEnd:null };
    clips[0][1] = { buffer:{duration:2}, name:'B', mode:'loop', sourceBpm:80, trimStart:0, trimEnd:null };
    scheduleClip(0,0, now());
    const bpmAfterFirst = bpm;
    scheduleClip(0,1, now());
    globalThis.__result = { bpmAfterFirst, bpmAfterSecond: bpm, rateB: rateFor(clips[0][1]) };
  `);
  const r = sb.__result;
  assert.strictEqual(r.bpmAfterFirst, 100);
  assert.strictEqual(r.bpmAfterSecond, 100, 'il secondo loop non deve cambiare un riferimento gia\' stabilito');
  assert.ok(Math.abs(r.rateB - 100/80) < 1e-9, 'il secondo loop deve comunque adattare la propria velocita\' al bpm corrente (100/80)');
}

async function testStopAllAndResyncAllResetReference(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'A', mode:'loop', sourceBpm:100, trimStart:0, trimEnd:null };
    scheduleClip(0,0, now());
    const afterSchedule = tempoReferenceSet;
    stopAll();
    const afterStopAll = tempoReferenceSet;
    playing = true; startTime = now();
    trackState[0].playingRow = 0;
    resyncAll();
    globalThis.__result = { afterSchedule, afterStopAll, afterResyncReestablished: tempoReferenceSet };
  `);
  const r = sb.__result;
  assert.strictEqual(r.afterSchedule, true);
  assert.strictEqual(r.afterStopAll, false, 'stopAll deve sciogliere il riferimento');
  assert.strictEqual(r.afterResyncReestablished, true, 'resyncAll scioglie il riferimento ma rischedula subito i loop in play, che lo ristabiliscono');
}

async function testSceneLaunchEstablishesFromLeftmostWithSourceBpm(){
  const sb = await runWithApp(`
    ac();
    clips[2][0] = { buffer:{duration:2}, name:'NoBpm', mode:'loop', trimStart:0, trimEnd:null };
    clips[2][1] = { buffer:{duration:2}, name:'First', mode:'loop', sourceBpm:110, trimStart:0, trimEnd:null };
    clips[2][2] = { buffer:{duration:2}, name:'Second', mode:'loop', sourceBpm:95, trimStart:0, trimEnd:null };
    launchScene(2);
    globalThis.__result = { bpm, tempoReferenceSet };
  `);
  const r = sb.__result;
  assert.strictEqual(r.bpm, 110, 'nel lancio scena vince la prima colonna (da sinistra) con sourceBpm noto tra quelle lanciate');
  assert.strictEqual(r.tempoReferenceSet, true);
}

async function testOneShotAndGateNeverEstablishReference(){
  const sb = await runWithApp(`
    ac();
    clips[3][3] = { buffer:{duration:1}, name:'OS', mode:'oneshot', sourceBpm:150, trimStart:0, trimEnd:null };
    playOnce(3,3);
    const afterOneShot = { bpm, tempoReferenceSet };
    clips[3][4] = { buffer:{duration:1}, name:'Gate', mode:'gate', sourceBpm:160, trimStart:0, trimEnd:null };
    startGate(3,4);
    globalThis.__result = { afterOneShot, afterGate: { bpm, tempoReferenceSet } };
  `);
  const r = sb.__result;
  assert.strictEqual(r.afterOneShot.tempoReferenceSet, false, 'un one-shot non deve mai stabilire il riferimento');
  assert.strictEqual(r.afterOneShot.bpm, 120);
  assert.strictEqual(r.afterGate.tempoReferenceSet, false, 'un gate non deve mai stabilire il riferimento');
  assert.strictEqual(r.afterGate.bpm, 120);
}

async function testClipRateIgnoresSyncBpmFlag(){
  const sb = await runWithApp(`
    ac();
    syncBpm = false;
    bpm = 140;
    const clip = { sourceBpm: 70 };
    globalThis.__result = { rate: clipRate(clip) };
  `);
  assert.ok(Math.abs(sb.__result.rate - 2) < 1e-9, 'clipRate deve applicare il rapporto BPM a prescindere dal vecchio flag syncBpm');
}

(async () => {
  const tests = [
    ['stabilisce il riferimento una volta, poi lo ignora', testEstablishesReferenceOnceThenIgnoresLater],
    ['ignora clip nulli o senza sourceBpm', testIgnoresNullOrBpmLessClips],
    ['schedulare un loop con sourceBpm stabilisce il riferimento', testSchedulingLoopEstablishesReference],
    ['un secondo loop si adatta senza cambiare il riferimento', testSecondLoopAdaptsWithoutChangingReference],
    ['stopAll/resyncAll azzerano e poi rischedulano il riferimento', testStopAllAndResyncAllResetReference],
    ['lancio scena: vince la prima colonna da sinistra con sourceBpm', testSceneLaunchEstablishesFromLeftmostWithSourceBpm],
    ['one-shot e gate non stabiliscono mai il riferimento', testOneShotAndGateNeverEstablishReference],
    ['clipRate ignora il vecchio flag syncBpm', testClipRateIgnoresSyncBpmFlag],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui i test e verifica che falliscano (RED)**

Run (da dentro la cartella scratchpad): `node test_bpm_auto_reference.js`

Expected: tutti e 8 i test FALLISCONO — `tryEstablishTempoReference`/`tempoReferenceSet` non esistono ancora (`ReferenceError`), e `testClipRateIgnoresSyncBpmFlag` fallisce perche' `clipRate` dipende ancora da `syncBpm`.

- [ ] **Step 3: Aggiungi lo stato `tempoReferenceSet`**

In `_sorgente/launchpad-studio.html`, riga 626, subito dopo la riga esistente:

```js
let bpm=120, bars=4, quantMode='off', phraseBars=4, syncBpm=false;
```

aggiungi:

```js
let tempoReferenceSet=false;   // vero se il BPM di progetto e' gia' "agganciato" a un suono dall'ultimo stopAll/resyncAll
```

- [ ] **Step 4: Rimuovi la dipendenza da `syncBpm` in `clipRate` e aggiungi `tryEstablishTempoReference`**

In `_sorgente/launchpad-studio.html`, riga 1197, sostituisci:

```js
function clipRate(clip){ return (syncBpm && clip && clip.sourceBpm)? bpm/clip.sourceBpm : 1; }
```

con:

```js
function clipRate(clip){ return (clip && clip.sourceBpm)? bpm/clip.sourceBpm : 1; }
```

Subito dopo la riga 1199 (`function rateFor(clip){ return clipRate(clip)*Math.pow(2, ((clip&&clip.pitch)||0)/12); }`), prima di `function gainFor(clip){...}`, aggiungi:

```js
// Il primo Loop che parte (dopo uno Stop tutto o un Re-sync) stabilisce da solo il BPM di progetto;
// da li' in poi ogni clip con un sourceBpm noto si adatta automaticamente (vedi clipRate). Un solo
// punto di chiamata: l'inizio di scheduleClip, attraversato sia dalla pressione diretta di un pad
// Loop sia dal lancio scena — nessun altro hook necessario.
function tryEstablishTempoReference(clip){
  if(tempoReferenceSet || !clip || !clip.sourceBpm) return;
  bpm=clip.sourceBpm;
  document.getElementById('bpm').value=bpm;
  document.getElementById('bpmVal').textContent=bpm;
  tempoReferenceSet=true;
  applyRates();
}
```

- [ ] **Step 5: Chiama `tryEstablishTempoReference` dentro `scheduleClip`**

In `_sorgente/launchpad-studio.html`, riga 1473-1474, sostituisci:

```js
function scheduleClip(r,c,when){
  const ts=trackState[c], clip=clips[r][c]; const F=0.006;
```

con:

```js
function scheduleClip(r,c,when){
  const ts=trackState[c], clip=clips[r][c]; const F=0.006;
  tryEstablishTempoReference(clip);
```

(deve stare prima di qualunque uso di `rateFor(clip)` piu' sotto nella stessa funzione, cosi' il nuovo `bpm` e' gia' in vigore quando la velocita' di riproduzione viene calcolata).

- [ ] **Step 6: Resetta il riferimento in `stopAll` e `resyncAll`**

In `_sorgente/launchpad-studio.html`, riga 1235-1236, sostituisci:

```js
function stopAll(){
  playing=false; playBtn.textContent='▶ Play'; playBtn.classList.add('primary');
```

con:

```js
function stopAll(){
  playing=false; tempoReferenceSet=false; playBtn.textContent='▶ Play'; playBtn.classList.add('primary');
```

Riga 1261-1263, sostituisci:

```js
function resyncAll(){
  if(!playing) return;
  const when=now()+0.03; startTime=when; nextClick=when; nextStepTime=when; stepCounter=0; lastBeat=-1;
```

con:

```js
function resyncAll(){
  if(!playing) return;
  tempoReferenceSet=false;
  const when=now()+0.03; startTime=when; nextClick=when; nextStepTime=when; stepCounter=0; lastBeat=-1;
```

- [ ] **Step 7: Nascondi il checkbox "Sync BPM"**

In `_sorgente/launchpad-studio.html`, riga 149, sostituisci:

```html
<label style="font-size:12px"><input type="checkbox" id="syncBpm"> Sync BPM</label>
```

con:

```html
<label style="font-size:12px;display:none"><input type="checkbox" id="syncBpm"> Sync BPM</label>
```

- [ ] **Step 8: Esegui i test e verifica che passino (GREEN)**

Run: `node test_bpm_auto_reference.js`
Expected: tutti e 8 i test PASS.

- [ ] **Step 9: Rebuild e verifica di regressione**

Da dentro `_sorgente/`: `python assemble.py`

Esegui anche l'intera suite di test esistente nella cartella scratchpad (tutti i `test_*.js`) per assicurarti che nessuna regressione sia stata introdotta, in particolare `test_live_trim.js` e `test_genre_overrides.js` (toccano `rateFor`/`scheduleClip` indirettamente).

- [ ] **Step 10: Verifica in Chrome vero**

Con Playwright (`playwright-core`, `executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'`), apri `Launchpad Studio.html` e verifica:
1. Il checkbox "Sync BPM" non e' piu' visibile nel pannello Transport.
2. Carica un genere (es. "▶ Carica genere"), premi un pad Loop: il campo BPM a schermo si aggiorna al `sourceBpm` di quel pad.
3. Premi un secondo pad Loop di un'altra colonna: il campo BPM NON cambia piu', ma il suono suona a velocita' adattata (nessun errore in console).
4. Premi "⏹ Stop tutto" poi un pad Loop diverso: il campo BPM si aggancia di nuovo al `sourceBpm` di QUESTO pad (non resta quello di prima).
5. Nessun errore in console durante l'intera sequenza.

- [ ] **Step 11: Commit**

```bash
git add "_sorgente/launchpad-studio.html"
git commit -m "$(cat <<'EOF'
BPM automatico: il primo loop che parte stabilisce il tempo di progetto

scheduleClip aggancia bpm al sourceBpm del primo clip Loop schedulato
dopo uno stopAll/resyncAll; clipRate applica il rapporto sempre,
niente piu' dipendenza dal checkbox Sync BPM (nascosto, non rimosso).
EOF
)"
```

---

## Task 2: Campo "BPM di origine" per pad + rilevamento assistito + persistenza per genere

**Files:**
- Modify: `_sorgente/launchpad-studio.html`
- Modify: `_sorgente/genre_ui.js`
- Test: `<scratchpad>/test_bpm_source_field.js` (nuovo)

**Interfaces:**
- Consumes: `activeGrid()`, `selected`, `selectPad(r,c)` (riga 1080), `saveGenreOverride(genre,r,c,data)` (gia' esistente), `genreOverrides` (mappa globale gia' esistente), `pushUndo()`, `tryEstablishTempoReference`/`tempoReferenceSet`/`clipRate` (dal Task 1, non modificati oltre).
- Produces: `function detectBpm(buffer)` (nuova, nessun altro task la usa), campo DOM `#clipSourceBpm` e bottone `#detectBpmBtn` (nuovi, usati solo da questo task).

- [ ] **Step 1: Scrivi i test (RED)**

Crea `<scratchpad>/test_bpm_source_field.js` con questo contenuto:

```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const { runWithApp } = require('./harness.js');
const GENRE_UI_SRC = fs.readFileSync('D:/MUSIC/Launchpad Studio/_sorgente/genre_ui.js', 'utf8');

const FAKE_GENRES = { G1: { bpm:120, clips: [
  { r:0,c:0, name:'Kick_01', mime:'audio/webm', data:'AAAA', mode:'loop', trimStart:0, trimEnd:null },
] }, G2: { bpm:100, clips: [
  { r:0,c:0, name:'Kick_09', mime:'audio/webm', data:'AAAA', mode:'loop', trimStart:0, trimEnd:null },
] } };

async function runGenre(code){
  return runWithApp(GENRE_UI_SRC + '\n' + code, { inject: { GENRES: FAKE_GENRES } });
}

async function testDetectBpmFindsKnownTempo(){
  const sb = await runWithApp(`
    const sr=8000, periodSec=0.5, totalSec=4;
    const n=Math.round(sr*totalSec);
    const data=new Float32Array(n);
    const periodSamples=Math.round(sr*periodSec);
    for(let i=0;i<n;i+=periodSamples){ for(let j=i;j<Math.min(n,i+40);j++) data[j]=1; }
    const buffer={ sampleRate:sr, getChannelData:()=>data };
    globalThis.__result = { bpm: detectBpm(buffer) };
  `);
  const est = sb.__result.bpm;
  assert.ok(est!=null, 'deve restituire una stima per un segnale periodico chiaro');
  assert.ok(Math.abs(est-120)<=5, 'stima attesa vicino a 120 BPM (periodo 0.5s), ottenuto '+est);
}

async function testDetectBpmOnNoiseDoesNotThrow(){
  const sb = await runWithApp(`
    const sr=8000, n=8000;
    const data=new Float32Array(n);
    for(let i=0;i<n;i++){ data[i]=Math.sin(i*12.9898)*0.5; }
    const buffer={ sampleRate:sr, getChannelData:()=>data };
    let threw=false, result=null;
    try{ result=detectBpm(buffer); }catch(e){ threw=true; }
    globalThis.__result = { threw, resultType: typeof result };
  `);
  assert.strictEqual(sb.__result.threw, false, 'detectBpm non deve mai lanciare eccezioni, anche su contenuto non ritmico');
}

async function testManualFieldMakesClipEligibleForReference(){
  const sb = await runWithApp(`
    ac();
    clips[5][5] = { buffer:{duration:2}, name:'Dragged', mode:'loop', trimStart:0, trimEnd:null };
    selected = { r:5, c:5 };
    document.getElementById('clipSourceBpm').value = '135';
    document.getElementById('clipSourceBpm').oninput({ target:{ value:'135' } });
    const sourceBpmAfterEdit = clips[5][5].sourceBpm;
    scheduleClip(5,5, now());
    globalThis.__result = { sourceBpmAfterEdit, bpmAfterSchedule: bpm, referenceSet: tempoReferenceSet };
  `);
  const r = sb.__result;
  assert.strictEqual(r.sourceBpmAfterEdit, 135, 'impostare il campo deve scrivere subito clip.sourceBpm');
  assert.strictEqual(r.bpmAfterSchedule, 135, 'un pad senza sourceBpm pregresso, una volta impostato a mano, deve poter diventare riferimento');
  assert.strictEqual(r.referenceSet, true);
}

async function testSelectPadRefreshesSourceBpmField(){
  const sb = await runWithApp(`
    ac();
    clips[6][6] = { buffer:{duration:2}, name:'Known', mode:'loop', sourceBpm:128, trimStart:0, trimEnd:null };
    clips[6][7] = { buffer:{duration:2}, name:'Unknown', mode:'loop', trimStart:0, trimEnd:null };
    selectPad(6,6);
    const known = document.getElementById('clipSourceBpm').value;
    selectPad(6,7);
    const unknown = document.getElementById('clipSourceBpm').value;
    globalThis.__result = { known, unknown };
  `);
  const r = sb.__result;
  assert.strictEqual(String(r.known), '128', 'selectPad deve mostrare il sourceBpm del pad');
  assert.strictEqual(String(r.unknown), '', 'un pad senza sourceBpm deve mostrare il campo vuoto');
}

async function testDetectBpmBtnFillsFieldAndClip(){
  const sb = await runWithApp(`
    ac();
    const sr=8000, periodSamples=Math.round(sr*0.5), n=sr*4;
    const data=new Float32Array(n);
    for(let i=0;i<n;i+=periodSamples){ for(let j=i;j<Math.min(n,i+40);j++) data[j]=1; }
    clips[7][7] = { buffer:{duration:4, sampleRate:sr, getChannelData:()=>data}, name:'Beat', mode:'loop', trimStart:0, trimEnd:null };
    selected = { r:7, c:7 };
    document.getElementById('detectBpmBtn').onclick();
    globalThis.__result = { fieldVal: document.getElementById('clipSourceBpm').value, clipSourceBpm: clips[7][7].sourceBpm };
  `);
  const r = sb.__result;
  assert.ok(r.clipSourceBpm!=null, 'il tasto Rileva BPM deve impostare subito clip.sourceBpm');
  assert.strictEqual(String(r.fieldVal), String(r.clipSourceBpm), 'il campo a schermo deve mostrare lo stesso valore rilevato');
}

async function testSaveModBtnPersistsSourceBpmAcrossReload(){
  const sb = await runGenre(`
    ac();
    await loadGenre('G1');
    selected = { r:0, c:0 };
    clips[0][0].sourceBpm = 133;
    await document.getElementById('saveModBtn').onclick();
    await loadGenre('G2');
    await loadGenre('G1');
    globalThis.__result = { sourceBpm: clips[0][0].sourceBpm };
  `);
  assert.strictEqual(sb.__result.sourceBpm, 133, 'il BPM di origine impostato a mano deve sopravvivere a un ricaricamento del genere, come taglio/pitch/reverse');
}

(async () => {
  const tests = [
    ['detectBpm trova un tempo noto su un segnale periodico', testDetectBpmFindsKnownTempo],
    ['detectBpm non lancia eccezioni su rumore', testDetectBpmOnNoiseDoesNotThrow],
    ['il campo manuale rende un pad idoneo come riferimento', testManualFieldMakesClipEligibleForReference],
    ['selectPad aggiorna il campo BPM di origine', testSelectPadRefreshesSourceBpmField],
    ['il tasto Rileva BPM riempie campo e clip', testDetectBpmBtnFillsFieldAndClip],
    ['Salva modifica persiste il BPM di origine per genere', testSaveModBtnPersistsSourceBpmAcrossReload],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui i test e verifica che falliscano (RED)**

Run: `node test_bpm_source_field.js`
Expected: tutti e 6 i test FALLISCONO — `detectBpm` non esiste, `#clipSourceBpm`/`#detectBpmBtn` non esistono nel DOM, `selectPad` non li aggiorna, `saveModBtn` non salva `sourceBpm`.

- [ ] **Step 3: Aggiungi il campo e il bottone nell'HTML**

In `_sorgente/launchpad-studio.html`, subito dopo la riga 189 (`</div>` che chiude la riga con Gain/Pitch/Choke) e prima della riga 190 (`<div class="row" style="font-size:12px">` con Copia/Incolla impostazioni), inserisci una nuova riga:

```html
      <div class="row" style="font-size:12px">
        <label>BPM di origine</label><input type="number" id="clipSourceBpm" min="40" max="240" style="width:64px">
        <button class="act" id="detectBpmBtn" title="Stima il BPM del pad selezionato analizzando la forma d'onda (indicativo, verificalo/correggilo nel campo)">🔍 Rileva BPM</button>
      </div>
```

- [ ] **Step 4: Aggiungi `detectBpm(buffer)`**

In `_sorgente/launchpad-studio.html`, subito dopo la funzione `tryEstablishTempoReference` aggiunta nel Task 1 (dopo la sua riga di chiusura `}`, prima di `function gainFor(clip){...}`), aggiungi:

```js
// Stima "best effort" del tempo di un AudioBuffer: inviluppo (RMS a finestre di ~10ms) -> autocorrelazione
// sull'intervallo di lag corrispondente a 60-200 BPM -> il lag col picco piu' alto e' il periodo del beat.
// Funziona bene su loop ritmici con transienti chiari, male su contenuto non percussivo (voce, ambient):
// e' un suggerimento di partenza, non una certezza — l'utente lo conferma o corregge nel campo.
function detectBpm(buffer){
  const sr=buffer.sampleRate, data=buffer.getChannelData(0);
  const hop=Math.round(sr*0.01);
  const env=[]; for(let i=0;i<data.length;i+=hop){ let s=0; for(let j=i;j<Math.min(i+hop,data.length);j++) s+=data[j]*data[j]; env.push(Math.sqrt(s/hop)); }
  const envRate=sr/hop;
  const minLag=Math.round(envRate*60/200), maxLag=Math.round(envRate*60/60);
  let bestLag=-1, bestScore=-Infinity;
  for(let lag=minLag; lag<=maxLag && lag<env.length; lag++){
    let score=0; for(let i=0;i<env.length-lag;i++) score+=env[i]*env[i+lag];
    if(score>bestScore){ bestScore=score; bestLag=lag; }
  }
  if(bestLag<=0) return null;
  return Math.round(60/(bestLag/envRate));
}
```

- [ ] **Step 5: Aggiorna `selectPad` per mostrare il BPM di origine**

In `_sorgente/launchpad-studio.html`, riga 1084-1085, sostituisci:

```js
  const cpi=document.getElementById('clipPitch'); if(cpi){ cpi.value=(cl&&cl.pitch)||0; document.getElementById('clipPitchVal').textContent=cpi.value; }
  const cch=document.getElementById('clipChoke'); if(cch) cch.value=(cl&&cl.choke)||0;
```

con:

```js
  const cpi=document.getElementById('clipPitch'); if(cpi){ cpi.value=(cl&&cl.pitch)||0; document.getElementById('clipPitchVal').textContent=cpi.value; }
  const csb=document.getElementById('clipSourceBpm'); if(csb) csb.value=(cl&&cl.sourceBpm)||'';
  const cch=document.getElementById('clipChoke'); if(cch) cch.value=(cl&&cl.choke)||0;
```

- [ ] **Step 6: Aggiungi gli handler del campo e del bottone**

In `_sorgente/launchpad-studio.html`, subito dopo la riga con l'handler `clipPitch.addEventListener('pointerdown',...)` (riga 1186: `document.getElementById('clipPitch').addEventListener('pointerdown',()=>pushUndo());`), aggiungi:

```js
document.getElementById('clipSourceBpm').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  const v=+e.target.value; cl.sourceBpm=(e.target.value===''||!v)?null:v; };
document.getElementById('clipSourceBpm').addEventListener('pointerdown',()=>pushUndo());
document.getElementById('detectBpmBtn').onclick=()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl||!cl.buffer) return;
  const est=detectBpm(cl.buffer); if(est==null) return;
  pushUndo();
  cl.sourceBpm=est;
  document.getElementById('clipSourceBpm').value=est;
};
```

- [ ] **Step 7: Estendi "Salva modifica" e il caricamento genere per portare `sourceBpm`**

In `_sorgente/launchpad-studio.html`, riga 1072-1078, sostituisci:

```js
document.getElementById('saveModBtn').onclick=async ()=>{
  const genre=loadedGenreKeyByBank[activeBank]; if(!genre) return;
  const {r,c}=selected; const cl=clips[r][c]; if(!cl) return;
  await saveGenreOverride(genre,r,c,{trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,reversed:!!cl.reversed,pitch:cl.pitch||0});
  const btn=document.getElementById('saveModBtn'); const orig=btn.textContent;
  btn.textContent='✓ Salvato'; setTimeout(()=>{ btn.textContent=orig; },1200);
};
```

con:

```js
document.getElementById('saveModBtn').onclick=async ()=>{
  const genre=loadedGenreKeyByBank[activeBank]; if(!genre) return;
  const {r,c}=selected; const cl=clips[r][c]; if(!cl) return;
  await saveGenreOverride(genre,r,c,{trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,reversed:!!cl.reversed,pitch:cl.pitch||0,sourceBpm:cl.sourceBpm||null});
  const btn=document.getElementById('saveModBtn'); const orig=btn.textContent;
  btn.textContent='✓ Salvato'; setTimeout(()=>{ btn.textContent=orig; },1200);
};
```

In `_sorgente/genre_ui.js`, righe 183-189, sostituisci:

```js
      if(genreKey){
        const ovr=genreOverrides[genreKey+'|'+cl.r+'|'+cl.c];
        if(ovr){
          nc.trimStart=ovr.trimStart||0; nc.trimEnd=ovr.trimEnd!=null?ovr.trimEnd:null; nc.pitch=ovr.pitch||0;
          if(ovr.reversed){ nc.origBuffer=audio; nc.revBuffer=reversedBuffer(audio); nc.buffer=nc.revBuffer; nc.reversed=true; }
        }
      }
```

con:

```js
      if(genreKey){
        const ovr=genreOverrides[genreKey+'|'+cl.r+'|'+cl.c];
        if(ovr){
          nc.trimStart=ovr.trimStart||0; nc.trimEnd=ovr.trimEnd!=null?ovr.trimEnd:null; nc.pitch=ovr.pitch||0;
          if(ovr.sourceBpm!=null) nc.sourceBpm=ovr.sourceBpm;
          if(ovr.reversed){ nc.origBuffer=audio; nc.revBuffer=reversedBuffer(audio); nc.buffer=nc.revBuffer; nc.reversed=true; }
        }
      }
```

- [ ] **Step 8: Esegui i test e verifica che passino (GREEN)**

Run: `node test_bpm_source_field.js`
Expected: tutti e 6 i test PASS.

- [ ] **Step 9: Rebuild e verifica di regressione**

Da dentro `_sorgente/`: `python assemble.py`

Esegui l'intera suite di test nella cartella scratchpad (`test_bpm_auto_reference.js` del Task 1, `test_genre_overrides.js`, `test_live_trim.js`, e tutti gli altri `test_*.js` presenti) per assicurarti che nessuna regressione sia stata introdotta.

- [ ] **Step 10: Verifica in Chrome vero**

Con Playwright, apri `Launchpad Studio.html` e verifica:
1. Seleziona un pad senza suono caricato: il campo "BPM di origine" e' vuoto.
2. Carica un genere, seleziona un pad: il campo mostra il BPM di quel genere.
3. Trascina un file audio qualunque su un pad vuoto (o registra dal microfono): il campo "BPM di origine" e' vuoto; scrivi un valore a mano, verifica che resti dopo aver riselezionato un altro pad e poi tornato a questo.
4. Su un pad con suono caricato, premi "🔍 Rileva BPM": il campo si riempie con un numero plausibile, nessun errore in console.
5. Modifica il BPM di origine di un pad caricato da genere, premi "💾 Salva modifica", ricarica un genere diverso poi ricarica quello originale: il BPM modificato deve essere tornato.

- [ ] **Step 11: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "_sorgente/genre_ui.js"
git commit -m "$(cat <<'EOF'
Campo "BPM di origine" per pad + rilevamento assistito

Permette di impostare/correggere il sourceBpm di qualunque pad (anche
file trascinati a mano, mai coperti da un genere) cosi' possa
partecipare all'aggancio automatico del tempo; il tasto "Rileva BPM"
propone una stima via autocorrelazione dell'inviluppo del segnale.
Il valore, come taglio/pitch/reverse, si salva per genere con
"Salva modifica".
EOF
)"
```

---

## Verifica finale end-to-end (dopo entrambi i task)

Con Playwright, in Chrome vero:
1. Carica un genere A su un banco, un genere B (BPM diverso) su un altro banco.
2. Premi un pad Loop del banco A: il BPM di progetto si aggancia al BPM del genere A.
3. Premi un pad Loop del banco B: il suono di B suona rallentato/velocizzato per allinearsi al BPM di A (ascolto/verifica `playbackRate` del source via `page.evaluate`), il campo BPM a schermo resta quello di A.
4. Premi "⏹ Stop tutto", poi premi PRIMA un pad Loop del banco B: il BPM di progetto ora si aggancia al BPM di B.
5. Nessun errore in console durante l'intera sequenza.
