# Modifiche suono Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiunge una nuova sezione UI "Modifiche suono", separata da "Suoni & Set", con fade in/out, un controllo Tempo (rallenta/velocizza senza cambiare tono), un controllo Tono (cambia intonazione senza cambiare velocità) e un filtro passa-basso per singolo pad — mantenendo intatto tutto ciò che esiste già (incluso il vecchio Pitch accoppiato).

**Architecture:** Tempo/Tono usano un motore di time-stretch vendorizzato (SoundTouch.js, WSOLA) applicato OFFLINE (rielabora l'intero buffer quando lo slider viene rilasciato, stesso schema già usato da Reverse: `origBuffer` intatto + buffer attivo ricalcolato). Fade in/out e Filtro sono invece in tempo reale — nodi Web Audio (`GainNode` per il fade, `BiquadFilterNode` per il filtro) inseriti nella catena audio di ogni voce, con lo stesso pattern già usato per taglio/pitch live (`applyLiveTrim`/`liveClipUpdate`) per aggiornare una voce già in corso.

**Tech Stack:** JavaScript vanilla, Web Audio API, SoundTouch.js (vendorizzata, nessuna chiamata di rete a runtime). Test con l'harness Node/vm esistente.

**Spec:** `docs/superpowers/specs/2026-08-13-modifiche-suono-design.md`

## Global Constraints

- Il vecchio controllo **Pitch** (accoppiato, resampling) in "Suoni & Set" resta esattamente com'è oggi — non va toccato, rinominato, né confuso col nuovo "Tono".
- Tempo/Tono si applicano **offline**, al rilascio dello slider (`change`, non `oninput` ad ogni pixel) — mai in tempo reale durante la riproduzione.
- Fade in/out e Filtro si applicano **in tempo reale**, live-regolabili anche mentre il suono sta girando.
- Ordine di composizione del buffer quando sia time-stretch che reverse sono attivi: **prima il time-stretch, poi il reverse** (il reverse lavora sempre sul risultato del time-stretch, mai viceversa).
- Cambiare **Tempo** aggiorna `clip.sourceBpm` proporzionalmente (`sourceBpm = sourceBpmOriginale / tempoFactor`), così l'aggancio automatico del BPM (Task 1/2 del piano `2026-08-13-bpm-automatico-primo-suono.md`, già implementato) continua a calcolare correttamente. Cambiare **Tono** non tocca `sourceBpm`.
- I nuovi campi persistono con lo stesso meccanismo già esistente per trim/pitch/reverse/sourceBpm: autosave, "Salva set", "Salva modifica" per genere, "Copia/Incolla impostazioni".
- Rebuild con `python assemble.py` da `_sorgente/` dopo ogni task che tocca `_sorgente/launchpad-studio.html` o `_sorgente/assemble.py`, e verifica in Chrome vero (Playwright) prima di considerare un task concluso, come da prassi del progetto.
- I test usano l'harness Node/vm esistente in scratchpad (percorso indicato all'implementatore nel brief di ogni task). Ogni file di test va nella cartella scratchpad di sessione, mai nel repository.

---

## Task 1: Motore di time-stretch (vendorizzazione SoundTouch.js + `applyTimeStretch`)

**Files:**
- Create: `_sorgente/soundtouch-vendor.js`
- Modify: `_sorgente/assemble.py`
- Modify: `_sorgente/launchpad-studio.html`
- Test: `<scratchpad>/test_time_stretch_engine.js` (nuovo)

**Interfaces:**
- Consumes: nessuna dipendenza da task precedenti (primo task del piano).
- Produces: `async function applyTimeStretch(buffer, tempoFactor, semitones)` — riceve un `AudioBuffer` (o l'oggetto compatibile usato dall'harness, con `.sampleRate`, `.numberOfChannels`, `.getChannelData(i)`, `.duration`/`.length`), restituisce una Promise che risolve in un nuovo `AudioBuffer` elaborato. `tempoFactor` è un moltiplicatore di velocità (1 = nessuna modifica, 1.2 = 20% più veloce, 0.5 = metà velocità). `semitones` è lo spostamento di intonazione (0 = nessuna modifica). I task successivi (3, 4) chiamano solo questa funzione, non toccano mai direttamente l'API di SoundTouch.

- [ ] **Step 1: Recupera e adatta il file vendorizzato**

