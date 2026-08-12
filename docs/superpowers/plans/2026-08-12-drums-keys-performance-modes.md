# Modalità performance Drums/Keys — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dare un ruolo reale ai 4 tasti superiori del Launchpad Mini MK3 (Session/Drums/Keys/User, CC 95-98) aggiungendo due nuove modalità performance — Drums (kit di campioni dedicato, colpi one-shot velocity-sensitive) e Keys (il clip selezionato suonato a intonazioni diverse, layout isomorfo a quarte) — sovrapposte alla griglia normale senza interrompere i loop in corso.

**Architecture:** Nuovo stato globale `perfMode` (`null|'drums'|'keys'`) e griglia indipendente `drumKit` (stessa forma di `clips`). Un helper `activeGrid()` fa sì che editor/trim/copia-incolla/undo riusino il codice esistente puntandolo su `drumKit` invece di `clips` quando serve, senza duplicarlo. Riproduzione: `triggerDrumHit`/`startKeysNote`+`stopKeysNote` sono varianti mirate di `playOnce`/`startGate`+`stopGate` già esistenti (stesso trim/pitch/gain, aggiungono velocity e — per Keys — un offset isomorfo di intonazione).

**Tech Stack:** JavaScript vanilla, Web Audio API, Web MIDI API — stesso stack del resto del file (nessuna nuova dipendenza). Test: harness Node esistente in `C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad\harness.js` (esegue il vero script estratto da `_sorgente/launchpad-studio.html` dentro un DOM/AudioContext finti).

## Global Constraints

- File sorgente canonico da modificare: `D:\MUSIC\Launchpad Studio\_sorgente\launchpad-studio.html` (script applicativo, marker `// ====================== STATO ======================`).
- Dopo OGNI task: rigenerare `D:\MUSIC\Launchpad Studio\Launchpad Studio.html` con `python assemble.py` (da `_sorgente/`, usare `python` non `python3` su Windows), rieseguire l'INTERA suite di test in scratchpad (`for f in test_*.js; do node "$f"; done`), verificare che sorgente e generato producano lo stesso script estratto (byte-identico), poi committare.
- TDD rigoroso: scrivere il test, eseguirlo e vedere il fallimento per il motivo giusto, poi implementare, poi verificare che passi. Non scrivere codice di produzione prima del test corrispondente.
- Non introdurre un concetto di "scala musicale" per Keys (fuori scope, vedi spec §"Fuori scope"): l'offset è sempre `(7-r)*5+c`, fisso.
- Non toccare il comportamento di Up/Down/Left/Right (CC 91-94, restano "ferma colonna").
- `perfMode` non entra MAI in `captureState`/`applyState`/autosave/`.lpstudio` (è stato di sessione transitorio). `drumKit` invece sì, in tutti e quattro.
- Spec di riferimento completa: `docs/superpowers/specs/2026-08-12-drums-keys-performance-modes-design.md`.

---

## Task 1: Stato globale — `perfMode`, `drumKit`, `activeGrid()`, `keysPitchOffset()`

**Files:**
- Modify: `D:\MUSIC\Launchpad Studio\_sorgente\launchpad-studio.html` (dopo la riga `let activeBank=0, clips=banks[0];`, circa riga 507)
- Test: `C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad\test_perfmode_state.js`

**Interfaces:**
- Produce: `perfMode` (let, `null|'drums'|'keys'`), `drumKit` (griglia 8×8, stessa forma di `clips[r][c]`), `activeGrid()` (funzione, nessun argomento, ritorna `drumKit` o `clips`), `keysPitchOffset(r,c)` (funzione, ritorna intero semitoni).

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_state.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testActiveGridSwitchesWithPerfMode(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:1}, name:'BankClip' };
    drumKit[0][0] = { buffer:{duration:1}, name:'KitClip' };
    const beforeName = activeGrid()[0][0].name;
    perfMode = 'drums';
    const afterName = activeGrid()[0][0].name;
    globalThis.__result = { beforeName, afterName };
  `);
  const r = sb.__result;
  assert.strictEqual(r.beforeName, 'BankClip', 'con perfMode=null activeGrid() deve restituire clips');
  assert.strictEqual(r.afterName, 'KitClip', 'con perfMode=drums activeGrid() deve restituire drumKit');
}

async function testKeysPitchOffsetIsomorphic(){
  const sb = await runWithApp(`
    globalThis.__result = {
      topLeft: keysPitchOffset(0,0), topRight: keysPitchOffset(0,7),
      bottomLeft: keysPitchOffset(7,0), bottomRight: keysPitchOffset(7,7),
      oneRowUp: keysPitchOffset(6,0) - keysPitchOffset(7,0),
    };
  `);
  const r = sb.__result;
  assert.strictEqual(r.bottomLeft, 0, 'riga in basso, colonna 0 = offset 0 (intonazione originale)');
  assert.strictEqual(r.bottomRight, 7, 'riga in basso, colonna 7 = +7 semitoni');
  assert.strictEqual(r.topLeft, 35, 'riga in alto, colonna 0 = +35 semitoni (7 righe * 5)');
  assert.strictEqual(r.topRight, 42, 'riga in alto, colonna 7 = +42 semitoni');
  assert.strictEqual(r.oneRowUp, 5, 'ogni riga verso l\'alto aggiunge una quarta (5 semitoni)');
}

async function testDrumKitStartsEmpty(){
  const sb = await runWithApp(`
    let allNull = true;
    for(let r=0;r<8;r++)for(let c=0;c<8;c++) if(drumKit[r][c]!==null) allNull=false;
    globalThis.__result = { allNull, perfModeDefault: perfMode };
  `);
  assert.strictEqual(sb.__result.allNull, true, 'drumKit deve partire vuoto (64 celle null)');
  assert.strictEqual(sb.__result.perfModeDefault, null, 'perfMode deve partire a null');
}

(async () => {
  const tests = [
    ['activeGrid() segue perfMode', testActiveGridSwitchesWithPerfMode],
    ['keysPitchOffset e\' isomorfo a quarte', testKeysPitchOffsetIsomorphic],
    ['drumKit/perfMode partono vuoti', testDrumKitStartsEmpty],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui e verifica che fallisca**

```
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
node test_perfmode_state.js
```
Atteso: FAIL — `perfMode`/`drumKit`/`activeGrid`/`keysPitchOffset` non sono definiti (ReferenceError).

- [ ] **Step 3: Implementa nel sorgente**

In `_sorgente/launchpad-studio.html`, subito dopo `let activeBank=0, clips=banks[0];` (circa riga 507), aggiungi:
```js
let perfMode=null;   // null | 'drums' | 'keys' — overlay di performance sui 4 tasti superiori (Session/Drums/Keys/User)
let drumKit=new Array(ROWS).fill(null).map(()=>new Array(COLS).fill(null));   // griglia 8x8 indipendente dai banchi, per la modalita' Drums
function activeGrid(){ return perfMode==='drums' ? drumKit : clips; }
function keysPitchOffset(r,c){ return (7-r)*5 + c; }   // layout isomorfo a quarte: riga 0 (alto) = piu' acuta
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_state.js
```
Atteso: `PASS - activeGrid() segue perfMode`, `PASS - keysPitchOffset e' isomorfo a quarte`, `PASS - drumKit/perfMode partono vuoti`.