Scarica il contenuto di `https://unpkg.com/soundtouchjs/dist/soundtouch.js` (build ES module della libreria SoundTouch — algoritmo WSOLA per pitch/tempo indipendenti). Annota nella prima riga del file adattato la versione effettiva servita da unpkg (visibile nell'URL dopo un redirect, o nel commento di intestazione del file scaricato), per tracciabilità futura.

Il file scaricato termina con una riga tipo:
```js
export { SoundTouch, PitchShifter, Stretch, RateTransposer, SimpleFilter, WebAudioBufferSource, AbstractFifoSamplePipe, getWebAudioNode };
```

Sostituisci quella riga finale con (il resto del file, sopra, resta invariato — è codice classico, non usa `import`):
```js
window.SoundTouch = SoundTouch;
window.SimpleFilter = SimpleFilter;
window.WebAudioBufferSource = WebAudioBufferSource;
```

Salva il risultato come `_sorgente/soundtouch-vendor.js` — questo lo rende un classico `<script>` non-module, coerente col resto del progetto (che condivide lo scope tra script classici, vedi `_sorgente/genre_ui.js`).

- [ ] **Step 2: Verifica l'API reale della classe `SoundTouch` prima di scrivere il wrapper**

Crea `<scratchpad>/probe_soundtouch_api.js`:
```js
'use strict';
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('./_sorgente/soundtouch-vendor.js', 'utf8');
const sandbox = { window: {}, console };
vm.createContext(sandbox);
vm.runInContext(src, sandbox);
const proto = sandbox.window.SoundTouch.prototype;
console.log('Metodi/proprieta\' su SoundTouch.prototype:', Object.getOwnPropertyNames(proto));
const inst = new sandbox.window.SoundTouch();
console.log('Proprieta\' su un\'istanza:', Object.getOwnPropertyNames(inst));
console.log('Ha putSamples:', typeof inst.putSamples);
console.log('Ha receiveSamples:', typeof inst.receiveSamples);
console.log('Ha flush:', typeof inst.flush);
console.log('Ha tempo setter:', 'tempo' in inst || Object.getOwnPropertyDescriptor(Object.getPrototypeOf(inst),'tempo')!=null);
console.log('Ha pitchSemitones/pitch:', 'pitchSemitones' in inst, 'pitch' in inst);
```

Esegui: `node probe_soundtouch_api.js` da dentro la cartella scratchpad.

Se `putSamples`/`receiveSamples`/`flush` non esistono con questi nomi esatti, o `tempo`/`pitchSemitones` non sono proprietà impostabili, adatta lo Step 3 sotto ai nomi reali trovati qui — questo probe è la fonte di verità, non il codice di esempio nello spec (che è indicativo, scritto prima di verificare contro la libreria reale).

- [ ] **Step 3: Scrivi i test (RED)**

Crea `<scratchpad>/test_time_stretch_engine.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');
const fs = require('fs');
const SOUNDTOUCH_SRC = fs.readFileSync('./_sorgente/soundtouch-vendor.js', 'utf8');

async function testTempoFactorAboveOneShrinksDuration(){
  const sb = await runWithApp(SOUNDTOUCH_SRC + `
    ac();
    const sr=8000, dur=2, n=sr*dur;
    const data=new Float32Array(n);
    for(let i=0;i<n;i++) data[i]=Math.sin(2*Math.PI*220*i/sr)*0.5;
    const buffer=ac().createBuffer(1,n,sr);
    buffer.getChannelData(0).set(data);
    const out = await applyTimeStretch(buffer, 1.25, 0);
    globalThis.__result = { outDuration: out.duration, inDuration: buffer.duration, outSampleRate: out.sampleRate };
  `);
  const r = sb.__result;
  const expected = r.inDuration / 1.25;
  assert.ok(Math.abs(r.outDuration - expected) < expected*0.1,
    `tempoFactor=1.25 deve ridurre la durata di circa 1/1.25 (atteso ~${expected.toFixed(2)}s, ottenuto ${r.outDuration.toFixed(2)}s)`);
  assert.strictEqual(r.outSampleRate, 8000, 'il sample rate di output deve restare invariato');
}

async function testTempoFactorOneAndNoSemitonesIsNearIdentity(){
  const sb = await runWithApp(SOUNDTOUCH_SRC + `
    ac();
    const sr=8000, n=sr*1;
    const data=new Float32Array(n);
    for(let i=0;i<n;i++) data[i]=Math.sin(2*Math.PI*220*i/sr)*0.5;
    const buffer=ac().createBuffer(1,n,sr);
    buffer.getChannelData(0).set(data);
    const out = await applyTimeStretch(buffer, 1, 0);
    globalThis.__result = { outDuration: out.duration, inDuration: buffer.duration };
  `);
  const r = sb.__result;
  assert.ok(Math.abs(r.outDuration - r.inDuration) < r.inDuration*0.1,
    `tempoFactor=1, semitones=0 deve restituire un buffer di durata quasi identica, atteso ~${r.inDuration}s ottenuto ${r.outDuration}s`);
}

async function testPitchOnlyShiftKeepsDurationRoughlyStable(){
  const sb = await runWithApp(SOUNDTOUCH_SRC + `
    ac();
    const sr=8000, n=sr*1;
    const data=new Float32Array(n);
    for(let i=0;i<n;i++) data[i]=Math.sin(2*Math.PI*220*i/sr)*0.5;
    const buffer=ac().createBuffer(1,n,sr);
    buffer.getChannelData(0).set(data);
    const out = await applyTimeStretch(buffer, 1, 7);
    globalThis.__result = { outDuration: out.duration, inDuration: buffer.duration };
  `);
  const r = sb.__result;
  assert.ok(Math.abs(r.outDuration - r.inDuration) < r.inDuration*0.15,
    `spostare solo il tono (semitones=7, tempoFactor=1) non deve cambiare sostanzialmente la durata, atteso ~${r.inDuration}s ottenuto ${r.outDuration}s`);
}

async function testStereoChannelCountPreserved(){
  const sb = await runWithApp(SOUNDTOUCH_SRC + `
    ac();
    const sr=8000, n=sr*1;
    const buffer=ac().createBuffer(2,n,sr);
    for(let ch=0;ch<2;ch++){ const d=buffer.getChannelData(ch); for(let i=0;i<n;i++) d[i]=Math.sin(2*Math.PI*220*i/sr)*0.5; }
    const out = await applyTimeStretch(buffer, 1.1, 0);
    globalThis.__result = { outChannels: out.numberOfChannels };
  `);
  assert.strictEqual(sb.__result.outChannels, 2, 'un buffer stereo in ingresso deve restare stereo in uscita');
}

(async () => {
  const tests = [
    ['tempoFactor>1 riduce la durata proporzionalmente', testTempoFactorAboveOneShrinksDuration],
    ['tempoFactor=1 e semitones=0 e\' quasi un\'identita\'', testTempoFactorOneAndNoSemitonesIsNearIdentity],
    ['cambiare solo il tono non cambia sostanzialmente la durata', testPitchOnlyShiftKeepsDurationRoughlyStable],
    ['un buffer stereo resta stereo', testStereoChannelCountPreserved],
  ];
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('PASS -', name); }
    catch (e) { failed++; console.log('FAIL -', name, '\n     ', e.message); }
  }
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 4: Esegui i test e verifica che falliscano (RED)**

Run: `node test_time_stretch_engine.js` da dentro la cartella scratchpad.
Expected: tutti e 4 i test FALLISCONO — `applyTimeStretch is not defined`.

- [ ] **Step 5: Scrivi `applyTimeStretch`**

In `_sorgente/launchpad-studio.html`, aggiungi questa funzione subito dopo `function reversedBuffer(buf){...}` (riga 1158-1159 nello stato attuale del file):

```js
// Time-stretch offline via SoundTouch.js (vendorizzata in soundtouch-vendor.js, iniettata da
// assemble.py). tempoFactor: 1=nessuna modifica, >1 piu' veloce, <1 piu' lento. semitones:
// spostamento di intonazione indipendente dalla velocita'. Interleaccia i canali (SoundTouch
// si aspetta un unico stream interleaved), elabora, poi de-interleaccia nel nuovo AudioBuffer.
async function applyTimeStretch(buffer, tempoFactor, semitones){
  const st = new SoundTouch();
  st.tempo = tempoFactor;
  st.pitchSemitones = semitones;
  const nCh = buffer.numberOfChannels, len = buffer.length, sr = buffer.sampleRate;
  const chans = []; for(let ch=0; ch<nCh; ch++) chans.push(buffer.getChannelData(ch));
  const interleaved = new Float32Array(len*2);   // SoundTouch lavora sempre in coppie (mono duplicato se serve)
  for(let i=0;i<len;i++){ interleaved[i*2]=chans[0][i]; interleaved[i*2+1]=(nCh>1?chans[1][i]:chans[0][i]); }
  st.putSamples(interleaved);
  st.flush();
  const outChunks = []; let total = 0;
  const chunk = new Float32Array(4096*2);
  let got;
  while((got = st.receiveSamples(chunk, 4096)) > 0){ outChunks.push(chunk.slice(0, got*2)); total += got; }
  const outLen = Math.max(1, total);
  const out = ac().createBuffer(nCh, outLen, sr);
  const outL = out.getChannelData(0), outR = nCh>1 ? out.getChannelData(1) : null;
  let pos = 0;
  for(const part of outChunks){ const n = part.length/2;
    for(let i=0;i<n;i++){ outL[pos+i]=part[i*2]; if(outR) outR[pos+i]=part[i*2+1]; }
    pos += n; }
  return out;
}
```

Se lo Step 2 ha trovato nomi diversi da `putSamples`/`receiveSamples`/`flush`/`tempo`/`pitchSemitones` sull'istanza reale, sostituiscili qui coi nomi reali prima di procedere.

- [ ] **Step 6: Aggiungi `soundtouch-vendor.js` all'assemblaggio**

In `_sorgente/assemble.py`, la funzione `main()` inizia con:
```python
for p in (SRC, DATA, UI, DKDATA, DKUI, CATUI):
    if not p.exists():
        sys.exit(f"ERRORE: manca {p.name} in {HERE}")
```

Aggiungi la nuova costante subito dopo `CATUI = HERE / "catalog_ui.js"`:
```python
SOUNDTOUCH = HERE / "soundtouch-vendor.js"
```

Aggiungi `SOUNDTOUCH` alla tupla di verifica esistenza:
```python
for p in (SRC, DATA, UI, DKDATA, DKUI, CATUI, SOUNDTOUCH):
```

Nel blocco che legge i file (`ui = UI.read_text(...)` ecc.), aggiungi:
```python
soundtouch = SOUNDTOUCH.read_text(encoding="utf-8")
```

Nel blocco che costruisce `block` (dove si concatenano `ui`, `dkui`, `catui`), inserisci `soundtouch` **prima** di `ui` (deve essere disponibile prima che qualunque altro script lo usi, anche se in pratica nessuno degli script iniettati lo chiama direttamente — solo `launchpad-studio.html` lo fa):
```python
block = ("\n<script>\nconst GENRES = " + data_text + ";\n" + soundtouch.rstrip() + "\n" + ui.rstrip()
         + "\nconst DRUM_KIT_PRESET = " + drumkit_text + ";\n" + dkui.rstrip()
         + "\n" + catui.rstrip()
         + "\n</script>\n\n")
```

- [ ] **Step 7: Esegui i test e verifica che passino (GREEN)**

Run: `node test_time_stretch_engine.js`
Expected: tutti e 4 i test PASS. Se un test fallisce per una discrepanza dell'API (non per un errore di logica), torna allo Step 2/5 e correggi i nomi dei metodi.

- [ ] **Step 8: Rebuild e regressione**

Da dentro `_sorgente/`: `python assemble.py`
Esegui l'intera suite di test esistente nella cartella scratchpad (`node run_all_tests.js`) per assicurarti che nessuna regressione sia stata introdotta.

- [ ] **Step 9: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "_sorgente/assemble.py" "_sorgente/soundtouch-vendor.js"
git commit -m "$(cat <<'EOF'
Vendorizza SoundTouch.js e aggiunge applyTimeStretch (motore time-stretch)

Base per Tempo/Tono indipendenti: elaborazione offline via WSOLA,
buffer in ingresso mai modificato, nuovo AudioBuffer in uscita.
Nessun collegamento ancora alla UI (task successivi).
EOF
)"
```

---

## Task 2: Nuova sezione UI "Modifiche suono" + Fade in/out

**Files:**
- Modify: `_sorgente/launchpad-studio.html`
- Test: `<scratchpad>/test_pad_fade.js` (nuovo)

**Interfaces:**
- Consumes: nessuna dipendenza diretta dal Task 1 (fade è indipendente dal time-stretch).
- Produces: sezione HTML `#secModificheSuono` con i controlli `#clipFadeIn`, `#clipFadeOut` (e placeholder per Tempo/Tono/Filtro che i Task 3-4 riempiono), campi `clip.fadeIn`/`clip.fadeOut` (secondi, default 0). I task successivi aggiungono controlli DENTRO questa stessa sezione, non ne creano una nuova.

- [ ] **Step 1: Scrivi i test (RED)**

Crea `<scratchpad>/test_pad_fade.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testPlayOnceAppliesFadeIn(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'X', mode:'oneshot', fadeIn:0.3, trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    playOnce(0,0);
    globalThis.__result = { calls: oneShotVoice.g.gain.calls.map(c=>c[0]+':'+c[1]+':'+c[2]) };
  `);
  const calls = sb.__result.calls;
  assert.ok(calls.some(c => c.startsWith('linearRampToValueAtTime') && c.endsWith(':0.3')),
    `un fadeIn di 0.3s deve pianificare una rampa che arriva al volume target a +0.3s dall'avvio, trovato ${JSON.stringify(calls)}`);
}

async function testPlayOnceWithoutFadeInUsesDefaultClickGuard(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'X', mode:'oneshot', trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    playOnce(0,0);
    globalThis.__result = { calls: oneShotVoice.g.gain.calls.map(c=>c[0]+':'+c[1]+':'+c[2]) };
  `);
  const calls = sb.__result.calls;
  assert.ok(calls.some(c => c.startsWith('linearRampToValueAtTime') && c.endsWith(':0.005')),
    `senza fadeIn impostato deve restare il guardrail anti-click di 5ms gia\' esistente, trovato ${JSON.stringify(calls)}`);
}

async function testStopTrackClipAppliesFadeOut(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'X', mode:'loop', fadeOut:0.4, trimStart:0, trimEnd:null };
    scheduleClip(0,0, now());
    await new Promise(res=>setTimeout(res,15));
    const g = trackState[0].g;
    stopTrackClip(0, true);
    globalThis.__result = { calls: g.calls.map(c=>c[0]+':'+c[1]+':'+c[2]) };
  `);
  const calls = sb.__result.calls;
  assert.ok(calls.some(c => c.startsWith('linearRampToValueAtTime') && c.endsWith(':0.4')),
    `stopTrackClip con fadeOut=0.4 sul clip in play deve pianificare la rampa a 0 a +0.4s, trovato ${JSON.stringify(calls)}`);
}

async function testGateFadeOutUsesClipValue(){
  const sb = await runWithApp(`
    ac();
    clips[1][1] = { buffer:{duration:2}, name:'Gate', mode:'gate', fadeOut:0.25, trimStart:0, trimEnd:null };
    selected = { r:1, c:1 };
    startGate(1,1);
    const g = gateSrc[1*8+1].g;
    stopGate(1,1);
    globalThis.__result = { calls: g.calls.map(c=>c[0]+':'+c[1]+':'+c[2]) };
  `);
  const calls = sb.__result.calls;
  assert.ok(calls.some(c => c.startsWith('linearRampToValueAtTime') && c.endsWith(':0.25')),
    `stopGate con fadeOut=0.25 deve pianificare la rampa a 0 a +0.25s, trovato ${JSON.stringify(calls)}`);
}

async function testGateWithoutFadeOutUsesDefaultGuard(){
  const sb = await runWithApp(`
    ac();
    clips[1][1] = { buffer:{duration:2}, name:'Gate', mode:'gate', trimStart:0, trimEnd:null };
    selected = { r:1, c:1 };
    startGate(1,1);
    const g = gateSrc[1*8+1].g;
    stopGate(1,1);
    globalThis.__result = { calls: g.calls.map(c=>c[0]+':'+c[1]+':'+c[2]) };
  `);
  const calls = sb.__result.calls;
  assert.ok(calls.some(c => c.startsWith('linearRampToValueAtTime') && c.endsWith(':0.006')),
    `senza fadeOut impostato deve restare il guardrail di 6ms gia\' esistente, trovato ${JSON.stringify(calls)}`);
}

(async () => {
  const tests = [
    ['playOnce applica il fadeIn del clip', testPlayOnceAppliesFadeIn],
    ['playOnce senza fadeIn usa il guardrail anti-click di default', testPlayOnceWithoutFadeInUsesDefaultClickGuard],
    ['stopTrackClip applica il fadeOut del clip', testStopTrackClipAppliesFadeOut],
    ['stopGate applica il fadeOut del clip', testGateFadeOutUsesClipValue],
    ['stopGate senza fadeOut usa il guardrail di default', testGateWithoutFadeOutUsesDefaultGuard],
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

Run: `node test_pad_fade.js`
Expected: `testPlayOnceAppliesFadeIn`, `testStopTrackClipAppliesFadeOut` e `testGateFadeOutUsesClipValue` FALLISCONO (il fade dura sempre 0.005/0.006 fissi, mai il valore del clip). Gli altri due passano già oggi (comportamento di default preesistente) — confermalo comunque per avere una baseline chiara.

- [ ] **Step 3: Aggiungi la sezione HTML**

In `_sorgente/launchpad-studio.html`, subito dopo la riga 210 (`</details>` che chiude "Suoni & Set") e prima della riga 212 (`<div class="divider"></div>`), inserisci:

```html
      <details class="sec-details" open>
      <summary>Modifiche suono</summary>
      <div class="row" style="font-size:12px">
        <label>Fade in</label><input type="range" id="clipFadeIn" min="0" max="2" step="0.01" value="0" style="flex:1;min-width:60px;accent-color:var(--accent)"><span id="clipFadeInVal" style="color:var(--dim)">0.00s</span>
      </div>
      <div class="row" style="font-size:12px">
        <label>Fade out</label><input type="range" id="clipFadeOut" min="0" max="2" step="0.01" value="0" style="flex:1;min-width:60px;accent-color:var(--accent)"><span id="clipFadeOutVal" style="color:var(--dim)">0.00s</span>
      </div>
      </details>
```

(I Task 3 e 4 aggiungono altri controlli DENTRO questo stesso blocco `<details>`, subito dopo il fade out — non creano una nuova sezione.)

- [ ] **Step 4: Aggiorna `selectPad` per mostrare fadeIn/fadeOut**

In `_sorgente/launchpad-studio.html`, riga 1090 (`const csb=document.getElementById('clipSourceBpm'); if(csb) csb.value=(cl&&cl.sourceBpm)||'';`), aggiungi subito dopo:

```js
  const cfi=document.getElementById('clipFadeIn'); if(cfi){ cfi.value=(cl&&cl.fadeIn)||0; document.getElementById('clipFadeInVal').textContent=((cl&&cl.fadeIn)||0).toFixed(2)+'s'; }
  const cfo=document.getElementById('clipFadeOut'); if(cfo){ cfo.value=(cl&&cl.fadeOut)||0; document.getElementById('clipFadeOutVal').textContent=((cl&&cl.fadeOut)||0).toFixed(2)+'s'; }
```

- [ ] **Step 5: Aggiungi gli handler dei due slider**

In `_sorgente/launchpad-studio.html`, subito dopo la riga con l'handler `clipSourceBpm.addEventListener('pointerdown',...)` (riga 1194: `document.getElementById('clipSourceBpm').addEventListener('pointerdown',()=>pushUndo());`), aggiungi:

```js
document.getElementById('clipFadeIn').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  cl.fadeIn=+e.target.value; document.getElementById('clipFadeInVal').textContent=cl.fadeIn.toFixed(2)+'s'; };
document.getElementById('clipFadeIn').addEventListener('pointerdown',()=>pushUndo());
document.getElementById('clipFadeOut').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  cl.fadeOut=+e.target.value; document.getElementById('clipFadeOutVal').textContent=cl.fadeOut.toFixed(2)+'s'; };
document.getElementById('clipFadeOut').addEventListener('pointerdown',()=>pushUndo());
```

- [ ] **Step 6: Applica il fadeIn in `playOnce` e `triggerDrumHit`**

In `_sorgente/launchpad-studio.html`, riga 1403 (dentro `playOnce`):
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+0.005);
```
sostituisci con:
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+Math.max(0.005,clip.fadeIn||0));
```

Riga 1383 (dentro `triggerDrumHit`, stessa espressione):
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip)*vel,now()+0.005);
```
sostituisci con:
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip)*vel,now()+Math.max(0.005,clip.fadeIn||0));
```

- [ ] **Step 7: Applica il fadeIn in `startGate` e `scheduleClip`**

Riga 1503 (dentro `startGate`):
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+0.005);
```
sostituisci con:
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+Math.max(0.005,clip.fadeIn||0));
```

Riga 1533 (dentro `scheduleClip`):
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,when); g.gain.linearRampToValueAtTime(gainFor(clip),when+F);
```
sostituisci con:
```js
  const g=ac().createGain(); g.gain.setValueAtTime(0,when); g.gain.linearRampToValueAtTime(gainFor(clip),when+Math.max(F,clip.fadeIn||0));
```

- [ ] **Step 8: Applica il fadeOut in `stopGate` e `stopTrackClipAt`**

Riga 1513 (dentro `stopGate`):
```js
  if(o){ const t=now(); try{ o.g.gain.setValueAtTime(o.g.gain.value,t); o.g.gain.linearRampToValueAtTime(0,t+0.006); o.src.stop(t+0.02);}catch(e){} delete gateSrc[k]; }
```
sostituisci con:
```js
  if(o){ const t=now(); const clip=clips[r][c]; const fo=Math.max(0.006,(clip&&clip.fadeOut)||0); try{ o.g.gain.setValueAtTime(o.g.gain.value,t); o.g.gain.linearRampToValueAtTime(0,t+fo); o.src.stop(t+fo+0.014);}catch(e){} delete gateSrc[k]; }