- [ ] **Step 5: Rebuild e regressione**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```
Atteso: nessuna riga `FAIL:` stampata (tutti i test, vecchi e nuovo, passano).

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html" "Launchpad Studio.html" 2>/dev/null; git add "_sorgente/launchpad-studio.html"
git commit -m "Aggiunge lo stato base per le modalita' performance Drums/Keys (perfMode, drumKit, activeGrid, keysPitchOffset)"
```
(nota: `Launchpad Studio.html` è gitignored, l'`add` su quel path non aggiunge nulla — va bene così, si rigenera con `assemble.py`).

---

## Task 2: Tasti superiori — Session/Drums/Keys/User in `onMidiMessage`

**Files:**
- Modify: `_sorgente/launchpad-studio.html`, funzione `onMidiMessage` (circa righe 702-718)
- Test: `scratchpad/test_perfmode_topkeys.js`

**Interfaces:**
- Consuma: `perfMode` (Task 1), `stopAll()`, `resyncAll()` (già esistenti).
- Produce: `exitPerfMode()` (nessun argomento, side-effect: `perfMode=null` + chiama `onPerfModeChanged()`), `onPerfModeChanged()` (nessun argomento; per ora, in questo task, è uno STUB che fa solo `renderAll(); refreshAllLeds();` — verrà esteso nei Task 6/7 con LED/UI dedicati, e in questo task NON deve ancora chiamare funzioni non esistenti).

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_topkeys.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testDrumsTogglesPerfMode(){
  const sb = await runWithApp(`
    ac();
    const before = perfMode;
    onMidiMessage({ data: [0xB0, 96, 127] });
    const afterOn = perfMode;
    onMidiMessage({ data: [0xB0, 96, 127] });
    const afterOff = perfMode;
    globalThis.__result = { before, afterOn, afterOff };
  `);
  const r = sb.__result;
  assert.strictEqual(r.before, null);
  assert.strictEqual(r.afterOn, 'drums', 'premere Drums (nota 96) deve attivare perfMode=drums');
  assert.strictEqual(r.afterOff, null, 'premerlo di nuovo deve disattivarlo');
}

async function testKeysTogglesPerfMode(){
  const sb = await runWithApp(`
    ac();
    onMidiMessage({ data: [0xB0, 97, 127] });
    const afterOn = perfMode;
    onMidiMessage({ data: [0xB0, 97, 127] });
    const afterOff = perfMode;
    globalThis.__result = { afterOn, afterOff };
  `);
  const r = sb.__result;
  assert.strictEqual(r.afterOn, 'keys', 'premere Keys (nota 97) deve attivare perfMode=keys');
  assert.strictEqual(r.afterOff, null);
}

async function testSessionExitsPerfModeOrStopsAll(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:1}, name:'X', mode:'loop' };
    triggerDown(0,0);
    await new Promise(r=>setTimeout(r,60));
    const wasPlaying = playing;
    onMidiMessage({ data: [0xB0, 95, 127] });   // Session, perfMode=null: deve fermare tutto
    const playingAfterStop = playing;
    onMidiMessage({ data: [0xB0, 96, 127] });   // entra in Drums
    const perfModeBeforeSession = perfMode;
    onMidiMessage({ data: [0xB0, 95, 127] });   // Session, perfMode!=null: deve solo uscire
    const perfModeAfterSession = perfMode;
    globalThis.__result = { wasPlaying, playingAfterStop, perfModeBeforeSession, perfModeAfterSession };
  `);
  const r = sb.__result;
  assert.strictEqual(r.wasPlaying, true);
  assert.strictEqual(r.playingAfterStop, false, 'Session a riposo (perfMode=null) deve fermare tutto');
  assert.strictEqual(r.perfModeBeforeSession, 'drums');
  assert.strictEqual(r.perfModeAfterSession, null, 'Session con overlay attivo deve solo uscire dall\'overlay');
}

async function testUserTriggersResync(){
  const sb = await runWithApp(`
    ac();
    let called = false;
    resyncAll = () => { called = true; };
    onMidiMessage({ data: [0xB0, 98, 127] });
    globalThis.__result = called;
  `);
  assert.strictEqual(sb.__result, true, 'User (nota 98) deve richiamare resyncAll()');
}

(async () => {
  const tests = [
    ['Drums (96) attiva/disattiva perfMode', testDrumsTogglesPerfMode],
    ['Keys (97) attiva/disattiva perfMode', testKeysTogglesPerfMode],
    ['Session (95) ferma tutto o esce dall\'overlay', testSessionExitsPerfModeOrStopsAll],
    ['User (98) fa resync', testUserTriggersResync],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_topkeys.js
```
Atteso: FAIL su tutti e 4 — nota 96/97/98 non fanno ancora nulla di specifico (finiscono nel generico `stopTrackClip(d1-91,true)`), nota 95 anche.

- [ ] **Step 3: Implementa nel sorgente**

In `_sorgente/launchpad-studio.html`, sostituisci la riga (circa 714):
```js
  if((type===0x90||type===0xB0)&&d2>0&&d1>=91&&d1<=98){ stopTrackClip(d1-91,true); return; }
```
con:
```js
  if((type===0x90||type===0xB0)&&d2>0&&d1>=91&&d1<=94){ stopTrackClip(d1-91,true); return; }
  if((type===0x90||type===0xB0)&&d2>0&&d1===95){ if(perfMode!==null){ exitPerfMode(); } else { stopAll(); } return; }
  if((type===0x90||type===0xB0)&&d2>0&&d1===96){ perfMode=(perfMode==='drums')?null:'drums'; onPerfModeChanged(); return; }
  if((type===0x90||type===0xB0)&&d2>0&&d1===97){ perfMode=(perfMode==='keys')?null:'keys'; onPerfModeChanged(); return; }
  if((type===0x90||type===0xB0)&&d2>0&&d1===98){ resyncAll(); return; }
```
Subito dopo la fine della funzione `onMidiMessage` (dopo la sua chiusura `}`), aggiungi:
```js
function exitPerfMode(){ perfMode=null; onPerfModeChanged(); }
function onPerfModeChanged(){ renderAll(); refreshAllLeds(); }
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_topkeys.js
```
Atteso: tutti e 4 PASS.

- [ ] **Step 5: Rebuild e regressione**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```
Verifica in particolare `test_bank_midi.js` (nota 89/19/39 devono lanciare ancora scene, invariato) e `test_scene_cc.js` — nessun impatto atteso, ma vanno riverificati perché `onMidiMessage` è cambiato.

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "Session/Drums/Keys/User (CC 95-98) attivano/disattivano le modalita' performance"
```

---

## Task 3: Modalità Drums — colpi one-shot velocity-sensitive dal kit

**Files:**
- Modify: `_sorgente/launchpad-studio.html`, vicino a `playOnce` (circa riga 1106) per la nuova funzione; dentro `onMidiMessage` per il routing della griglia.
- Test: `scratchpad/test_perfmode_drums.js`

**Interfaces:**
- Consuma: `drumKit`, `perfMode`, `trimBounds(clip)`, `rateFor(clip)`, `gainFor(clip)`, `applyChoke(clip,src,gainNode,t,ctx)`, `now()`, `ac()`, `trackGains[c]`, `oneShots` (array, già esistenti).
- Produce: `triggerDrumHit(r,c,velocity)` — `velocity` è il byte MIDI 0-127 (secondo parametro di Note On).

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_drums.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

function makeClip(){ return { buffer:{duration:1,numberOfChannels:1,length:44100,sampleRate:44100,getChannelData:()=>new Float32Array(44100)}, name:'Kick', mode:'loop', gain:1 }; }

async function testDrumsModePlaysKitNotBankClip(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    drumKit[0][0] = ${JSON.stringify({name:'KitKick',gain:1}).replace('}',',buffer:{duration:0.5}}')};
    clips[0][0] = { buffer:{duration:1}, name:'BankLoop', mode:'loop' };
    onMidiMessage({ data:[0x90, 81, 100] });   // nota 81 = pad (0,0): padToNote(0,0)=11+(7-0)*10+0=81
    globalThis.__result = { oneShotCount: oneShots.length, playingRowOnBank: trackState[0].playingRow };
  `);
  const r = sb.__result;
  assert.strictEqual(r.oneShotCount, 1, 'un colpo Drums deve creare una voce one-shot');
  assert.strictEqual(r.playingRowOnBank, null, 'non deve toccare trackState del banco normale (nessun loop-toggle)');
}

async function testDrumsModeVelocityScalesGain(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    drumKit[0][0] = { buffer:{duration:1}, name:'Kick', gain:1 };
    let capturedGain = null;
    const origCreateGain = audioCtx.createGain.bind(audioCtx);
    audioCtx.createGain = () => { const g = origCreateGain(); const orig = g.gain.linearRampToValueAtTime.bind(g.gain);
      g.gain.linearRampToValueAtTime = (v,t) => { capturedGain = v; return orig(v,t); }; return g; };
    triggerDrumHit(0,0,64);   // velocity a meta' scala (~0.5)
    globalThis.__result = capturedGain;
  `);
  assert.ok(sb.__result > 0.4 && sb.__result < 0.6, `velocity 64/127 deve scalare il gain a circa 0.5, trovato ${sb.__result}`);
}

async function testDrumsModeIgnoredWhenPerfModeNull(){
  const sb = await runWithApp(`
    ac();
    drumKit[0][0] = { buffer:{duration:1}, name:'Kick' };
    clips[0][0] = { buffer:{duration:1}, name:'BankLoop', mode:'loop' };
    onMidiMessage({ data:[0x90, 81, 100] });   // nota 81 = pad (0,0); perfMode=null: deve comportarsi come sempre (triggerDown sul banco)
    await new Promise(r=>setTimeout(r,60));
    globalThis.__result = { oneShotCount: oneShots.length, playingRowOnBank: trackState[0].playingRow };
  `);
  const r = sb.__result;
  assert.strictEqual(r.oneShotCount, 0, 'fuori da Drums mode non deve suonare il kit');
  assert.strictEqual(r.playingRowOnBank, 0, 'fuori da Drums mode il comportamento normale (loop) resta invariato');
}