```

Riga 1547 (dentro `stopTrackClipAt`):
```js
function stopTrackClipAt(c,t){
  const ts=trackState[c]; const F=0.006;
  if(ts.src){ try{ if(ts.g){ ts.g.gain.setValueAtTime(ts.g.gain.value,t); ts.g.gain.linearRampToValueAtTime(0,t+F);} ts.src.stop(t+F+0.006);}catch(e){} }
```
sostituisci con:
```js
function stopTrackClipAt(c,t){
  const ts=trackState[c]; const F=0.006;
  if(ts.src){ const pr=ts.playingRow; const clip=(pr!=null)?clips[pr][c]:null; const fo=Math.max(F,(clip&&clip.fadeOut)||0);
    try{ if(ts.g){ ts.g.gain.setValueAtTime(ts.g.gain.value,t); ts.g.gain.linearRampToValueAtTime(0,t+fo);} ts.src.stop(t+fo+0.006);}catch(e){} }
```

(`triggerDrumHit`/`playOnce` non hanno bisogno di un fadeOut esplicito allo stop: già suonano fino alla fine naturale del taglio; `stopOneShotVoice`/`stopDrumVoice` restano col loro fade fisso di 6ms, che si applica solo quando la voce viene interrotta anzitempo — es. da un choke o da un nuovo taglio in corso — non è il fadeOut "musicale" di questa sezione, è un guardrail anti-click sull'interruzione forzata.)

- [ ] **Step 9: Esegui i test e verifica che passino (GREEN)**

Run: `node test_pad_fade.js`
Expected: tutti e 5 i test PASS.

- [ ] **Step 10: Rebuild, regressione, Chrome vero**

`python assemble.py` da `_sorgente/`, poi `node run_all_tests.js`. Verifica in Chrome vero: la nuova sezione "Modifiche suono" appare subito sotto "Suoni & Set", è collassabile come le altre; un pad con fadeIn/fadeOut impostati suona percettibilmente con un'entrata/uscita morbida invece che a scatto.

- [ ] **Step 11: Commit**

```bash
git add "_sorgente/launchpad-studio.html"
git commit -m "$(cat <<'EOF'
Nuova sezione "Modifiche suono": fade in/out per pad

Fade in su playOnce/triggerDrumHit/startGate/scheduleClip, fade out
su stopGate/stopTrackClipAt — sostituiscono il guardrail anti-click
fisso quando il clip ha un valore esplicito, restano 5-6ms altrimenti.
EOF
)"
```

---

## Task 3: Filtro per singolo pad (tempo reale)

**Files:**
- Modify: `_sorgente/launchpad-studio.html`
- Test: `<scratchpad>/test_pad_filter.js` (nuovo)

**Interfaces:**
- Consumes: la sezione "Modifiche suono" del Task 2 (aggiunge un controllo dentro lo stesso `<details>`).
- Produces: `clip.filterCutoff` (0-1, default 1 = nessun filtro/pieno spettro), un `BiquadFilterNode` inserito nella catena audio di ogni voce (`src -> filterNode -> g -> trackGains[c]`), funzione `function applyLiveFilter(r,c,cl)` che aggiorna la frequenza del filtro di una voce già in corso — stesso pattern di `applyLiveTrim`.

- [ ] **Step 1: Scrivi i test (RED)**

Crea `<scratchpad>/test_pad_filter.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

async function testPlayOnceInsertsFilterNodeWithCutoff(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'X', mode:'oneshot', filterCutoff:0.3, trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    playOnce(0,0);
    globalThis.__result = { hasFilterNode: !!oneShotVoice.filterNode, freq: oneShotVoice.filterNode ? oneShotVoice.filterNode.frequency.value : null, expected: 20*Math.pow(1000,0.3) };
  `);
  const r = sb.__result;
  assert.strictEqual(r.hasFilterNode, true, 'una voce one-shot deve avere un BiquadFilterNode nella propria catena');
  assert.ok(Math.abs(r.freq - r.expected) < 1, `la frequenza di taglio deve seguire la stessa curva del filtro master, atteso ${r.expected} ottenuto ${r.freq}`);
}

async function testDefaultFilterCutoffIsFullyOpen(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'X', mode:'oneshot', trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    playOnce(0,0);
    globalThis.__result = { freq: oneShotVoice.filterNode.frequency.value, expected: 20*Math.pow(1000,1) };
  `);
  const r = sb.__result;
  assert.ok(Math.abs(r.freq - r.expected) < 1, `senza filterCutoff impostato il filtro deve restare completamente aperto (20kHz), atteso ${r.expected} ottenuto ${r.freq}`);
}

async function testApplyLiveFilterUpdatesPlayingLoop(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'A', mode:'loop', filterCutoff:1, trimStart:0, trimEnd:null };
    scheduleClip(0,0, now());
    await new Promise(res=>setTimeout(res,15));
    clips[0][0].filterCutoff = 0.2;
    applyLiveFilter(0,0,clips[0][0]);
    globalThis.__result = { freq: trackState[0].filterNode.frequency.value, expected: 20*Math.pow(1000,0.2) };
  `);
  const r = sb.__result;
  assert.ok(Math.abs(r.freq - r.expected) < 1, `applyLiveFilter deve aggiornare subito il filtro di un loop gia\' in corso, atteso ${r.expected} ottenuto ${r.freq}`);
}

async function testFilterSliderUpdatesLiveWhileGatePlaying(){
  const sb = await runWithApp(`
    ac();
    clips[1][1] = { buffer:{duration:2}, name:'Gate', mode:'gate', filterCutoff:1, trimStart:0, trimEnd:null };
    selected = { r:1, c:1 };
    startGate(1,1);
    document.getElementById('clipFilter').oninput({ target:{ value:'0.5' } });
    globalThis.__result = { freq: gateSrc[1*8+1].filterNode.frequency.value, expected: 20*Math.pow(1000,0.5), clipVal: clips[1][1].filterCutoff };
  `);
  const r = sb.__result;
  assert.strictEqual(r.clipVal, 0.5, 'muovere lo slider deve aggiornare clip.filterCutoff');
  assert.ok(Math.abs(r.freq - r.expected) < 1, `muovere lo slider Filtro mentre un gate e\' tenuto premuto deve aggiornare subito il filtro reale, atteso ${r.expected} ottenuto ${r.freq}`);
}

(async () => {
  const tests = [
    ['playOnce inserisce un BiquadFilterNode con la frequenza del clip', testPlayOnceInsertsFilterNodeWithCutoff],
    ['senza filterCutoff il filtro resta completamente aperto', testDefaultFilterCutoffIsFullyOpen],
    ['applyLiveFilter aggiorna un loop gia\' in corso', testApplyLiveFilterUpdatesPlayingLoop],
    ['lo slider Filtro aggiorna live un gate tenuto premuto', testFilterSliderUpdatesLiveWhileGatePlaying],
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

Run: `node test_pad_filter.js`
Expected: tutti e 4 FALLISCONO — `filterNode`/`applyLiveFilter`/`#clipFilter` non esistono ancora.

- [ ] **Step 3: Aggiungi il controllo HTML**

In `_sorgente/launchpad-studio.html`, dentro la sezione "Modifiche suono" creata nel Task 2, subito dopo il blocco del Fade out (prima del tag di chiusura `</details>` di quella sezione), aggiungi:

```html
      <div class="row" style="font-size:12px">
        <label>Filtro</label><input type="range" id="clipFilter" min="0" max="1" step="0.01" value="1" style="flex:1;min-width:60px;accent-color:var(--accent)">
      </div>
```

- [ ] **Step 4: Aggiungi `applyLiveFilter` e la funzione di frequenza condivisa**

In `_sorgente/launchpad-studio.html`, subito dopo `applyLiveTrim` (la sua chiusura è alla riga 1060, prima della riga vuota che precede `document.getElementById('clipTrimStart').oninput=...`), aggiungi:

```js
// Stessa curva di frequenza gia' usata dal filtro master (20*Math.pow(1000,x), x 0-1), applicata
// pero' al singolo pad. Aggiorna live il BiquadFilterNode di una voce gia' in corso, stesso schema
// di applyLiveTrim per taglio inizio/fine.
function filterFreqFor(clip){ const v=(clip&&clip.filterCutoff!=null)?clip.filterCutoff:1; return 20*Math.pow(1000,v); }
function applyLiveFilter(r,c,cl){
  const freq = filterFreqFor(cl);
  const ts=trackState[c];
  if(ts && ts.playingRow===r && ts.filterNode){ ts.filterNode.frequency.setTargetAtTime(freq,audioCtx.currentTime,0.02); return; }
  const gt=gateSrc[r*8+c];
  if(gt && gt.filterNode){ gt.filterNode.frequency.setTargetAtTime(freq,audioCtx.currentTime,0.02); return; }
  if(oneShotVoice && oneShotVoice.r===r && oneShotVoice.c===c && oneShotVoice.filterNode) oneShotVoice.filterNode.frequency.setTargetAtTime(freq,audioCtx.currentTime,0.02);
  if(drumVoice && drumVoice.r===r && drumVoice.c===c && drumVoice.filterNode) drumVoice.filterNode.frequency.setTargetAtTime(freq,audioCtx.currentTime,0.02);
}
```

- [ ] **Step 5: Aggiungi l'handler dello slider**

In `_sorgente/launchpad-studio.html`, subito dopo l'handler `clipFadeOut` aggiunto nel Task 2 (`document.getElementById('clipFadeOut').addEventListener('pointerdown',()=>pushUndo());`), aggiungi:

```js
document.getElementById('clipFilter').oninput=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  cl.filterCutoff=+e.target.value; applyLiveFilter(r,c,cl); };
document.getElementById('clipFilter').addEventListener('pointerdown',()=>pushUndo());
```

- [ ] **Step 6: Aggiorna `selectPad` per mostrare il filtro**

Subito dopo le righe di `clipFadeIn`/`clipFadeOut` aggiunte nel Task 2 dentro `selectPad`, aggiungi:

```js
  const cfl=document.getElementById('clipFilter'); if(cfl) cfl.value=(cl&&cl.filterCutoff!=null)?cl.filterCutoff:1;
```

- [ ] **Step 7: Inserisci il `BiquadFilterNode` nella catena audio delle 4 funzioni di trigger**

Riga 1381 (dentro `triggerDrumHit`), sostituisci:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=false; src.playbackRate.value=rateFor(clip);
  const vel=Math.max(0,Math.min(1,(velocity!=null?velocity:127)/127));
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip)*vel,now()+Math.max(0.005,clip.fadeIn||0));
  src.connect(g).connect(trackGains[c]); src.start(now(),tS,tE-tS); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'oneshot'});
  oneShots.push(src); src.onended=()=>{ oneShots=oneShots.filter(s=>s!==src); if(drumVoice&&drumVoice.src===src) drumVoice=null; };
  drumVoice={src,g,r,c};
```
con:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=false; src.playbackRate.value=rateFor(clip);
  const vel=Math.max(0,Math.min(1,(velocity!=null?velocity:127)/127));
  const filterNode=ac().createBiquadFilter(); filterNode.type='lowpass'; filterNode.frequency.value=filterFreqFor(clip); filterNode.Q.value=0.9;
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip)*vel,now()+Math.max(0.005,clip.fadeIn||0));
  src.connect(filterNode).connect(g).connect(trackGains[c]); src.start(now(),tS,tE-tS); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'oneshot'});
  oneShots.push(src); src.onended=()=>{ oneShots=oneShots.filter(s=>s!==src); if(drumVoice&&drumVoice.src===src) drumVoice=null; };
  drumVoice={src,g,filterNode,r,c};
```