(async () => {
  const tests = [
    ['Drums mode suona il kit, non il banco', testDrumsModePlaysKitNotBankClip],
    ['la velocity scala il gain del colpo', testDrumsModeVelocityScalesGain],
    ['fuori da Drums mode il comportamento e\' invariato', testDrumsModeIgnoredWhenPerfModeNull],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_drums.js
```
Atteso: FAIL — `triggerDrumHit` non esiste, e `onMidiMessage` non ramifica ancora su `perfMode==='drums'` per la griglia (chiama sempre `triggerDown`).

- [ ] **Step 3: Implementa nel sorgente**

In `_sorgente/launchpad-studio.html`, subito prima di `function playOnce(r,c){` (circa riga 1106), aggiungi:
```js
function triggerDrumHit(r,c,velocity){
  const clip=drumKit[r][c]; if(!clip) return;
  ac().resume();
  const {start:tS,end:tE}=trimBounds(clip);
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=false; src.playbackRate.value=rateFor(clip);
  const vel=Math.max(0,Math.min(1,(velocity!=null?velocity:127)/127));
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip)*vel,now()+0.005);
  src.connect(g).connect(trackGains[c]); src.start(now(),tS,tE-tS); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'oneshot'});
  oneShots.push(src); src.onended=()=>{ oneShots=oneShots.filter(s=>s!==src); };
}
```
Poi, nella funzione `onMidiMessage`, sostituisci il blocco finale:
```js
  const p=noteToPad[d1]; if(!p) return;
  if(type===0x90&&d2>0){ triggerDown(p.r,p.c); }
  else if(type===0x80||(type===0x90&&d2===0)){ triggerUp(p.r,p.c); }
}
```
con:
```js
  const p=noteToPad[d1]; if(!p) return;
  if(perfMode==='drums'){ if(type===0x90&&d2>0){ triggerDrumHit(p.r,p.c,d2); } return; }
  if(type===0x90&&d2>0){ triggerDown(p.r,p.c); }
  else if(type===0x80||(type===0x90&&d2===0)){ triggerUp(p.r,p.c); }
}
```
(la ramificazione per `perfMode==='keys'` viene aggiunta nel Task 4, non qui.)

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_drums.js
```
Atteso: tutti e 3 PASS.

- [ ] **Step 5: Rebuild e regressione**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "Modalita' Drums: colpi one-shot velocity-sensitive dal kit dedicato"
```

---

## Task 4: Modalità Keys — clip selezionato a intonazioni isomorfe, stile gate

**Files:**
- Modify: `_sorgente/launchpad-studio.html`, vicino a `startGate`/`stopGate` (circa righe 1116-1133) per le nuove funzioni; `onMidiMessage` per il routing; `applyRates()` (circa riga 1023) per l'aggiornamento live del pitch.
- Test: `scratchpad/test_perfmode_keys.js`

**Interfaces:**
- Consuma: `clips`, `selected.r`/`selected.c`, `trimBounds`, `rateFor`, `gainFor`, `now()`, `ac()`, `trackGains[c]`, `startTime`, `playing` (già esistenti).
- Produce: `keysSrc` (oggetto, chiave `r*8+c`, stessa forma di `gateSrc`: `{src,g}`), `startKeysNote(r,c,velocity)`, `stopKeysNote(r,c)`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_keys.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testKeysPlaysSelectedClipAtOffsetPitch(){
  const sb = await runWithApp(`
    ac();
    selected.r=3; selected.c=2;
    clips[3][2] = { buffer:{duration:1}, name:'Bass', mode:'loop', pitch:0 };
    perfMode='keys';
    onMidiMessage({ data:[0x90, 53, 100] });   // nota 53 = pad (3,2) sulla griglia: padToNote(3,2)=11+(7-3)*10+2=53
    globalThis.__result = { keysSrcCount: Object.keys(keysSrc).length };
  `);
  assert.strictEqual(sb.__result.keysSrcCount, 1, 'una nota Keys deve creare una voce attiva in keysSrc');
}

async function testKeysNoteOnOffLifecycle(){
  const sb = await runWithApp(`
    ac();
    selected.r=0; selected.c=0;
    clips[0][0] = { buffer:{duration:1}, name:'Bass', mode:'loop' };
    perfMode='keys';
    onMidiMessage({ data:[0x90, 81, 100] });   // nota 81 = pad (0,0): padToNote(0,0)=11+(7-0)*10+0=81
    const afterOn = Object.keys(keysSrc).length;
    onMidiMessage({ data:[0x80, 81, 0] });     // note off
    globalThis.__result = { afterOn, afterOffCount: Object.keys(keysSrc).length };
  `);
  const r = sb.__result;
  assert.strictEqual(r.afterOn, 1);
  assert.strictEqual(r.afterOffCount, 0, 'note-off deve rimuovere la voce da keysSrc');
}

async function testKeysPitchOffsetAppliedToPlaybackRate(){
  const sb = await runWithApp(`
    ac();
    selected.r=7; selected.c=0;   // riga in basso, colonna 0: keysPitchOffset=0
    clips[7][0] = { buffer:{duration:1}, name:'Bass', mode:'loop', pitch:0 };
    startKeysNote(7,7,100);   // premo il pad (7,7): offset = keysPitchOffset(7,7) = 7 semitoni
    const rate7 = keysSrc[7*8+7].src.playbackRate.value;
    startKeysNote(0,0,100);   // premo il pad (0,0): offset = keysPitchOffset(0,0) = 35 semitoni
    const rate0 = keysSrc[0*8+0].src.playbackRate.value;
    globalThis.__result = { rate7, rate0, expected7: Math.pow(2,7/12), expected0: Math.pow(2,35/12) };
  `);
  const r = sb.__result;
  assert.ok(Math.abs(r.rate7 - r.expected7) < 1e-6, `pad (7,7) deve avere playbackRate 2^(7/12), trovato ${r.rate7}`);
  assert.ok(Math.abs(r.rate0 - r.expected0) < 1e-6, `pad (0,0) deve avere playbackRate 2^(35/12), trovato ${r.rate0}`);
}

async function testKeysDoesNotAffectBankLoop(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:1}, name:'X', mode:'loop' };
    triggerDown(0,0);
    await new Promise(r=>setTimeout(r,60));
    const playingRowBefore = trackState[0].playingRow;
    selected.r=1; selected.c=1;
    clips[1][1] = { buffer:{duration:1}, name:'Instrument' };
    perfMode='keys';
    onMidiMessage({ data:[0x90, 72, 100] });   // nota 72 = pad (1,1): padToNote(1,1)=11+(7-1)*10+1=72
    globalThis.__result = { playingRowBefore, playingRowAfter: trackState[0].playingRow };
  `);
  const r = sb.__result;
  assert.strictEqual(r.playingRowBefore, 0);
  assert.strictEqual(r.playingRowAfter, 0, 'suonare una nota Keys non deve toccare trackState del loop in corso su un\'altra colonna');
}

(async () => {
  const tests = [
    ['Keys crea una voce attiva sul clip selezionato', testKeysPlaysSelectedClipAtOffsetPitch],
    ['note-on/off gestiscono correttamente keysSrc', testKeysNoteOnOffLifecycle],
    ['il playbackRate riflette keysPitchOffset', testKeysPitchOffsetAppliedToPlaybackRate],
    ['Keys non tocca i loop dei banchi', testKeysDoesNotAffectBankLoop],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```
Nota: i numeri di nota nei test (53 per il pad (3,2), 81 per (0,0), 72 per (1,1)) sono già calcolati con `padToNote(r,c)=11+(7-r)*10+c` — se un test comunque fallisse con `keysSrcCount: 0`/simili, ricontrolla il calcolo prima di sospettare l'implementazione.

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_keys.js
```
Atteso: FAIL — `keysSrc`/`startKeysNote`/`stopKeysNote` non esistono, e `onMidiMessage` non ramifica su `perfMode==='keys'`.

- [ ] **Step 3: Implementa nel sorgente**

In `_sorgente/launchpad-studio.html`, subito dopo la chiusura di `function stopGate(r,c){...}` (circa riga 1133), aggiungi:
```js
const keysSrc={};   // note "Keys" attive: chiave r*8+c, stessa forma di gateSrc ma indipendente (non tocca trackState/gateSrc)
function startKeysNote(r,c,velocity){
  const clip=clips[selected.r][selected.c]; if(!clip) return;
  ac().resume(); stopKeysNote(r,c);
  const {start:tS,end:tE}=trimBounds(clip);
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=true; src.loopStart=tS; src.loopEnd=tE;
  src.playbackRate.value=rateFor(clip)*Math.pow(2,keysPitchOffset(r,c)/12);
  const vel=Math.max(0,Math.min(1,(velocity!=null?velocity:127)/127));
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip)*vel,now()+0.005);
  src.connect(g).connect(trackGains[selected.c]);
  const grate=src.playbackRate.value||1, gper=(tE-tS)/grate;
  let goff=tS; if(gper>0.0001 && playing){ let e=now()-startTime; e=((e%gper)+gper)%gper; goff=tS+e*grate; }
  src.start(now(), goff);
  keysSrc[r*8+c]={src,g};
}
function stopKeysNote(r,c){
  const k=r*8+c, o=keysSrc[k];
  if(o){ const t=now(); try{ o.g.gain.setValueAtTime(o.g.gain.value,t); o.g.gain.linearRampToValueAtTime(0,t+0.006); o.src.stop(t+0.02);}catch(e){} delete keysSrc[k]; }
}
```
Poi, in `applyRates()` (circa riga 1023), aggiungi in coda (dopo il ciclo esistente su `gateSrc`) l'aggiornamento live delle note Keys attive:
```js
function applyRates(){ if(!audioCtx) return;
  for(let c=0;c<COLS;c++){ const ts=trackState[c]; if(ts.src&&ts.playingRow!=null){ const cl=clips[ts.playingRow][c]; if(cl){ try{ ts.src.playbackRate.setTargetAtTime(rateFor(cl),audioCtx.currentTime,0.03);}catch(e){} } } }
  for(const k in gateSrc){ const o=gateSrc[k], r=Math.floor(k/8), c=k%8, cl=clips[r][c]; if(cl&&o.src){ try{ o.src.playbackRate.setTargetAtTime(rateFor(cl),audioCtx.currentTime,0.03);}catch(e){} } }
  for(const k in keysSrc){ const o=keysSrc[k], r=Math.floor(k/8), c=k%8, cl=clips[selected.r][selected.c]; if(cl&&o.src){ try{ o.src.playbackRate.setTargetAtTime(rateFor(cl)*Math.pow(2,keysPitchOffset(r,c)/12),audioCtx.currentTime,0.03);}catch(e){} } }
}
```
Infine, in `onMidiMessage`, estendi il blocco aggiunto nel Task 3:
```js
  const p=noteToPad[d1]; if(!p) return;
  if(perfMode==='drums'){ if(type===0x90&&d2>0){ triggerDrumHit(p.r,p.c,d2); } return; }
  if(perfMode==='keys'){
    if(type===0x90&&d2>0){ startKeysNote(p.r,p.c,d2); }
    else if(type===0x80||(type===0x90&&d2===0)){ stopKeysNote(p.r,p.c); }
    return;
  }
  if(type===0x90&&d2>0){ triggerDown(p.r,p.c); }
  else if(type===0x80||(type===0x90&&d2===0)){ triggerUp(p.r,p.c); }
}
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_keys.js
```
Atteso: tutti e 4 PASS (correggi eventuali numeri di nota nel test come indicato allo Step 1, poi rilancia).

- [ ] **Step 5: Rebuild e regressione**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "Modalita' Keys: il clip selezionato suona a intonazioni isomorfe a quarte, stile gate"
```

---

## Task 5: Editor consapevole della griglia attiva (`activeGrid()`) + uscita automatica al cambio banco

**Files:**
- Modify: `_sorgente/launchpad-studio.html` — `selectPad`, `renderPad`, `loadFileToPad`, `clearBtn.onclick`, `padMode.onchange`, `padModeCol.onclick`, `clipRev.onchange`, `copyClipBtn.onclick`, `pasteClipBtn.onclick`, `liveClipUpdate`, `clipGain.oninput`, `clipPitch.oninput`, `clipChoke.onchange`, `clipTrimStart.oninput`, `clipTrimEnd.oninput`, `switchBank`.
- Test: `scratchpad/test_perfmode_editor.js`

**Interfaces:**
- Consuma: `activeGrid()` (Task 1).
- Nessuna nuova funzione prodotta — solo call site esistenti che ora leggono/scrivono tramite `activeGrid()` invece di `clips` direttamente.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_editor.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testLoadFileWritesToKitWhenInDrumsMode(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    selected.r=2; selected.c=3;
    const fakeFile = { name:'Snare.wav', type:'audio/wav', arrayBuffer: async () => new ArrayBuffer(8) };
    await loadFileToPad(fakeFile, 2, 3);
    globalThis.__result = { kitCell: drumKit[2][3] && drumKit[2][3].name, bankCell: clips[2][3] };
  `);
  const r = sb.__result;
  assert.strictEqual(r.kitCell, 'Snare', 'in Drums mode il file caricato deve finire in drumKit, non in clips');
  assert.strictEqual(r.bankCell, null, 'il banco normale non deve essere toccato');
}

async function testSelectPadReflectsKitContentInDrumsMode(){
  const sb = await runWithApp(`
    ac();
    drumKit[1][1] = { buffer:{duration:2}, name:'Clap', mode:'loop', gain:0.7, pitch:3, choke:2, trimStart:0.1, trimEnd:1.5 };
    perfMode='drums';
    selectPad(1,1);
    globalThis.__result = {
      gain: +document.getElementById('clipGain').value,
      pitch: +document.getElementById('clipPitch').value,
      choke: +document.getElementById('clipChoke').value,
    };
  `);
  const r = sb.__result;
  assert.strictEqual(r.gain, 0.7);
  assert.strictEqual(r.pitch, 3);
  assert.strictEqual(r.choke, 2);
}

async function testClearButtonClearsKitPadNotBankLoop(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:1}, name:'BankLoop', mode:'loop' };
    triggerDown(0,0);
    await new Promise(r=>setTimeout(r,60));
    const playingBefore = trackState[0].playingRow;
    drumKit[0][0] = { buffer:{duration:1}, name:'KitSample' };
    perfMode='drums'; selected.r=0; selected.c=0;
    document.getElementById('clearBtn').click();
    globalThis.__result = { kitCellAfter: drumKit[0][0], playingAfter: trackState[0].playingRow };
  `);
  const r = sb.__result;
  assert.strictEqual(r.playingBefore, 0);
  assert.strictEqual(r.kitCellAfter, null, 'Svuota pad deve cancellare la cella del kit');
  assert.strictEqual(r.playingAfter, 0, 'non deve fermare il loop del banco normale sulla stessa colonna');
}

async function testCopyPasteWorksWithinKit(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    drumKit[0][0] = { buffer:{duration:1}, name:'A', mode:'loop', gain:0.5, pitch:2, choke:0, trimStart:0, trimEnd:1 };
    drumKit[0][1] = { buffer:{duration:1}, name:'B', mode:'loop', gain:1, pitch:0, choke:0, trimStart:0, trimEnd:1 };
    selected.r=0; selected.c=0;
    document.getElementById('copyClipBtn').click();
    selected.r=0; selected.c=1;
    document.getElementById('pasteClipBtn').click();
    globalThis.__result = { gain: drumKit[0][1].gain, pitch: drumKit[0][1].pitch };
  `);
  const r = sb.__result;
  assert.strictEqual(r.gain, 0.5);
  assert.strictEqual(r.pitch, 2);
}