Riga 1402 (dentro `playOnce`), sostituisci:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=false; src.playbackRate.value=rateFor(clip);
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+Math.max(0.005,clip.fadeIn||0));
  src.connect(g).connect(trackGains[c]); src.start(now(),tS,tE-tS); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'oneshot'});
  oneShots.push(src); src.onended=()=>{ oneShots=oneShots.filter(s=>s!==src); if(oneShotVoice&&oneShotVoice.src===src) oneShotVoice=null; };
  oneShotVoice={src,g,r,c};
```
con:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=false; src.playbackRate.value=rateFor(clip);
  const filterNode=ac().createBiquadFilter(); filterNode.type='lowpass'; filterNode.frequency.value=filterFreqFor(clip); filterNode.Q.value=0.9;
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+Math.max(0.005,clip.fadeIn||0));
  src.connect(filterNode).connect(g).connect(trackGains[c]); src.start(now(),tS,tE-tS); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'oneshot'});
  oneShots.push(src); src.onended=()=>{ oneShots=oneShots.filter(s=>s!==src); if(oneShotVoice&&oneShotVoice.src===src) oneShotVoice=null; };
  oneShotVoice={src,g,filterNode,r,c};
```

Riga 1502 (dentro `startGate`), sostituisci:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=true; src.loopStart=tS; src.loopEnd=tE; src.playbackRate.value=rateFor(clip);
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+Math.max(0.005,clip.fadeIn||0));
  src.connect(g).connect(trackGains[c]);
```
con:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=true; src.loopStart=tS; src.loopEnd=tE; src.playbackRate.value=rateFor(clip);
  const filterNode=ac().createBiquadFilter(); filterNode.type='lowpass'; filterNode.frequency.value=filterFreqFor(clip); filterNode.Q.value=0.9;
  const g=ac().createGain(); g.gain.setValueAtTime(0,now()); g.gain.linearRampToValueAtTime(gainFor(clip),now()+Math.max(0.005,clip.fadeIn||0));
  src.connect(filterNode).connect(g).connect(trackGains[c]);
```
e più sotto nella stessa funzione, sostituisci:
```js
  src.start(now(), goff); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'gate'});
  gateSrc[r*8+c]={src,g};
```
con:
```js
  src.start(now(), goff); applyChoke(clip,src,g,now(),{col:c,row:r,kind:'gate'});
  gateSrc[r*8+c]={src,g,filterNode};
```

Riga 1532 (dentro `scheduleClip`), sostituisci:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=true; src.loopStart=tS; src.loopEnd=tE; src.playbackRate.value=rateFor(clip);
  const g=ac().createGain(); g.gain.setValueAtTime(0,when); g.gain.linearRampToValueAtTime(gainFor(clip),when+Math.max(F,clip.fadeIn||0));
  src.connect(g).connect(trackGains[c]);
```
con:
```js
  const src=ac().createBufferSource(); src.buffer=clip.buffer; src.loop=true; src.loopStart=tS; src.loopEnd=tE; src.playbackRate.value=rateFor(clip);
  const filterNode=ac().createBiquadFilter(); filterNode.type='lowpass'; filterNode.frequency.value=filterFreqFor(clip); filterNode.Q.value=0.9;
  const g=ac().createGain(); g.gain.setValueAtTime(0,when); g.gain.linearRampToValueAtTime(gainFor(clip),when+Math.max(F,clip.fadeIn||0));
  src.connect(filterNode).connect(g).connect(trackGains[c]);
```
e più sotto nella stessa funzione, sostituisci:
```js
  src.start(when, offset); applyChoke(clip,src,g,when,{col:c,row:r,kind:'loop'}); ts.src=src; ts.g=g;
```
con:
```js
  src.start(when, offset); applyChoke(clip,src,g,when,{col:c,row:r,kind:'loop'}); ts.src=src; ts.g=g; ts.filterNode=filterNode;
```

- [ ] **Step 8: Esegui i test e verifica che passino (GREEN)**

Run: `node test_pad_filter.js`
Expected: tutti e 4 PASS.

- [ ] **Step 9: Rebuild, regressione, Chrome vero**

`python assemble.py`, poi `node run_all_tests.js`. Verifica in Chrome vero: abbassare il knob Filtro su un pad in riproduzione lo rende percettibilmente più ovattato, senza toccare gli altri pad né il filtro master.

- [ ] **Step 10: Commit**

```bash
git add "_sorgente/launchpad-studio.html"
git commit -m "$(cat <<'EOF'
Filtro passa-basso per singolo pad, in tempo reale

BiquadFilterNode inserito nella catena audio di ogni voce (src ->
filterNode -> g -> trackGains), stessa curva di frequenza del filtro
master. applyLiveFilter aggiorna una voce gia' in corso, stesso
schema di applyLiveTrim.
EOF
)"
```

---

## Task 4: Tempo e Tono indipendenti (integrazione col motore + BPM automatico)

**Files:**
- Modify: `_sorgente/launchpad-studio.html`
- Test: `<scratchpad>/test_pad_tempo_tone.js` (nuovo)

**Interfaces:**
- Consumes: `applyTimeStretch(buffer, tempoFactor, semitones)` (Task 1), la sezione "Modifiche suono" (Task 2/3, aggiunge due controlli in più nello stesso `<details>`).
- Produces: `clip.tempoStretch` (default 1), `clip.toneShift` (default 0 semitoni), `clip.sourceBpmOriginale` (il sourceBpm prima di qualunque Tempo manuale — creato la prima volta che Tempo viene toccato), funzione `async function rebuildProcessedBuffer(cl)` che ricalcola `cl.buffer` da `cl.origBuffer` applicando time-stretch poi reverse — sostituisce la logica ad-hoc oggi dentro `clipRev.onchange` e `pasteClipBtn.onclick`.

- [ ] **Step 1: Scrivi i test (RED)**

Crea `<scratchpad>/test_pad_tempo_tone.js`:
```js
'use strict';
const assert = require('assert');
const { runWithApp } = require('./harness.js');

function makeSynthBuffer(){
  return `
    const sr=8000, n=sr*1;
    const data=new Float32Array(n);
    for(let i=0;i<n;i++) data[i]=Math.sin(2*Math.PI*220*i/sr)*0.5;
    const buffer=ac().createBuffer(1,n,sr);
    buffer.getChannelData(0).set(data);
  `;
}

async function testChangingTempoUpdatesSourceBpmProportionally(){
  const sb = await runWithApp(makeSynthBuffer() + `
    clips[0][0] = { buffer, origBuffer:buffer, name:'X', mode:'loop', sourceBpm:120, tempoStretch:1, toneShift:0, trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    document.getElementById('clipTempo').value = '1.2';
    await document.getElementById('clipTempo').onchange({ target: document.getElementById('clipTempo') });
    globalThis.__result = { sourceBpm: clips[0][0].sourceBpm, sourceBpmOriginale: clips[0][0].sourceBpmOriginale };
  `);
  const r = sb.__result;
  assert.strictEqual(r.sourceBpmOriginale, 120, 'la prima volta che Tempo cambia deve salvare il sourceBpm originale per poterlo ripristinare');
  assert.ok(Math.abs(r.sourceBpm - 120/1.2) < 0.5, `sourceBpm deve aggiornarsi a sourceBpmOriginale/tempoFactor (120/1.2=100), ottenuto ${r.sourceBpm}`);
}

async function testResettingTempoToOneRestoresOriginalSourceBpm(){
  const sb = await runWithApp(makeSynthBuffer() + `
    clips[0][0] = { buffer, origBuffer:buffer, name:'X', mode:'loop', sourceBpm:120, tempoStretch:1, toneShift:0, trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    document.getElementById('clipTempo').value = '1.2';
    await document.getElementById('clipTempo').onchange({ target: document.getElementById('clipTempo') });
    document.getElementById('clipTempo').value = '1';
    await document.getElementById('clipTempo').onchange({ target: document.getElementById('clipTempo') });
    globalThis.__result = { sourceBpm: clips[0][0].sourceBpm };
  `);
  assert.strictEqual(sb.__result.sourceBpm, 120, 'riportare Tempo a 1 (nessuna modifica) deve ripristinare il sourceBpm originale');
}

async function testChangingToneDoesNotTouchSourceBpm(){
  const sb = await runWithApp(makeSynthBuffer() + `
    clips[0][0] = { buffer, origBuffer:buffer, name:'X', mode:'loop', sourceBpm:120, tempoStretch:1, toneShift:0, trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    document.getElementById('clipTone').value = '5';
    await document.getElementById('clipTone').onchange({ target: document.getElementById('clipTone') });
    globalThis.__result = { sourceBpm: clips[0][0].sourceBpm, toneShift: clips[0][0].toneShift };
  `);
  const r = sb.__result;
  assert.strictEqual(r.sourceBpm, 120, 'cambiare Tono non deve mai toccare sourceBpm');
  assert.strictEqual(r.toneShift, 5);
}

async function testRebuildProcessedBufferAppliesStretchThenReverse(){
  const sb = await runWithApp(makeSynthBuffer() + `
    clips[0][0] = { buffer, origBuffer:buffer, name:'X', mode:'loop', tempoStretch:1.3, toneShift:0, reversed:true, trimStart:0, trimEnd:null };
    await rebuildProcessedBuffer(clips[0][0]);
    globalThis.__result = { activeDuration: clips[0][0].buffer.duration, origDuration: clips[0][0].origBuffer.duration, sameAsOrig: clips[0][0].buffer===clips[0][0].origBuffer };
  `);
  const r = sb.__result;
  assert.strictEqual(r.sameAsOrig, false, 'il buffer attivo dopo il rebuild non deve mai essere lo stesso oggetto di origBuffer');
  assert.ok(Math.abs(r.activeDuration - r.origDuration/1.3) < (r.origDuration/1.3)*0.1,
    `con tempoStretch=1.3 la durata attiva deve riflettere lo stretch (atteso ~${(r.origDuration/1.3).toFixed(2)}s, ottenuto ${r.activeDuration.toFixed(2)}s)`);
}