async function testSwitchBankExitsPerfMode(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    await switchBank(1);
    globalThis.__result = perfMode;
  `);
  assert.strictEqual(sb.__result, null, 'cambiare banco deve uscire automaticamente da Drums/Keys');
}

(async () => {
  const tests = [
    ['loadFileToPad scrive nel kit in Drums mode', testLoadFileWritesToKitWhenInDrumsMode],
    ['selectPad mostra il contenuto del kit in Drums mode', testSelectPadReflectsKitContentInDrumsMode],
    ['Svuota pad opera sul kit, non sul banco', testClearButtonClearsKitPadNotBankLoop],
    ['copia/incolla funziona dentro il kit', testCopyPasteWorksWithinKit],
    ['switchBank esce automaticamente dall\'overlay', testSwitchBankExitsPerfMode],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_editor.js
```
Atteso: FAIL su tutti e 5 (tutte le funzioni editano ancora `clips` incondizionatamente).

- [ ] **Step 3: Implementa nel sorgente**

Applica queste sostituzioni testuali esatte in `_sorgente/launchpad-studio.html` (ogni blocco è un "prima" → "dopo"):

**`selectPad`** (circa riga 923), prima riga della funzione:
```js
// PRIMA
  const pm=document.getElementById('padMode'); const cl=clips[r][c]; if(pm) pm.value=(cl&&cl.mode)||'loop';
// DOPO
  const pm=document.getElementById('padMode'); const cl=activeGrid()[r][c]; if(pm) pm.value=(cl&&cl.mode)||'loop';
```

**`renderPad`** (cerca `function renderPad(r,c){`):
```js
// PRIMA
function renderPad(r,c){
  const el=padEls[r][c], clip=clips[r][c], ts=trackState[c];
  el.classList.toggle('loaded',!!clip);
  el.classList.toggle('playing',ts.playingRow===r);
  el.classList.toggle('queued',ts.queuedRow===r);
  el.classList.toggle('selected',selected.r===r&&selected.c===c);
// DOPO
function renderPad(r,c){
  const el=padEls[r][c], clip=activeGrid()[r][c], ts=trackState[c];
  const showPlayState = perfMode===null;   // in Drums/Keys lo stato di trackState appartiene al banco, non al kit: non mostrarlo
  el.classList.toggle('loaded',!!clip);
  el.classList.toggle('playing', showPlayState && ts.playingRow===r);
  el.classList.toggle('queued', showPlayState && ts.queuedRow===r);
  el.classList.toggle('selected',selected.r===r&&selected.c===c);
```

**`loadFileToPad`**:
```js
// PRIMA
    clips[r][c]={buffer:audio,name:file.name.replace(/\.[^.]+$/,''),raw,mime:file.type||'audio/wav'};
// DOPO
    activeGrid()[r][c]={buffer:audio,name:file.name.replace(/\.[^.]+$/,''),raw,mime:file.type||'audio/wav'};
```

**`clearBtn`**:
```js
// PRIMA
document.getElementById('clearBtn').onclick=()=>{const{r,c}=selected; pushUndo(); stopTrackClip(c,true); clips[r][c]=null; renderPad(r,c); updateLed(r,c);};
// DOPO
document.getElementById('clearBtn').onclick=()=>{const{r,c}=selected; pushUndo(); if(perfMode===null) stopTrackClip(c,true); activeGrid()[r][c]=null; renderPad(r,c); updateLed(r,c);};
```

**`padMode`/`padModeCol`**:
```js
// PRIMA
document.getElementById('padMode').onchange=(e)=>{ const{r,c}=selected; if(clips[r][c]){ pushUndo(); stopPadSound(r,c); clips[r][c].mode=e.target.value; renderPad(r,c); updateLed(r,c);} };
document.getElementById('padModeCol').onclick=()=>{ const{c}=selected; const m=document.getElementById('padMode').value;
  pushUndo();
  for(let r=0;r<ROWS;r++){ if(clips[r][c]){ stopPadSound(r,c); clips[r][c].mode=m; renderPad(r,c); updateLed(r,c);} } };
// DOPO
document.getElementById('padMode').onchange=(e)=>{ const{r,c}=selected; const g=activeGrid(); if(g[r][c]){ pushUndo(); if(perfMode===null) stopPadSound(r,c); g[r][c].mode=e.target.value; renderPad(r,c); updateLed(r,c);} };
document.getElementById('padModeCol').onclick=()=>{ const{c}=selected; const m=document.getElementById('padMode').value; const g=activeGrid();
  pushUndo();
  for(let r=0;r<ROWS;r++){ if(g[r][c]){ if(perfMode===null) stopPadSound(r,c); g[r][c].mode=m; renderPad(r,c); updateLed(r,c);} } };
```

**`clipRev`**:
```js
// PRIMA
document.getElementById('clipRev').onchange=(e)=>{ const{r,c}=selected; const cl=clips[r][c]; if(!cl){ e.target.checked=false; return; }
// DOPO
document.getElementById('clipRev').onchange=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl){ e.target.checked=false; return; }
```
(resto della funzione invariato)

**`copyClipBtn`/`pasteClipBtn`**:
```js
// PRIMA
document.getElementById('copyClipBtn').onclick=()=>{ const{r,c}=selected; const cl=clips[r][c]; if(!cl) return;
// DOPO
document.getElementById('copyClipBtn').onclick=()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
```
```js
// PRIMA
document.getElementById('pasteClipBtn').onclick=()=>{ const{r,c}=selected; const cl=clips[r][c]; if(!cl||!clipSettingsClipboard) return;
// DOPO
document.getElementById('pasteClipBtn').onclick=()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl||!clipSettingsClipboard) return;
```
(resto di entrambe le funzioni invariato)

**`liveClipUpdate`/`clipGain`/`clipPitch`/`clipChoke`**:
```js
// PRIMA
function liveClipUpdate(r,c){ const ts=trackState[c], cl=clips[r][c]; if(!cl||!audioCtx) return;
  if(ts.playingRow===r && ts.src){ try{ ts.src.playbackRate.setTargetAtTime(rateFor(cl),audioCtx.currentTime,0.02); if(ts.g) ts.g.gain.setTargetAtTime(gainFor(cl),audioCtx.currentTime,0.02); }catch(e){} } }
document.getElementById('clipGain').oninput=(e)=>{ const{r,c}=selected; if(clips[r][c]){ clips[r][c].gain=+e.target.value; liveClipUpdate(r,c);} };
document.getElementById('clipPitch').oninput=(e)=>{ document.getElementById('clipPitchVal').textContent=e.target.value; const{r,c}=selected; if(clips[r][c]){ clips[r][c].pitch=+e.target.value; liveClipUpdate(r,c);} };
document.getElementById('clipChoke').onchange=(e)=>{ const{r,c}=selected; if(clips[r][c]){ pushUndo(); clips[r][c].choke=+e.target.value; } };
// DOPO
function liveClipUpdate(r,c){ const ts=trackState[c], cl=activeGrid()[r][c]; if(!cl||!audioCtx) return;
  if(ts.playingRow===r && ts.src){ try{ ts.src.playbackRate.setTargetAtTime(rateFor(cl),audioCtx.currentTime,0.02); if(ts.g) ts.g.gain.setTargetAtTime(gainFor(cl),audioCtx.currentTime,0.02); }catch(e){} } }
document.getElementById('clipGain').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(cl){ cl.gain=+e.target.value; liveClipUpdate(r,c);} };
document.getElementById('clipPitch').oninput=(e)=>{ document.getElementById('clipPitchVal').textContent=e.target.value; const{r,c}=selected; const cl=activeGrid()[r][c]; if(cl){ cl.pitch=+e.target.value; liveClipUpdate(r,c);} };
document.getElementById('clipChoke').onchange=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(cl){ pushUndo(); cl.choke=+e.target.value; } };
```

**`clipTrimStart`/`clipTrimEnd`**:
```js
// PRIMA
document.getElementById('clipTrimStart').oninput=(e)=>{ const{r,c}=selected; const cl=clips[r][c]; if(!cl||!cl.buffer) return;
// DOPO
document.getElementById('clipTrimStart').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl||!cl.buffer) return;
```
```js
// PRIMA
document.getElementById('clipTrimEnd').oninput=(e)=>{ const{r,c}=selected; const cl=clips[r][c]; if(!cl||!cl.buffer) return;
// DOPO
document.getElementById('clipTrimEnd').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl||!cl.buffer) return;
```
(resto di entrambe invariato)

**`switchBank`**:
```js
// PRIMA
async function switchBank(i){ if(i===activeBank||i<0||i>=NBANKS) return;
  await stopAllSmooth(1.0);   // dissolvenza un po' piu' breve del cambio genere (1.2s): qui i suoni sono gia' decodificati, non c'e' attesa di caricamento
  activeBank=i; clips=banks[i]; selectPad(selected.r,selected.c); recomputeTrackColors(); renderAll(); refreshAllLeds(); updateBankUI(); }
// DOPO
async function switchBank(i){ if(i===activeBank||i<0||i>=NBANKS) return;
  await stopAllSmooth(1.0);   // dissolvenza un po' piu' breve del cambio genere (1.2s): qui i suoni sono gia' decodificati, non c'e' attesa di caricamento
  perfMode=null;
  activeBank=i; clips=banks[i]; selectPad(selected.r,selected.c); recomputeTrackColors(); renderAll(); refreshAllLeds(); updateBankUI(); }
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_editor.js
```
Atteso: tutti e 5 PASS.

- [ ] **Step 5: Rebuild e regressione completa**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```
Presta particolare attenzione a `test_trim.js`, `test_copy_paste_clip.js`, `test_loadfile_mode.js`, `test_bank_smooth.js` — sono i test più a rischio di regressione da questo task (molti call site toccati).

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "L'editor pad (selectPad/trim/copia-incolla/carica file) diventa consapevole della griglia attiva (banco o kit Drums)"
```

---

## Task 6: Feedback LED — tasti superiori e griglia in Drums/Keys

**Files:**
- Modify: `_sorgente/launchpad-studio.html` — `refreshAllLeds`, `updateLed` (circa righe 719-736), `onPerfModeChanged` (Task 2).
- Test: `scratchpad/test_perfmode_leds.js`

**Interfaces:**
- Consuma: `perfMode`, `drumKit` (Task 1).
- Produce: `setTopLed(index,color,mode)` — `index` 0-7 (0=Up...7=User), stessa firma concettuale di `setLed` ma per la fila superiore.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_leds.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testTopRowLedsLightUpWithDrumsActive(){
  const sb = await runWithApp(`
    ac();
    const sent = [];
    outPort = { send: (bytes) => sent.push(bytes) };
    perfMode = 'drums';
    refreshAllLeds();
    const drumsMsg = sent.find(b => b[1]===96);   // nota 96 = Drums
    const sessionMsg = sent.find(b => b[1]===95);
    globalThis.__result = { drumsColor: drumsMsg && drumsMsg[2], sessionColor: sessionMsg && sessionMsg[2] };
  `);
  const r = sb.__result;
  assert.ok(r.drumsColor != null, 'il tasto Drums deve ricevere un colore quando attivo');
  assert.notStrictEqual(r.drumsColor, r.sessionColor, 'Drums attivo deve avere un colore diverso da Session (che non e\' un toggle)');
}

async function testGridLedsReflectKitContentInDrumsMode(){
  const sb = await runWithApp(`
    ac();
    const sent = [];
    outPort = { send: (bytes) => sent.push(bytes) };
    perfMode = 'drums';
    drumKit[0][0] = { buffer:{duration:1}, name:'Kick' };
    updateLed(0,0);
    updateLed(0,1);   // vuoto
    globalThis.__result = { loadedColor: sent[0][2], emptyColor: sent[1][2] };
  `);
  const r = sb.__result;
  assert.notStrictEqual(r.loadedColor, 0, 'un pad del kit caricato deve avere un colore acceso');
  assert.strictEqual(r.emptyColor, 0, 'un pad del kit vuoto deve restare spento');
}

async function testGridLedsUniformInKeysMode(){
  const sb = await runWithApp(`
    ac();
    const sent = [];
    outPort = { send: (bytes) => sent.push(bytes) };
    perfMode = 'keys';
    updateLed(0,0);
    updateLed(5,5);
    globalThis.__result = { c1: sent[0][2], c2: sent[1][2] };
  `);
  const r = sb.__result;
  assert.strictEqual(r.c1, r.c2, 'in Keys mode tutta la griglia deve avere lo stesso colore, a prescindere dalla posizione');
  assert.notStrictEqual(r.c1, 0, 'il colore Keys non deve essere spento');
}

(async () => {
  const tests = [
    ['i LED dei tasti superiori riflettono perfMode', testTopRowLedsLightUpWithDrumsActive],
    ['i LED della griglia riflettono il contenuto del kit in Drums mode', testGridLedsReflectKitContentInDrumsMode],
    ['i LED della griglia sono uniformi in Keys mode', testGridLedsUniformInKeysMode],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_leds.js
```
Atteso: FAIL — i tasti superiori non ricevono mai un LED oggi, e `updateLed` non conosce ancora `perfMode`.

- [ ] **Step 3: Implementa nel sorgente**

Subito dopo `function setLed(r,c,color,mode='static'){...}` (circa riga 719-723), aggiungi:
```js
function setTopLed(index,color,mode='static'){
  if(!outPort) return;
  const st=mode==='pulse'?0x92:mode==='flash'?0x91:0x90;
  try{ outPort.send([st,91+index,color]); }catch(e){}
}
```
Sostituisci `refreshAllLeds`:
```js
// PRIMA
function refreshAllLeds(){ for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) updateLed(r,c);
  if(outPort){ for(let r=0;r<ROWS;r++){ try{ outPort.send([0x90,19+(7-r)*10,37]); }catch(e){} } } }
// DOPO
function refreshAllLeds(){ for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) updateLed(r,c);
  if(outPort){ for(let r=0;r<ROWS;r++){ try{ outPort.send([0x90,19+(7-r)*10,37]); }catch(e){} } }
  setTopLed(0,3,'static'); setTopLed(1,3,'static'); setTopLed(2,3,'static'); setTopLed(3,3,'static');   // Up/Down/Left/Right, neutro
  setTopLed(4,3,'static');                                    // Session (non e' un toggle)
  setTopLed(5,perfMode==='drums'?5:3,'static');                // Drums
  setTopLed(6,perfMode==='keys'?37:3,'static');                // Keys
  setTopLed(7,3,'static');                                     // User (non e' un toggle)
}
```
Sostituisci `updateLed`:
```js
// PRIMA
function updateLed(r,c){
  const ts=trackState[c];
  const anySolo=tracks.some(t=>t.solo), silenced=anySolo?!tracks[c].solo:tracks[c].muted;
  if(ts.playingRow===r && !silenced){ setLed(r,c,21,'pulse'); return; }
  if(ts.queuedRow===r && !silenced){ setLed(r,c,13,'flash'); return; }
  if(clips[r][c]){ setLed(r,c,padColorIndex(c),'static'); return; }
  setLed(r,c,0,'static');
}
// DOPO
function updateLed(r,c){
  if(perfMode==='drums'){ setLed(r,c, drumKit[r][c]?9:0, 'static'); return; }
  if(perfMode==='keys'){ setLed(r,c,37,'static'); return; }
  const ts=trackState[c];
  const anySolo=tracks.some(t=>t.solo), silenced=anySolo?!tracks[c].solo:tracks[c].muted;
  if(ts.playingRow===r && !silenced){ setLed(r,c,21,'pulse'); return; }
  if(ts.queuedRow===r && !silenced){ setLed(r,c,13,'flash'); return; }
  if(clips[r][c]){ setLed(r,c,padColorIndex(c),'static'); return; }
  setLed(r,c,0,'static');
}
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_leds.js
```
Atteso: tutti e 3 PASS.

- [ ] **Step 5: Rebuild e regressione**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "LED: i 4 tasti superiori si accendono, la griglia riflette Drums/Keys quando attivi"
```

---

## Task 7: UI a schermo — bottoni Drums Kit/Keys e banner

**Files:**
- Modify: `_sorgente/launchpad-studio.html` — vicino alla IIFE che crea la bank bar (circa righe 826-830); `onPerfModeChanged` (Task 2, va sostituito qui con l'implementazione reale).
- Test: `scratchpad/test_perfmode_ui.js`

**Interfaces:**
- Consuma: `perfMode`, `bankBar` DOM element (già esistente via `document.getElementById('bankBar')`).
- Produce: `updatePerfModeUI()` (nessun argomento; aggiorna le classi `on` dei bottoni Drums/Keys e il testo/visibilità del banner). `onPerfModeChanged()` viene ridefinita per chiamare anche `updatePerfModeUI()`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_ui.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testDrumsButtonTogglesPerfModeAndOnClass(){
  const sb = await runWithApp(`
    ac();
    const bb = document.getElementById('bankBar');
    const drumsBtn = bb.children.find(c => c.textContent && c.textContent.includes('Drums'));
    drumsBtn.click();
    const afterOn = { mode: perfMode, hasOnClass: drumsBtn.classList.contains('on') };
    drumsBtn.click();
    const afterOff = { mode: perfMode, hasOnClass: drumsBtn.classList.contains('on') };
    globalThis.__result = { afterOn, afterOff };
  `);
  const r = sb.__result;
  assert.strictEqual(r.afterOn.mode, 'drums');
  assert.strictEqual(r.afterOn.hasOnClass, true, 'il bottone Drums Kit deve mostrarsi attivo');
  assert.strictEqual(r.afterOff.mode, null);
  assert.strictEqual(r.afterOff.hasOnClass, false);
}

async function testKeysButtonTogglesPerfMode(){
  const sb = await runWithApp(`
    ac();
    const bb = document.getElementById('bankBar');
    const keysBtn = bb.children.find(c => c.textContent && c.textContent.includes('Keys'));
    keysBtn.click();
    globalThis.__result = perfMode;
  `);
  assert.strictEqual(sb.__result, 'keys');
}

async function testBankButtonExitsPerfModeUI(){
  const sb = await runWithApp(`
    ac();
    const bb = document.getElementById('bankBar');
    const drumsBtn = bb.children.find(c => c.textContent && c.textContent.includes('Drums'));
    drumsBtn.click();
    const beforeSwitch = drumsBtn.classList.contains('on');
    await switchBank(1);
    globalThis.__result = { beforeSwitch, afterSwitch: drumsBtn.classList.contains('on') };
  `);
  const r = sb.__result;
  assert.strictEqual(r.beforeSwitch, true);
  assert.strictEqual(r.afterSwitch, false, 'cambiando banco il bottone Drums Kit deve tornare non attivo');
}

(async () => {
  const tests = [
    ['il bottone Drums Kit attiva/disattiva perfMode e la classe on', testDrumsButtonTogglesPerfModeAndOnClass],
    ['il bottone Keys attiva perfMode', testKeysButtonTogglesPerfMode],
    ['cambiare banco disattiva i bottoni overlay', testBankButtonExitsPerfModeUI],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```
Nota: questo test richiede che l'harness (`makeFakeEl`) supporti `classList.contains` con stato reale (non sempre `false`) e che `el.children` sia un array reale con `.find`. Verifica prima di scrivere il test che `harness.js` li supporti già (leggi `makeFakeEl`/`makeFakeDocument` in cima al file): la `classList` finta attuale ha `contains(){ return false; }` fisso e `toggle(){}` no-op — **non traccia lo stato**. Se è così, PRIMA di questo Step aggiorna `harness.js` (non è codice applicativo, è infrastruttura di test) rendendo `classList` stateful:
```js
// in makeFakeEl, sostituisci:
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
// con:
    classList: { _set: new Set(), add(cls){ this._set.add(cls); }, remove(cls){ this._set.delete(cls); },
      toggle(cls,force){ const has=this._set.has(cls); const on=(force!==undefined)?force:!has; if(on) this._set.add(cls); else this._set.delete(cls); return on; },
      contains(cls){ return this._set.has(cls); } },
```
e verifica che nessun test esistente (`for f in test_*.js; do node "$f"; done`) si rompa per questo cambiamento prima di proseguire (è un cambiamento infrastrutturale, va isolato e verificato a parte con l'intera suite).

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_ui.js
```
Atteso: FAIL — non esiste ancora nessun bottone "Drums Kit"/"Keys" nella bank bar.

- [ ] **Step 3: Implementa nel sorgente**

Sostituisci la IIFE della bank bar (circa righe 826-830):
```js
// PRIMA
(function(){
  const bb=document.getElementById('bankBar');
  const lbl=document.createElement('span'); lbl.textContent='Bank'; lbl.style.cssText='font-size:12px;color:var(--dim);margin-right:4px'; bb.appendChild(lbl);
  for(let i=0;i<NBANKS;i++){ const b=document.createElement('button'); b.className='act'+(i===0?' on':''); b.textContent=String.fromCharCode(65+i); b.style.padding='6px 11px'; b.onclick=()=>switchBank(i); bb.appendChild(b); bankBtns.push(b); }
})();
// DOPO
let drumsKitBtn=null, keysBtn=null, perfModeBanner=null;
function updatePerfModeUI(){
  if(drumsKitBtn) drumsKitBtn.classList.toggle('on', perfMode==='drums');
  if(keysBtn) keysBtn.classList.toggle('on', perfMode==='keys');
  if(perfModeBanner){
    if(perfMode==='drums'){ perfModeBanner.style.display=''; perfModeBanner.textContent='🥁 Modalità Drums Kit — i pad suonano il kit dedicato (colpi one-shot)'; }
    else if(perfMode==='keys'){ perfModeBanner.style.display=''; const cl=clips[selected.r][selected.c]; perfModeBanner.textContent='🎹 Modalità Keys — i pad suonano "'+(cl?cl.name:'(nessun clip selezionato)')+'" a intonazioni diverse'; }
    else { perfModeBanner.style.display='none'; }
  }
}
(function(){
  const bb=document.getElementById('bankBar');
  const lbl=document.createElement('span'); lbl.textContent='Bank'; lbl.style.cssText='font-size:12px;color:var(--dim);margin-right:4px'; bb.appendChild(lbl);
  for(let i=0;i<NBANKS;i++){ const b=document.createElement('button'); b.className='act'+(i===0?' on':''); b.textContent=String.fromCharCode(65+i); b.style.padding='6px 11px'; b.onclick=()=>switchBank(i); bb.appendChild(b); bankBtns.push(b); }
  drumsKitBtn=document.createElement('button'); drumsKitBtn.className='act'; drumsKitBtn.textContent='🥁 Drums Kit'; drumsKitBtn.style.cssText='padding:6px 11px;margin-left:8px';
  drumsKitBtn.onclick=()=>{ perfMode=(perfMode==='drums')?null:'drums'; onPerfModeChanged(); };
  bb.appendChild(drumsKitBtn);
  keysBtn=document.createElement('button'); keysBtn.className='act'; keysBtn.textContent='🎹 Keys'; keysBtn.style.cssText='padding:6px 11px;margin-left:4px';
  keysBtn.onclick=()=>{ perfMode=(perfMode==='keys')?null:'keys'; onPerfModeChanged(); };
  bb.appendChild(keysBtn);
  perfModeBanner=document.createElement('div'); perfModeBanner.style.cssText='display:none;margin-top:6px;padding:6px 10px;background:#20242e;border:1px solid #2c313d;border-radius:8px;font-size:12px;color:var(--accent)';
  bb.parentNode.insertBefore(perfModeBanner, bb.nextSibling);
})();
```
Sostituisci `onPerfModeChanged` (definita nel Task 2):
```js
// PRIMA
function onPerfModeChanged(){ renderAll(); refreshAllLeds(); }
// DOPO
function onPerfModeChanged(){ selectPad(selected.r,selected.c); renderAll(); refreshAllLeds(); updatePerfModeUI(); }
```
Infine, in `switchBank` (Task 5), dopo `perfMode=null;` aggiungi la chiamata a `updatePerfModeUI()`:
```js
// PRIMA
  perfMode=null;
  activeBank=i; clips=banks[i]; selectPad(selected.r,selected.c); recomputeTrackColors(); renderAll(); refreshAllLeds(); updateBankUI(); }
// DOPO
  perfMode=null; updatePerfModeUI();
  activeBank=i; clips=banks[i]; selectPad(selected.r,selected.c); recomputeTrackColors(); renderAll(); refreshAllLeds(); updateBankUI(); }
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_ui.js
```
Atteso: tutti e 3 PASS.

- [ ] **Step 5: Rebuild e regressione completa**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```
Il cambiamento a `harness.js` (Step 1) è infrastrutturale e condiviso da tutta la suite: verifica con particolare attenzione che nessun test preesistente che usa `classList.toggle`/`.contains` (es. `test_bank_midi.js`, `test_undo.js`) si comporti diversamente da prima.

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "UI a schermo: bottoni Drums Kit/Keys nella bank bar con banner di stato"
```

---

## Task 8: Persistenza — `drumKit` in `.lpstudio`, autosave, Undo/Redo

**Files:**
- Modify: `_sorgente/launchpad-studio.html` — `saveBtn.onclick`, `setInput.onchange`, `buildAutosaveSnapshot`, `restoreAutosave`, `captureState`, `applyState`.
- Test: `scratchpad/test_perfmode_persistence.js`

**Interfaces:**
- Nessuna nuova funzione — estende il formato dati esistente con un campo `drumKit` opzionale/additivo, e la copertura Undo esistente.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `test_perfmode_persistence.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testSaveOpenRoundTripsDrumKit(){
  const sb = await runWithApp(`
    ac();
    drumKit[0][0] = { buffer:{duration:1}, name:'Kick', mode:'loop', raw:new ArrayBuffer(8), mime:'audio/wav', gain:0.8, pitch:1, choke:0, trimStart:0, trimEnd:1 };
    let savedJson = null;
    URL.createObjectURL = (blob) => { blob.text().then(t => savedJson = t); return 'blob:fake'; };
    document.getElementById('saveBtn').click();
    await new Promise(r=>setTimeout(r,10));
    drumKit[0][0] = null;   // simula un'app "vuota" prima del ripristino
    const fakeFile = { text: async () => savedJson };
    await document.getElementById('setInput').onchange({ target: { files:[fakeFile], value:'' } });
    globalThis.__result = { name: drumKit[0][0] && drumKit[0][0].name, gain: drumKit[0][0] && drumKit[0][0].gain };
  `);
  const r = sb.__result;
  assert.strictEqual(r.name, 'Kick', 'il kit deve sopravvivere al round-trip salva/apri set');
  assert.strictEqual(r.gain, 0.8);
}

async function testOldFileWithoutDrumKitLeavesKitUntouched(){
  const sb = await runWithApp(`
    ac();
    drumKit[3][3] = { buffer:{duration:1}, name:'ExistingKit' };
    const oldFormatJson = JSON.stringify({version:2,bpm:120,bars:4,quantMode:'off',phraseBars:4,activeBank:0,banks:[[],[],[],[]],tracks:[],snapshots:[]});
    const fakeFile = { text: async () => oldFormatJson };
    await document.getElementById('setInput').onchange({ target: { files:[fakeFile], value:'' } });
    globalThis.__result = drumKit[3][3] && drumKit[3][3].name;
  `);
  assert.strictEqual(sb.__result, 'ExistingKit', 'un file .lpstudio senza drumKit non deve cancellare il kit corrente');
}

async function testAutosaveRoundTripsDrumKit(){
  const sb = await runWithApp(`
    ac();
    drumKit[2][2] = { buffer:{duration:1}, name:'Hat', mode:'loop', raw:new ArrayBuffer(8), mime:'audio/wav', gain:1, pitch:0, choke:0, trimStart:0, trimEnd:1 };
    const snap = buildAutosaveSnapshot();
    drumKit[2][2] = null;
    await restoreAutosave(snap);
    globalThis.__result = drumKit[2][2] && drumKit[2][2].name;
  `);
  assert.strictEqual(sb.__result, 'Hat');
}

async function testUndoCoversDrumKitEdits(){
  const sb = await runWithApp(`
    ac();
    perfMode='drums';
    drumKit[0][0]=null;
    pushUndo();
    drumKit[0][0]={buffer:{duration:1},name:'NewHit'};
    undo();
    globalThis.__result = drumKit[0][0];
  `);
  assert.strictEqual(sb.__result, null, 'undo deve annullare una modifica al kit');
}

(async () => {
  const tests = [
    ['salva/apri set porta con se\' il kit Drums', testSaveOpenRoundTripsDrumKit],
    ['un file vecchio senza drumKit non cancella il kit corrente', testOldFileWithoutDrumKitLeavesKitUntouched],
    ['autosave porta con se\' il kit Drums', testAutosaveRoundTripsDrumKit],
    ['undo copre le modifiche al kit', testUndoCoversDrumKitEdits],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: Esegui e verifica che fallisca**

```
node test_perfmode_persistence.js
```
Atteso: FAIL su tutti e 4 — nessuna delle funzioni di salvataggio/undo conosce ancora `drumKit`.

- [ ] **Step 3: Implementa nel sorgente**

**`saveBtn.onclick`** — dopo il ciclo `for(let b=0;b<NBANKS;b++){...out.banks.push(bankClips);}` e prima di `const blob=...`, aggiungi:
```js
  const kitClips=[];
  for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){ const cl=drumKit[r][c];
    if(cl&&cl.raw) kitClips.push({r,c,name:cl.name,mime:cl.mime,reversed:cl.reversed||false,gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,data:abToB64(cl.raw)}); }
  out.drumKit=kitClips;
```

**`setInput.onchange`** — dopo il blocco `if(Array.isArray(data.banks)){...} else {...}` (formato v1/v2 banchi) e prima di `snapshots=Array.isArray(data.snapshots)...`, aggiungi:
```js
    if(Array.isArray(data.drumKit)){
      for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) drumKit[r][c]=null;
      for(const cl of data.drumKit) await loadClipInto(drumKit,cl,null);
    }
```

**`buildAutosaveSnapshot`** — dopo il ciclo `for(let b=0;b<NBANKS;b++){...out.banks.push(bankClips);}` e prima di `return out;`, aggiungi:
```js
  const kitClips=[];
  for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){ const cl=drumKit[r][c];
    if(cl&&cl.raw) kitClips.push({r,c,name:cl.name,mime:cl.mime,reversed:cl.reversed||false,
      gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,
      trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,
      raw:cl.raw}); }
  out.drumKit=kitClips;
```

**`restoreAutosave`** — dopo il blocco che ripopola `banks` (`for(let b=0;b<NBANKS;b++){ for(const cl of (snap.banks&&snap.banks[b])||[]){...} }`) e prima di `activeBank=Math.min(...)`, aggiungi:
```js
  for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) drumKit[r][c]=null;
  for(const cl of (snap.drumKit||[])){
    try{ const raw=cl.raw; const audio=await ac().decodeAudioData(raw.slice(0));
      const nc={buffer:audio,name:cl.name,raw,mime:cl.mime,gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null};
      if(cl.reversed){ nc.origBuffer=audio; nc.revBuffer=reversedBuffer(audio); nc.buffer=nc.revBuffer; nc.reversed=true; }
      drumKit[cl.r][cl.c]=nc;
    }catch(e){}
  }
```

**`captureState`**:
```js
// PRIMA
    snapshots:snapshots.map(s=>s?s.slice():null),
    banks:banks.map(bank=>bank.map(row=>row.map(cloneClip))) };
// DOPO
    snapshots:snapshots.map(s=>s?s.slice():null),
    banks:banks.map(bank=>bank.map(row=>row.map(cloneClip))),
    drumKit:drumKit.map(row=>row.map(cloneClip)) };
```

**`applyState`**:
```js
// PRIMA
  for(let b=0;b<NBANKS;b++)for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) banks[b][r][c]=cloneClip(state.banks[b][r][c]);
  activeBank=Math.min(Math.max(state.activeBank||0,0),NBANKS-1); clips=banks[activeBank]; updateBankUI();
// DOPO
  for(let b=0;b<NBANKS;b++)for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) banks[b][r][c]=cloneClip(state.banks[b][r][c]);
  for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) drumKit[r][c]=cloneClip(state.drumKit[r][c]);
  activeBank=Math.min(Math.max(state.activeBank||0,0),NBANKS-1); clips=banks[activeBank]; updateBankUI();
```

- [ ] **Step 4: Esegui e verifica che passi**

```
node test_perfmode_persistence.js
```
Atteso: tutti e 4 PASS.

- [ ] **Step 5: Rebuild e regressione completa**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```
Presta particolare attenzione a `test_save_load.js`, `test_multibank_save.js`, `test_autosave.js`, `test_undo.js`, `test_undo_coverage.js`.

- [ ] **Step 6: Commit**

```
cd "D:\MUSIC\Launchpad Studio"
git add "_sorgente/launchpad-studio.html"
git commit -m "Il kit Drums viene salvato/ripristinato in .lpstudio, autosave e Undo/Redo"
```