async function testRebuildProcessedBufferNoStretchNoReverseKeepsOriginalDuration(){
  const sb = await runWithApp(makeSynthBuffer() + `
    clips[0][0] = { buffer, origBuffer:buffer, name:'X', mode:'loop', tempoStretch:1, toneShift:0, reversed:false, trimStart:0, trimEnd:null };
    await rebuildProcessedBuffer(clips[0][0]);
    globalThis.__result = { activeDuration: clips[0][0].buffer.duration, origDuration: clips[0][0].origBuffer.duration };
  `);
  const r = sb.__result;
  assert.ok(Math.abs(r.activeDuration - r.origDuration) < 0.05, 'senza stretch ne\' reverse la durata attiva deve restare quella originale');
}

(async () => {
  const tests = [
    ['cambiare Tempo aggiorna sourceBpm proporzionalmente', testChangingTempoUpdatesSourceBpmProportionally],
    ['riportare Tempo a 1 ripristina il sourceBpm originale', testResettingTempoToOneRestoresOriginalSourceBpm],
    ['cambiare Tono non tocca sourceBpm', testChangingToneDoesNotTouchSourceBpm],
    ['rebuildProcessedBuffer applica stretch poi reverse', testRebuildProcessedBufferAppliesStretchThenReverse],
    ['rebuildProcessedBuffer senza modifiche mantiene la durata originale', testRebuildProcessedBufferNoStretchNoReverseKeepsOriginalDuration],
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

Run: `node test_pad_tempo_tone.js`
Expected: tutti e 5 FALLISCONO — `#clipTempo`/`#clipTone`/`rebuildProcessedBuffer` non esistono ancora.

- [ ] **Step 3: Aggiungi i controlli HTML**

Dentro la sezione "Modifiche suono", subito dopo il blocco Filtro aggiunto nel Task 3 (prima della chiusura `</details>` della sezione), aggiungi:

```html
      <div class="row" style="font-size:12px">
        <label>Tempo</label><input type="range" id="clipTempo" min="0.5" max="2" step="0.01" value="1" style="flex:1;min-width:60px;accent-color:var(--accent)"><span id="clipTempoVal" style="color:var(--dim)">100%</span>
      </div>
      <div class="row" style="font-size:12px">
        <label>Tono</label><input type="range" id="clipTone" min="-12" max="12" step="1" value="0" style="flex:1;min-width:60px;accent-color:var(--accent)"><span id="clipToneVal" style="color:var(--dim)">0</span>
      </div>
```

- [ ] **Step 4: Scrivi `rebuildProcessedBuffer`**

Subito dopo `applyTimeStretch` (aggiunta nel Task 1, dopo `reversedBuffer`), aggiungi:

```js
// Unico punto che ricalcola il buffer ATTIVO di un clip da quello originale: prima il time-stretch
// (se tempoStretch!=1 o toneShift!=0), poi il reverse (se cl.reversed) — ordine fisso, vedi spec.
// Sostituisce la logica ad-hoc che clipRev.onchange/pasteClipBtn avevano prima (che gestivano solo
// origBuffer/revBuffer, ignari di un eventuale time-stretch in mezzo).
async function rebuildProcessedBuffer(cl){
  if(!cl.origBuffer) cl.origBuffer=cl.buffer;
  let base=cl.origBuffer;
  const tempo=cl.tempoStretch||1, semitones=cl.toneShift||0;
  if(tempo!==1 || semitones!==0){
    base=await applyTimeStretch(base, tempo, semitones);
  }
  cl.buffer = cl.reversed ? reversedBuffer(base) : base;
}
```

- [ ] **Step 5: Aggiorna `clipRev.onchange` e `pasteClipBtn.onclick` per usare `rebuildProcessedBuffer`**

Riga 1160-1169 (`clipRev.onchange`), sostituisci il corpo intero:
```js
document.getElementById('clipRev').onchange=(e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl){ e.target.checked=false; return; }
  pushUndo();
  if(!cl.origBuffer) cl.origBuffer=cl.buffer;
  // trimStart/trimEnd sono in secondi sul buffer ATTIVO: al ribaltamento vanno specchiati (dur-e, dur-s),
  // altrimenti dopo il reverse suona la porzione simmetrica sbagliata invece della stessa porzione al contrario.
  const dur=cl.origBuffer.duration, s=cl.trimStart||0, en=(cl.trimEnd!=null)?cl.trimEnd:dur;
  cl.trimStart=Math.max(0,dur-en); cl.trimEnd=Math.max(0,dur-s);
  if(e.target.checked){ if(!cl.revBuffer) cl.revBuffer=reversedBuffer(cl.origBuffer); cl.buffer=cl.revBuffer; cl.reversed=true; }
  else { cl.buffer=cl.origBuffer; cl.reversed=false; }
  selectPad(r,c); };
```
con:
```js
document.getElementById('clipRev').onchange=async (e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl){ e.target.checked=false; return; }
  pushUndo();
  if(!cl.origBuffer) cl.origBuffer=cl.buffer;
  // trimStart/trimEnd sono in secondi sul buffer ATTIVO: al ribaltamento vanno specchiati (dur-e, dur-s),
  // altrimenti dopo il reverse suona la porzione simmetrica sbagliata invece della stessa porzione al contrario.
  const dur=cl.origBuffer.duration, s=cl.trimStart||0, en=(cl.trimEnd!=null)?cl.trimEnd:dur;
  cl.trimStart=Math.max(0,dur-en); cl.trimEnd=Math.max(0,dur-s);
  cl.reversed=e.target.checked;
  await rebuildProcessedBuffer(cl);
  selectPad(r,c); };
```

Riga 1176-1185 (`pasteClipBtn.onclick`), sostituisci il corpo intero:
```js
document.getElementById('pasteClipBtn').onclick=()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl||!clipSettingsClipboard) return;
  pushUndo();
  const s=clipSettingsClipboard;
  cl.mode=s.mode; cl.gain=s.gain; cl.pitch=s.pitch; cl.choke=s.choke;
  const dur=cl.buffer?cl.buffer.duration:0;
  cl.trimStart=Math.min(s.trimStart,dur); cl.trimEnd=(s.trimEnd!=null)?Math.min(s.trimEnd,dur):null;
  if(!cl.origBuffer) cl.origBuffer=cl.buffer;
  if(s.reversed){ if(!cl.revBuffer) cl.revBuffer=reversedBuffer(cl.origBuffer); cl.buffer=cl.revBuffer; cl.reversed=true; }
  else { cl.buffer=cl.origBuffer; cl.reversed=false; }
  selectPad(r,c); updateLed(r,c); };
```
con:
```js
document.getElementById('pasteClipBtn').onclick=async ()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl||!clipSettingsClipboard) return;
  pushUndo();
  const s=clipSettingsClipboard;
  cl.mode=s.mode; cl.gain=s.gain; cl.pitch=s.pitch; cl.choke=s.choke;
  cl.fadeIn=s.fadeIn||0; cl.fadeOut=s.fadeOut||0; cl.filterCutoff=s.filterCutoff!=null?s.filterCutoff:1;
  cl.tempoStretch=s.tempoStretch||1; cl.toneShift=s.toneShift||0;
  const dur=cl.buffer?cl.buffer.duration:0;
  cl.trimStart=Math.min(s.trimStart,dur); cl.trimEnd=(s.trimEnd!=null)?Math.min(s.trimEnd,dur):null;
  if(!cl.origBuffer) cl.origBuffer=cl.buffer;
  cl.reversed=!!s.reversed;
  await rebuildProcessedBuffer(cl);
  selectPad(r,c); updateLed(r,c); };
```

(`clipSettingsClipboard`'s copia dei nuovi campi la aggiunge il Task 5, che si occupa di tutta la persistenza — qui li leggiamo con fallback sicuri se non ancora presenti, `s.fadeIn||0` ecc., così questo task resta indipendente dall'ordine di esecuzione rispetto al Task 5.)

- [ ] **Step 6: Aggiorna `selectPad` per mostrare Tempo/Tono**

Subito dopo la riga `clipFilter` aggiunta nel Task 3 dentro `selectPad`, aggiungi:

```js
  const ctp=document.getElementById('clipTempo'); if(ctp){ const tv=(cl&&cl.tempoStretch)||1; ctp.value=tv; document.getElementById('clipTempoVal').textContent=Math.round(tv*100)+'%'; }
  const cto=document.getElementById('clipTone'); if(cto){ const sv=(cl&&cl.toneShift)||0; cto.value=sv; document.getElementById('clipToneVal').textContent=sv; }
```

- [ ] **Step 7: Aggiungi gli handler di Tempo e Tono**

Subito dopo l'handler `clipFilter` aggiunto nel Task 3, aggiungi:

```js
document.getElementById('clipTempo').onchange=async (e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  const newTempo=+e.target.value;
  if(cl.sourceBpmOriginale==null) cl.sourceBpmOriginale=cl.sourceBpm||null;
  cl.tempoStretch=newTempo;
  document.getElementById('clipTempoVal').textContent=Math.round(newTempo*100)+'%';
  if(cl.sourceBpmOriginale!=null) cl.sourceBpm=Math.round(cl.sourceBpmOriginale/newTempo);
  await rebuildProcessedBuffer(cl);
  drawWaveform(cl);
};
document.getElementById('clipTempo').addEventListener('pointerdown',()=>pushUndo());
document.getElementById('clipTone').onchange=async (e)=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  cl.toneShift=+e.target.value;
  document.getElementById('clipToneVal').textContent=cl.toneShift;
  await rebuildProcessedBuffer(cl);
  drawWaveform(cl);
};
document.getElementById('clipTone').addEventListener('pointerdown',()=>pushUndo());
```

- [ ] **Step 8: Esegui i test e verifica che passino (GREEN)**

Run: `node test_pad_tempo_tone.js`
Expected: tutti e 5 PASS.

- [ ] **Step 9: Rebuild e regressione completa**

`python assemble.py`, poi `node run_all_tests.js` — presta particolare attenzione a `test_trim.js`, `test_live_trim.js` e ai test di Reverse esistenti (`clipRev.onchange` è stato riscritto in questo task).

- [ ] **Step 10: Verifica in Chrome vero**

Apri `Launchpad Studio.html` con Playwright:
1. Seleziona un pad con audio caricato, sposta Tempo a 130%: dopo un istante il pad suona più veloce, "BPM di origine" si aggiorna di conseguenza.
2. Riporta Tempo a 100%: "BPM di origine" torna al valore iniziale.
3. Sposta Tono senza toccare Tempo: il pad suona con intonazione diversa ma "BPM di origine" resta invariato.
4. Attiva Reverse su un pad con Tempo già modificato: suona alla velocità modificata E al contrario, nessun errore in console.

- [ ] **Step 11: Commit**

```bash
git add "_sorgente/launchpad-studio.html"
git commit -m "$(cat <<'EOF'
Tempo e Tono indipendenti per pad (time-stretch offline)

rebuildProcessedBuffer centralizza la ricostruzione del buffer attivo
(stretch poi reverse), sostituendo la logica ad-hoc di
clipRev.onchange/pasteClipBtn. Tempo aggiorna sourceBpm
proporzionalmente per restare coerente con l'aggancio automatico del
BPM; Tono lo lascia invariato.
EOF
)"
```

---

## Task 5: Persistenza (autosave, Salva set, Salva modifica, Copia/Incolla)

**Files:**
- Modify: `_sorgente/launchpad-studio.html`
- Modify: `_sorgente/genre_ui.js`
- Test: `<scratchpad>/test_sound_mods_persistence.js` (nuovo)

**Interfaces:**
- Consumes: `clip.fadeIn`/`fadeOut`/`filterCutoff`/`tempoStretch`/`toneShift`/`sourceBpmOriginale` (Task 2-4).
- Produces: nessuna nuova funzione — estende le liste di campi serializzati già esistenti in 5 punti.

- [ ] **Step 1: Scrivi i test (RED)**

Crea `<scratchpad>/test_sound_mods_persistence.js`:
```js
'use strict';
const assert = require('assert');
const fs = require('fs');
const { runWithApp } = require('./harness.js');
const GENRE_UI_SRC = fs.readFileSync('./_sorgente/genre_ui.js', 'utf8');

const FAKE_GENRES = { G1: { bpm: 120, clips: [
  { r: 0, c: 0, name: 'Kick_01', mime: 'audio/webm', data: 'AAAA', mode: 'loop', trimStart: 0, trimEnd: null },
] } };

async function runGenre(code){
  return runWithApp(GENRE_UI_SRC + '\n' + code, { inject: { GENRES: FAKE_GENRES } });
}

async function testSaveSetSerializesNewFields(){
  const sb = await runWithApp(`
    ac();
    const originalSet = { version:2, bpm:120, bars:4, quantMode:'off', activeBank:0, tracks:[], snapshots:null, banks:[[{r:0,c:0,name:'X',mime:'audio/webm',mode:'loop',trimStart:0,trimEnd:null,data:'AAAA'}],[],[],[]] };
    await document.getElementById('setInput').onchange({ target:{ files:[{ text: async()=>JSON.stringify(originalSet) }], value:'' } });
    selected = { r:0, c:0 };
    clips[0][0].buffer = { duration:4 };
    clips[0][0].fadeIn = 0.5; clips[0][0].fadeOut = 0.7; clips[0][0].filterCutoff = 0.4; clips[0][0].tempoStretch = 1.3; clips[0][0].toneShift = -3;
    let capturedBlobText = null;
    const OrigBlob = Blob;
    globalThis.Blob = class extends OrigBlob { constructor(parts, opts){ super(parts, opts); capturedBlobText = parts[0]; } };
    document.getElementById('saveBtn').onclick();
    const saved = JSON.parse(capturedBlobText);
    globalThis.__result = saved.banks[0][0];
  `);
  const r = sb.__result;
  assert.strictEqual(r.fadeIn, 0.5); assert.strictEqual(r.fadeOut, 0.7);
  assert.strictEqual(r.filterCutoff, 0.4); assert.strictEqual(r.tempoStretch, 1.3); assert.strictEqual(r.toneShift, -3);
}

async function testAutosaveSnapshotIncludesNewFields(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, raw:new ArrayBuffer(8), name:'X', mime:'audio/wav', mode:'loop', fadeIn:0.2, fadeOut:0.3, filterCutoff:0.6, tempoStretch:0.8, toneShift:4, trimStart:0, trimEnd:null };
    const snap = buildAutosaveSnapshot();
    globalThis.__result = snap.banks[activeBank].find(c=>c.r===0&&c.c===0);
  `);
  const r = sb.__result;
  assert.strictEqual(r.fadeIn, 0.2); assert.strictEqual(r.fadeOut, 0.3);
  assert.strictEqual(r.filterCutoff, 0.6); assert.strictEqual(r.tempoStretch, 0.8); assert.strictEqual(r.toneShift, 4);
}

async function testSaveModBtnPersistsNewFieldsAcrossGenreReload(){
  const sb = await runGenre(`
    ac();
    await loadGenre('G1');
    selected = { r:0, c:0 };
    clips[0][0].fadeIn = 0.4; clips[0][0].fadeOut = 0.6; clips[0][0].filterCutoff = 0.3; clips[0][0].tempoStretch = 1.1; clips[0][0].toneShift = 2;
    await document.getElementById('saveModBtn').onclick();
    await loadGenre('G1');
    globalThis.__result = { fadeIn: clips[0][0].fadeIn, fadeOut: clips[0][0].fadeOut, filterCutoff: clips[0][0].filterCutoff, tempoStretch: clips[0][0].tempoStretch, toneShift: clips[0][0].toneShift };
  `);
  const r = sb.__result;
  assert.strictEqual(r.fadeIn, 0.4); assert.strictEqual(r.fadeOut, 0.6);
  assert.strictEqual(r.filterCutoff, 0.3); assert.strictEqual(r.tempoStretch, 1.1); assert.strictEqual(r.toneShift, 2);
}

async function testCopyPasteIncludesNewFields(){
  const sb = await runWithApp(`
    ac();
    clips[0][0] = { buffer:{duration:2}, name:'A', mode:'loop', fadeIn:0.15, fadeOut:0.25, filterCutoff:0.5, tempoStretch:1.2, toneShift:-2, trimStart:0, trimEnd:null };
    clips[0][1] = { buffer:{duration:2}, name:'B', mode:'loop', trimStart:0, trimEnd:null };
    selected = { r:0, c:0 };
    document.getElementById('copyClipBtn').onclick();
    selected = { r:0, c:1 };
    await document.getElementById('pasteClipBtn').onclick();
    globalThis.__result = { fadeIn: clips[0][1].fadeIn, fadeOut: clips[0][1].fadeOut, filterCutoff: clips[0][1].filterCutoff, tempoStretch: clips[0][1].tempoStretch, toneShift: clips[0][1].toneShift };
  `);
  const r = sb.__result;
  assert.strictEqual(r.fadeIn, 0.15); assert.strictEqual(r.fadeOut, 0.25);
  assert.strictEqual(r.filterCutoff, 0.5); assert.strictEqual(r.tempoStretch, 1.2); assert.strictEqual(r.toneShift, -2);
}

(async () => {
  const tests = [
    ['"Salva set" serializza i nuovi campi', testSaveSetSerializesNewFields],
    ['buildAutosaveSnapshot include i nuovi campi', testAutosaveSnapshotIncludesNewFields],
    ['"Salva modifica" persiste i nuovi campi tra un ricaricamento genere e l\'altro', testSaveModBtnPersistsNewFieldsAcrossGenreReload],
    ['Copia/Incolla impostazioni include i nuovi campi', testCopyPasteIncludesNewFields],
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

Run: `node test_sound_mods_persistence.js`
Expected: tutti e 4 FALLISCONO — i nuovi campi non vengono ancora letti né scritti da nessuno dei 4 meccanismi.

- [ ] **Step 3: "Salva set" (`saveBtn.onclick`)**

Riga 1618-1619 (nel `for` che costruisce `bankClips`):
```js
      if(cl&&cl.raw) bankClips.push({r,c,name:cl.name,mime:cl.mime,mode:cl.mode||'loop',reversed:cl.reversed||false,gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:cl.steps||null,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm||null,data:abToB64(cl.raw)}); }
```
sostituisci con:
```js
      if(cl&&cl.raw) bankClips.push({r,c,name:cl.name,mime:cl.mime,mode:cl.mode||'loop',reversed:cl.reversed||false,gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:cl.steps||null,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm||null,fadeIn:cl.fadeIn||0,fadeOut:cl.fadeOut||0,filterCutoff:cl.filterCutoff!=null?cl.filterCutoff:1,tempoStretch:cl.tempoStretch||1,toneShift:cl.toneShift||0,data:abToB64(cl.raw)}); }
```

- [ ] **Step 4: "Apri set" (`setInput.onchange`, dentro `loadClipInto`)**

Riga 1661:
```js
        const nc={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',sourceBpm:cl.sourceBpm!=null?cl.sourceBpm:srcBpm,gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:Array.isArray(cl.steps)?cl.steps:null,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null};
```
sostituisci con:
```js
        const nc={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',sourceBpm:cl.sourceBpm!=null?cl.sourceBpm:srcBpm,gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:Array.isArray(cl.steps)?cl.steps:null,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,fadeIn:cl.fadeIn||0,fadeOut:cl.fadeOut||0,filterCutoff:cl.filterCutoff!=null?cl.filterCutoff:1,tempoStretch:cl.tempoStretch||1,toneShift:cl.toneShift||0};
```

Subito dopo, la stessa funzione `loadClipInto` ha:
```js
        if(cl.reversed){ nc.origBuffer=audio; nc.revBuffer=reversedBuffer(audio); nc.buffer=nc.revBuffer; nc.reversed=true; }
        grid[cl.r][cl.c]=nc;
```
sostituisci con:
```js
        nc.origBuffer=audio; nc.reversed=!!cl.reversed;
        if((nc.tempoStretch&&nc.tempoStretch!==1) || nc.toneShift){ await rebuildProcessedBuffer(nc); }
        else if(cl.reversed){ nc.buffer=reversedBuffer(audio); }
        grid[cl.r][cl.c]=nc;
```

- [ ] **Step 5: Autosave (`buildAutosaveSnapshot` e `restoreAutosave`)**

Riga 1779-1782 (`buildAutosaveSnapshot`):
```js
      if(cl&&cl.raw) bankClips.push({r,c,name:cl.name,mime:cl.mime,mode:cl.mode||'loop',reversed:cl.reversed||false,
        gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:cl.steps||null,
        trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm||null,
        raw:cl.raw}); }
```
sostituisci con:
```js
      if(cl&&cl.raw) bankClips.push({r,c,name:cl.name,mime:cl.mime,mode:cl.mode||'loop',reversed:cl.reversed||false,
        gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:cl.steps||null,
        trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm||null,
        fadeIn:cl.fadeIn||0,fadeOut:cl.fadeOut||0,filterCutoff:cl.filterCutoff!=null?cl.filterCutoff:1,tempoStretch:cl.tempoStretch||1,toneShift:cl.toneShift||0,
        raw:cl.raw}); }
```

Riga 1841 (`restoreAutosave`):
```js
        const nc={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:Array.isArray(cl.steps)?cl.steps:null,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm!=null?cl.sourceBpm:(snap.bpm||null)};
        if(cl.reversed){ nc.origBuffer=audio; nc.revBuffer=reversedBuffer(audio); nc.buffer=nc.revBuffer; nc.reversed=true; }
        banks[b][cl.r][cl.c]=nc;
```
sostituisci con:
```js
        const nc={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,steps:Array.isArray(cl.steps)?cl.steps:null,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm!=null?cl.sourceBpm:(snap.bpm||null),fadeIn:cl.fadeIn||0,fadeOut:cl.fadeOut||0,filterCutoff:cl.filterCutoff!=null?cl.filterCutoff:1,tempoStretch:cl.tempoStretch||1,toneShift:cl.toneShift||0};
        nc.origBuffer=audio; nc.reversed=!!cl.reversed;
        if((nc.tempoStretch&&nc.tempoStretch!==1) || nc.toneShift){ await rebuildProcessedBuffer(nc); }
        else if(cl.reversed){ nc.buffer=reversedBuffer(audio); }
        banks[b][cl.r][cl.c]=nc;
```

- [ ] **Step 6: "Salva modifica" (`saveModBtn.onclick`) e applicazione dell'override in `genre_ui.js`**

In `_sorgente/launchpad-studio.html`, riga 1080:
```js
  await saveGenreOverride(genre,r,c,{trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,reversed:!!cl.reversed,pitch:cl.pitch||0,sourceBpm:cl.sourceBpm||null});
```
sostituisci con:
```js
  await saveGenreOverride(genre,r,c,{trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,reversed:!!cl.reversed,pitch:cl.pitch||0,sourceBpm:cl.sourceBpm||null,fadeIn:cl.fadeIn||0,fadeOut:cl.fadeOut||0,filterCutoff:cl.filterCutoff!=null?cl.filterCutoff:1,tempoStretch:cl.tempoStretch||1,toneShift:cl.toneShift||0});
```

In `_sorgente/genre_ui.js`, il blocco che applica l'override (dentro `loadGenreData`):
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
sostituisci con:
```js
      if(genreKey){
        const ovr=genreOverrides[genreKey+'|'+cl.r+'|'+cl.c];
        if(ovr){
          nc.trimStart=ovr.trimStart||0; nc.trimEnd=ovr.trimEnd!=null?ovr.trimEnd:null; nc.pitch=ovr.pitch||0;
          if(ovr.sourceBpm!=null) nc.sourceBpm=ovr.sourceBpm;
          nc.fadeIn=ovr.fadeIn||0; nc.fadeOut=ovr.fadeOut||0; nc.filterCutoff=ovr.filterCutoff!=null?ovr.filterCutoff:1;
          nc.tempoStretch=ovr.tempoStretch||1; nc.toneShift=ovr.toneShift||0;
          nc.origBuffer=audio; nc.reversed=!!ovr.reversed;
          if((nc.tempoStretch&&nc.tempoStretch!==1) || nc.toneShift){ await rebuildProcessedBuffer(nc); }
          else if(ovr.reversed){ nc.buffer=reversedBuffer(audio); }
        }
      }
```

(Questo blocco è dentro un `for(const cl of data.clips)` che già usa `await` per `decodeAudioData` poco sopra — la funzione contenitore è già `async`, `await rebuildProcessedBuffer(nc)` qui dentro è quindi valido senza altre modifiche.)

- [ ] **Step 7: Copia/Incolla impostazioni (`copyClipBtn.onclick`)**

Riga 1172-1174:
```js
document.getElementById('copyClipBtn').onclick=()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  clipSettingsClipboard={mode:cl.mode||'loop',gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,
    trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,reversed:!!cl.reversed};
  document.getElementById('pasteClipBtn').disabled=false; };
```
sostituisci con:
```js
document.getElementById('copyClipBtn').onclick=()=>{ const{r,c}=selected; const cl=activeGrid()[r][c]; if(!cl) return;
  clipSettingsClipboard={mode:cl.mode||'loop',gain:cl.gain!=null?cl.gain:1,pitch:cl.pitch||0,choke:cl.choke||0,
    trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,reversed:!!cl.reversed,
    fadeIn:cl.fadeIn||0,fadeOut:cl.fadeOut||0,filterCutoff:cl.filterCutoff!=null?cl.filterCutoff:1,tempoStretch:cl.tempoStretch||1,toneShift:cl.toneShift||0};
  document.getElementById('pasteClipBtn').disabled=false; };
```

(`pasteClipBtn.onclick` legge già questi campi da `s.fadeIn` ecc. — sistemato nel Task 4 Step 5 — non serve toccarlo di nuovo qui.)

- [ ] **Step 8: Esegui i test e verifica che passino (GREEN)**

Run: `node test_sound_mods_persistence.js`
Expected: tutti e 4 PASS.

- [ ] **Step 9: Rebuild e regressione completa**

`python assemble.py` da `_sorgente/`, poi `node run_all_tests.js` — l'intera suite (inclusi tutti i test dei Task 1-4 di questo piano) deve restare verde.

- [ ] **Step 10: Verifica in Chrome vero**

Con Playwright: imposta fade/tempo/tono/filtro su un pad caricato da genere, premi "Salva modifica", ricarica un genere diverso poi ricarica quello originale — tutti e 5 i valori devono essere tornati. Ripeti con "Salva set"/"Apri set". Nessun errore in console durante l'intera sequenza.

- [ ] **Step 11: Commit**

```bash
git add "_sorgente/launchpad-studio.html" "_sorgente/genre_ui.js"
git commit -m "$(cat <<'EOF'
Persistenza per fade/filtro/tempo/tono (autosave, set, genere, copia/incolla)

Estende i 5 punti di serializzazione clip gia' esistenti (Salva set,
Apri set, autosave, Salva modifica + applicazione override in
genre_ui.js, Copia impostazioni) con fadeIn/fadeOut/filterCutoff/
tempoStretch/toneShift — stesso trattamento gia' riservato a
trim/pitch/reverse/sourceBpm.
EOF
)"
```

---

## Verifica finale end-to-end (dopo tutti i task)

Con Playwright, in Chrome vero:
1. Su un pad qualunque: imposta fade in 0.5s, fade out 0.8s, Tempo 140%, Tono +4, Filtro a metà — suona percettibilmente diverso (entrata/uscita morbide, più veloce, intonazione più alta, più ovattato), nessun errore in console.
2. "BPM di origine" di quel pad riflette il Tempo modificato; premere il pad aggancia correttamente il tempo di progetto.
3. Attiva Reverse sullo stesso pad: suona alla velocità/tono modificati E al contrario.
4. Riporta Tempo a 100%: "BPM di origine" torna al valore iniziale, il pad torna alla velocità nativa (ancora col Tono/Filtro/Fade impostati).
5. "Salva set", ricarica la pagina, "Apri set" quel file: tutti i valori tornano esattamente com'erano.
6. Il vecchio slider "Pitch" in "Suoni & Set" continua a funzionare esattamente come prima (accoppiato a velocità), invariato.