---

## Task 9: Verifica finale, documentazione, push

**Files:**
- Modify: `D:\MUSIC\Launchpad Studio\SVILUPPO.md` (§5 checklist funzioni, §8 limiti noti), `D:\MUSIC\Launchpad Studio\Manuale Launchpad Studio.html` (sezione controlli hardware/tasti superiori).
- Nessun test nuovo — questo task verifica l'insieme e aggiorna la documentazione utente/sviluppo.

- [ ] **Step 1: Rebuild finale e verifica byte-identica**

```
cd "D:\MUSIC\Launchpad Studio\_sorgente" && python assemble.py
```
Poi verifica che lo script applicativo estratto da sorgente e generato sia identico:
```
cd "D:\MUSIC\Launchpad Studio"
node -e "
const fs=require('fs');
function extract(p){ const h=fs.readFileSync(p,'utf8'); const s=h.indexOf('<script>',h.indexOf('lamejs')+1); return h.slice(s, h.indexOf('</script>', s)); }
const a=extract('_sorgente/launchpad-studio.html');
const b=extract('Launchpad Studio.html');
console.log('match:', a===b);
"
```
Atteso: `match: true`.

- [ ] **Step 2: Suite di regressione completa (vecchi + nuovi test)**

```
cd "C:\Users\panco\AppData\Local\Temp\claude\d--MUSIC-Launchpad-Studio\f54e3e52-eb9c-4bcc-a37e-2616e0913a35\scratchpad"
for f in test_*.js; do node "$f" || echo "FAIL: $f"; done
```
Atteso: nessuna riga `FAIL:`.

- [ ] **Step 3: Aggiorna `SVILUPPO.md`**

Nella sezione `## 5. Funzioni implementate (checklist)`, aggiungi in fondo al paragrafo (prima del testo che introduce la sezione 6):
```
**Modalità performance Drums/Keys**: i 4 tasti superiori Session/Drums/Keys/User (CC 95-98) hanno un ruolo dedicato — Session ferma tutto (o esce dall'overlay se attivo), Drums attiva/disattiva un kit di campioni indipendente dai banchi (`drumKit`, 8×8, colpi one-shot velocity-sensitive, LED dedicato), Keys attiva/disattiva la riproduzione del clip selezionato a intonazioni isomorfe a quarte (stile gate, tenuto premuto = suona), User fa Re-sync. I loop dei banchi continuano a suonare sotto l'overlay. Il kit Drums è salvato in `.lpstudio`/autosave/Undo come i banchi; `perfMode` (quale overlay è attivo) è stato di sessione, non salvato. Vedi `docs/superpowers/specs/2026-08-12-drums-keys-performance-modes-design.md` per la progettazione completa.
```
Nella sezione `## 9. Backlog`, aggiungi una riga:
```
14. ~~Ruolo dedicato per Session/Drums/Keys/User~~ — **fatto** (vedi §5, modalità performance Drums/Keys).
```

- [ ] **Step 4: Aggiorna il Manuale utente**

In `Manuale Launchpad Studio.html`, cerca la sezione che descrive i controlli hardware/la fila superiore del Launchpad (cerca `91-98` o `fila superiore` o "Up" nel file). Aggiungi un paragrafo che spiega in linguaggio semplice, rivolto all'utente finale:
```html
<p>La fila di 8 tasti tondi sopra la griglia: i primi 4 (Up/Down/Left/Right) fermano la colonna corrispondente. Gli altri 4 hanno un ruolo speciale — <b>Session</b> ferma tutto (o torna alla griglia normale se sei in Drums/Keys); <b>Drums</b> attiva un kit di campioni dedicato e indipendente dai tuoi banchi: ogni pad diventa un colpo singolo (batteria a dita), premi di nuovo Drums per tornare alla griglia normale; <b>Keys</b> fa suonare il pad che hai selezionato a intonazioni diverse su tutta la griglia (tenendo premuto suoni, rilasciando si ferma) — utile per bassi/synth/vocal chop suonati come una piccola tastiera; <b>User</b> riallinea tutti i loop attivi (Re-sync). Mentre sei in Drums o Keys, i loop che stai già suonando continuano tranquillamente sotto.</p>
```

- [ ] **Step 5: Commit e push**

```
cd "D:\MUSIC\Launchpad Studio"
git add SVILUPPO.md "Manuale Launchpad Studio.html" "_sorgente/launchpad-studio.html"
git commit -m "Documenta le modalita' performance Drums/Keys (Manuale + SVILUPPO.md)"
git push
```

---

## Self-Review (eseguita durante la scrittura del piano)

- **Copertura spec**: ogni sezione della spec (stato globale, comportamento tasti, comportamento griglia Drums/Keys, LED, persistenza, UI, testing) ha un task corrispondente (Task 1→stato, 2→tasti, 3→Drums, 4→Keys, 5→editor, 6→LED, 7→UI, 8→persistenza, 9→verifica/docs). Nessuna sezione della spec priva di task.
- **Placeholder**: nessun TBD/TODO; ogni step ha codice reale, non descrizioni generiche.
- **Coerenza dei nomi**: `activeGrid()`, `perfMode`, `drumKit`, `keysPitchOffset(r,c)`, `triggerDrumHit(r,c,velocity)`, `startKeysNote(r,c,velocity)`/`stopKeysNote(r,c)`, `keysSrc`, `setTopLed(index,color,mode)`, `exitPerfMode()`, `onPerfModeChanged()`, `updatePerfModeUI()` sono usati con la stessa firma in tutti i task che li referenziano (verificato incrociando Task 1↔3↔4↔5↔6↔7).
- **Nota sul Task 7**: richiede un piccolo cambiamento a `harness.js` (infrastruttura di test, non codice applicativo) per rendere `classList` stateful — è isolato e va verificato con l'intera suite prima di proseguire, come indicato nello step stesso.
