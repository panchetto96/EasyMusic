# Launchpad Studio — Documento di sviluppo (handoff)

> Scopo: permettere di **riprendere lo sviluppo da zero in un'altra sessione**. Qui c'è tutto: cosa fa l'app, com'è fatta, come si ricostruisce, i formati dati, i limiti noti e il backlog.

Ultimo aggiornamento: 2026-08-11.

---

## 1. Cos'è
App **web (HTML unico)** che trasforma un **Novation Launchpad Mini MK3** in uno strumento da live-looping / campionatore a griglia, stile Ableton Session View ma semplificato. Gira in **Chrome/Edge** (serve **Web MIDI**). Nessuna installazione: si apre con doppio clic.

- Griglia 8×8 = i pad. Colonne = tracce/strumenti, righe = scene.
- Carichi loop/campioni sui pad e li lanci col Launchpad; i LED danno feedback.
- Include un **jukebox**: 9 generi (loop Novation) già incorporati, caricabili da menù a tendina.

## 2. Modalità di avvio — UNIFICATA
Storicamente c'erano 3 varianti (base, jukebox, HD-Docker). **Decisione: una sola app HTML**, `Launchpad Studio.html`, doppio clic, niente server/Docker. La versione HD lossless via server è **ritirata** (vantaggio audio inudibile vs attrito del server). L'audio del jukebox è compresso (Opus stereo) per stare in un file solo.

## 3. Struttura cartella (D:\MUSIC\Launchpad Studio\)
```
Launchpad Studio.html          <- L'APP (self-contained, generi incorporati). Questo è il deliverable.
Launchpad Sets/                <- 9 set .lpstudio (Opus 256k stereo, uno per genere) da caricare con "Apri set"
Registrazioni/                 <- WAV registrati dall'utente
Manuale Launchpad Studio.html  <- manuale utente
SVILUPPO.md                    <- questo file
_sorgente/                     <- SORGENTI + BUILD (vedi §6)
  launchpad-studio.html        <- APP BASE (senza generi): è il SORGENTE da editare
  genres.json                  <- dati dei 9 generi (audio Opus base64, ~76 MB)
  genre_ui.js                  <- barra "Genere" + funzione loadGenre (glue)
  assemble.py                  <- build: sorgente + genres.json + genre_ui.js -> app
  BUILD.md                     <- istruzioni di build
_Archivio/Launchpad Sets PRO/  <- 3 set FLAC lossless (esempi, pesanti)
```
NOTA: `Launchpad Studio.html` è **generato** da `_sorgente/` con `assemble.py`. Non editare a mano il file da 76 MB: modifica il sorgente e ri-assembla (vedi §6). Lo script rigenera l'app **identica al byte**.

## 4. Architettura del sorgente (`launchpad-studio.html`)
Un unico file: `<style>` + markup + **due `<script>`**:
1. **lamejs** (encoder MP3, LGPL) minificato — libreria di terzi.
2. **App** (~700 righe), organizzata in sezioni commentate:
   - STATO: `clips` (griglia attiva), `banks` (4 banchi), `tracks`, `trackState`, `audioCtx`.
   - WEB MIDI: `initMIDI/pick/populatePorts/connectPorts/onMidiMessage/setLed/updateLed`. Programmer Mode via SysEx.
   - GRIGLIA+MIXER: costruzione pad (pointer events), mixer per traccia, handler master/FX, barre Scene/Preset/Bank/Seq.
   - CARICAMENTO SUONI + per-clip (reverse/gain/pitch/choke).
   - TRANSPORT/CLOCK: `secPerBeat`, `nextBoundary`, `triggerDown/Up`, `playOnce`, `startGate/stopGate`, `launchScene`, `scheduleClip`, `stopTrackClip`, `resyncAll`.
   - METRONOMO/SCHEDULER: `scheduler()` (requestAnimationFrame + look-ahead) gestisce metronomo e **step sequencer**.
   - REGISTRAZIONE microfono (su pad) e REGISTRAZIONE BRANO (mix master → WAV/MP3).
   - SALVA/APRI SET (.lpstudio).

### Grafo audio (Web Audio)
```
per traccia: BufferSource -> Gain(fade) -> trackGains[c] -> trackLow[c](lowshelf) -> trackHigh[c](highshelf) -> masterGain
                                                                 \-> trackRevSend[c] -> fxReverb (comb+allpass)
                                                                 \-> trackDlySend[c] -> fxDelay
             masterGain -> masterFilter(lowpass) -> masterLimiter(comp) -> destination
                                    \-> fxDelaySend->fxDelay(+feedback)->masterLimiter
                                    \-> fxReverbSend->fxReverb(Freeverb: 8 comb + 4 allpass)->masterLimiter
                                    \-> recDest (MediaStreamDestination, per la registrazione)
```
- **Phase-lock**: i loop partono con un offset calcolato da `startTime` così restano in fase anche lanciati a tempi diversi. `resyncAll` ri-ancora `startTime` e li fa ripartire da zero insieme.
- **Limiter** sul master evita il clipping quando si sommano più loop.
- **EQ e invii per traccia**: `trackLow`/`trackHigh` (shelf ±12dB, frequenze fisse 200Hz/4kHz) e `trackRevSend`/`trackDlySend` (0-1, si sommano al segnale che il master manda già a riverbero/delay) sono per **colonna**, non per clip — condivisi tra i banchi come `tracks[c].volume/muted/solo`. Controlli nel pannello, sotto le manopole master, scoperti sulla colonna selezionata (`selected.c`).
- **Riverbero = Freeverb vero** (8 comb filter in parallelo + 4 allpass in serie, `buildReverbGraph`), non più un IR di rumore bianco. Il cursore "dim." resta 0.3–3.5 per compatibilità ma ora pilota il feedback dei comb (`setReverbSize`, mappato 0.28–0.95 — sotto 1 per restare stabile).

### MIDI (Launchpad Mini MK3, Programmer Mode)
- SysEx Programmer: `F0 00 20 29 02 0D 0E 01 F7`; Live: `...0E 00 F7`.
- Griglia 8×8 = note 11..88: `note = 11 + (7-row)*10 + col`.
- Colonna destra (scene) = note/CC 19,29,...,89 → `launchScene`. **Verificato su hardware reale (Mini MK3): questi arrivano come CC (0xB0), non Note On come da documentazione Novation "canonica"** — il codice ascolta entrambi (`type===0x90||type===0xB0`). Prima della correzione (2026-08-11) lo scene launch da pad fisico non ha mai funzionato per questo motivo, solo dai pulsanti a schermo.
  - Nota 29 riservata: `cycleBank()` (cambia banco A→B→C→D→A…).
  - Nota 19 (in basso) riservata: `stopAll()`.
  - Le altre 6 (39,49,59,69,79,89) lanciano le scene normalmente.
- Fila superiore = 91..98 → stop colonna.
- LED: Note On, canale 1 statico (0x90), 2 flash (0x91), 3 pulse (0x92); velocity = indice palette Novation.
- **Windows tranello**: la porta che controlla i LED è la SECONDA interfaccia (`MIDIIN2/MIDIOUT2 (LPMiniMK3 MIDI)`), NON quella dal nome pulito (che è la DAW). Vedi `pick()`.
- **Nessun tasto fisico libero per il banco**: sul Mini MK3 griglia+riga superiore+colonna scene esauriscono tutti i controlli fisici — non c'è una "colonna laterale" separata come su Launchpad X/Pro. Per questo il cambio banco da pad è stato ottenuto sacrificando un tasto scena (nota 29), non aggiungendo un controllo nuovo.

## 5. Funzioni implementate (checklist)
Connessione/LED, auto-detect porta, Test LED, Reset device (Live). Griglia 8×8 con drag&drop. Mixer per traccia (volume/M/S/stop). Master + filtro passa-basso + **delay** + **riverbero** + limiter. Transport: Play/Stop, BPM, **Tap tempo**, **Sync BPM** (time-stretch a resampling), quantizzazione (Subito/Movimento/Battuta/Frase), metronomo, **Pre-count**. Modalità pad **Loop/One-shot/Gate** — **default sempre Loop per ogni pad, su tutti i suoni** (jukebox, set, file trascinati): nessuna euristica indovina la modalità dal nome del file, one-shot/gate solo se scelti esplicitamente dall'utente (o salvati così in un `.lpstudio`). Scelta di design voluta: per uno strumento da live-looping la prevedibilità conta più della comodità di un auto-detect. **Scene launch** (righe) + **Re-sync** + Stop tutto. **Preset/snapshot** (8). **Banking** (4 banchi) — cambio banco anche dal pad fisico (nota scena 29, ciclico A→B→C→D→A…), non solo da schermo; usa `stopAllSmooth` (dissolvenza 1.0s, un po' più breve del cambio genere/1.2s: qui i suoni sono già decodificati in memoria, il vantaggio dei banchi rispetto a caricare un genere/set diverso è proprio l'istantaneità). **Step sequencer** (16 step per pad). Per-clip: **Reverse, Gain, Pitch, Choke group**. Registrazione **microfono→pad** e **brano→WAV/MP3** (MediaRecorder + encode; MP3 via lamejs non bloccante). Salva/Apri **.lpstudio**. **Colore per categoria**: al caricamento di un genere o di un set, `recomputeTrackColors()` deduce dal nome dei clip (prefisso senza il numero finale, es. "Drums" da "Drums_07") quali colonne sono lo stesso tipo di strumento e gli assegna lo stesso colore (pad + LED Launchpad); colonne vuote o non riconoscibili restano ciascuna col proprio colore. Non scatta sui pad caricati a mano trascinando un file (nessuna categoria nota per confrontarli). **Trim per clip**: cursori Inizio/Fine + forma d'onda (canvas, min/max per pixel) sul pad selezionato; usa `loopStart`/`loopEnd` nativi di `AudioBufferSourceNode` per loop/gate e `start(when, offset, duration)` per one-shot/step; persistito in `.lpstudio` e nell'autosave (`trimStart`/`trimEnd` in secondi). **Transizione morbida**: caricare un genere o un set non ferma più di colpo (`stopAllSmooth`, dissolvenza del master ~1.2s invece di `stopAll()` secco). **Autosave** (IndexedDB, non localStorage — l'audio supera di gran lunga i ~5-10MB che localStorage reggerebbe): salvataggio periodico (ogni 20s se `audioCtx` esiste) più esplicito dopo apertura set/genere; salva **tutti e 4 i banchi**; al riavvio chiede conferma prima di ripristinare. Indicatore di stato ("Autosave: salvato alle HH:MM:SS" o avviso se fallisce) + pulsante **🗑️ Cancella autosave**. **Undo copre anche BPM/Battute/Quantizza/Sync BPM/tempo Delay** (non solo griglia e mix), con cattura "a inizio modifica" (focus/pointerdown) invece che per ogni singolo tasto/trascinamento. **Salva/Apri set multi-banco**: `.lpstudio` ora salva e ripristina tutti e 4 i banchi (formato v2), retrocompatibile con i vecchi file a banco singolo (v1). **EQ e invii per traccia**: shelf bassi/alti ±12dB + invio indipendente a riverbero/delay, per colonna, condiviso tra i banchi. **Copia/incolla impostazioni pad** (📋/📥): trasferisce modo/gain/pitch/choke/trim/reverse tra pad, mai l'audio. **Riverbero vero** (Freeverb: 8 comb + 4 allpass) al posto del rumore bianco filtrato.

## 6. Build / assemblaggio (IMPORTANTE per riprendere)
La pipeline è **completa e dentro `_sorgente/`**: `assemble.py` rigenera `Launchpad Studio.html` **identico al byte** (verificato con `cmp` — vedi nota sotto). Comando:
```
cd _sorgente && python assemble.py           # -> ../Launchpad Studio.html
python assemble.py /percorso/out.html         # output alternativo
```
Su Windows usa `python`, non `python3` (qui `python3` è intercettato dall'App Execution Alias e prova ad aprire il Microsoft Store invece di eseguire lo script). Su Mac/Linux è spesso il contrario: usa quello che risulta installato sul tuo sistema.

Come funziona: legge `launchpad-studio.html` (app base), e prima di `</body>` inietta un `<script>` con `const GENRES = ` + il contenuto di `genres.json` + il glue `genre_ui.js` (barra "Genere" + `loadGenre`). `genres.json` contiene i 9 generi con l'audio Opus in base64 (~76 MB, 348 clip); `genre_ui.js` è il codice della UI. Lo script scrive l'output con `newline=""` per non far tradurre a Windows i fine riga `\n` in `\r\n` (senza, l'output non è identico al byte e cresce di ~1 KB per differenze di terminazione riga).

Regola pratica: **modifica `launchpad-studio.html`** (logica app) o `genre_ui.js` (UI generi) o `genres.json` (dati), poi ri-esegui `assemble.py`. `assemble.py` valida il JSON e conta le clip. Per la sintassi JS: `node --check genre_ui.js`, oppure estrai gli `<script>` dell'app e passali a `node --check`.

### Rigenerare i dati dei generi da zero (raramente serve)
`genres.json` è già presente, quindi la build è autosufficiente. Ricostruirlo dai loop **grezzi** serve solo se vuoi cambiare selezione/qualità dei suoni, e richiede i pacchetti **Novation Anniversary** (30 Years) — NON inclusi nella cartella. Logica (script `build_parts.py`/`build_jukebox_pro.py` non conservati, ma semplici da rifare): per genere e categoria (Drums/Bass/Melodic/Percussion/FX), transcodifica i loop in **Opus stereo** con `ffmpeg -af loudnorm ... -c:a libopus`, base64, e assembla `{bpm,bars,quantMode,phraseBars,master,tracks,clips:[{r,c,name,mime,data}]}` per ciascun genere (nome cartella loop = `(Tonalità, BPMbpm)`). Stessa logica per i set `.lpstudio` (256k) e i FLAC PRO. **In pratica non serve**: per modifiche all'app basta editare il sorgente e lanciare `assemble.py`.

⚠️ Nessun clip del jukebox ha `mode` impostato nei dati (né in `genres.json` né nei `.lpstudio`): partono tutti **Loop** per default di codice (vedi §5). Questo vale anche per gli "Extra_01..08" (T7) di **LoFi · Japanese** — che nel pacchetto Novation sono la colonna equivalente a "FX ..." degli altri generi (texture/atmosfera con riverbero registrato nel file) — e restano volutamente in loop come tutto il resto: è così che li vuole l'utente, non un difetto da correggere. Se in futuro si rigenera `genres.json` da zero, **non** reintrodurre un'euristica automatica sul nome del file per decidere la modalità.

## 7. Formato .lpstudio (set)
**Versione 2 (attuale)**: `{version:2, bpm, bars, quantMode, phraseBars?, activeBank, master, filter?, revWet?, revSize?, dlyWet?, dlyFb?, dlyTime?, snapshots, tracks:[{volume,muted,solo,low?,high?,revSend?,dlySend?}], banks:[[clip,...] x4]}` — ogni elemento di `banks` è l'array di clip di quel banco, stessa forma di prima (`{r,c,name,mime,mode,reversed,gain,pitch,choke,steps,trimStart?,trimEnd?,data(base64 audio)}`). Salva e ripristina **tutti e 4 i banchi**, non solo l'attivo.

**Versione 1 (retrocompatibilità)**: file vecchi con `clips:[...]` invece di `banks` si aprono ancora — `Apri set` rileva l'assenza di `data.banks` e ricade sul comportamento storico (un solo banco: quello attivo al momento dell'apertura; gli altri 3 restano intatti, non vengono toccati).

Il caricamento ripristina master/volumi traccia/EQ-invii per traccia, filtro e FX (reverb/delay) esattamente come salvati (i campi `?` sono opzionali: se assenti si usano i default di fabbrica). `quantMode` viene comunque forzato a `'off'` al caricamento — scelta intenzionale per ripartire subito in fase, non in coda.

## 8. Limiti noti
- Audio jukebox **compresso** (Opus). Qualità piena solo caricando i WAV originali o i set FLAC PRO.
- **Time-stretch** = resampling (cambia intonazione), non pitch-preserving.
- Registrazione via **MediaRecorder** = internamente Opus (pulita ma non PCM bit-perfect). L'AudioWorklet PCM funziona solo via http/localhost, non da `file://`.
- **Banchi B/C/D**: salvati sia nell'autosave sia in `.lpstudio` (formato v2, vedi §7).
- **Step sequencer**: 16 step / 1 battuta, parte solo con transport in Play.
- **Autosave** presente (IndexedDB, ogni 20s + su apertura set/genere, con indicatore di stato e pulsante di cancellazione) **e Undo/Redo** (Ctrl+Z/Ctrl+Y o i pulsanti, 30 livelli, pila in memoria — vedi §5): insieme coprono sia il crash/chiusura accidentale sia l'errore mentre lavori. L'Undo non registra la riproduzione/cosa sta suonando in quel momento, solo il contenuto della griglia e i parametri di mix/tempo/FX. Tra un autosave esplicito e l'altro (fuori da apri-set/genere) c'è comunque una finestra fino a 20s in cui un crash può perdere l'ultima modifica — non c'è un trigger esplicito su ogni singola azione (carica pad, gain, sequencer, ecc.), solo il timer periodico.
- Due file da tenere allineati (sorgente + generato) tramite lo script di assemblaggio.
- **Build risolta:** `_sorgente/assemble.py` + `genres.json` + `genre_ui.js` sono presenti e rigenerano `Launchpad Studio.html` **identico al byte** (verificato con `cmp`). Non serve più tenere allineati a mano sorgente e file generato: si edita `_sorgente/` e si lancia `assemble.py` (vedi §6). Gli script che generano `genres.json` dai loop Novation grezzi (`build_parts.py` ecc.) non sono conservati, ma non servono per lavorare sull'app perché `genres.json` è già presente (vedi §6, "Rigenerare i dati dei generi").
- Il riverbero è ora un **Freeverb vero** (8 comb + 4 allpass), non più rumore bianco filtrato — vedi §4. Resta comunque un algoritmo "da manuale" con parametri fissi (frequenza di damping, tuning dei comb): niente pre-delay separato né controllo di damping esposto in UI.
- **EQ/invii per traccia** sono per colonna (condivisi tra banchi), non per singolo clip — se serve un timbro diverso per due suoni sulla stessa colonna, oggi non si può.
- Nessuna copia dell'audio tra pad: **📋/📥 Copia impostazioni** trasferisce solo modo/gain/pitch/choke/trim/reverse, mai il suono stesso.
- **Legale**: i loop Novation NON sono redistribuibili in un software venduto — per vendere l'app va spedita **senza suoni** (o con suoni licenziati per software). "Launchpad"/"Ableton" sono marchi: serve un nome proprio. lamejs è LGPL (attribuzione).

## 9. Backlog (prossimi passi consigliati)

1. ~~Auto-save + Undo~~ — **fatto** (IndexedDB + stack in memoria, vedi §5/§8).
2. ~~Start/trim per clip con forma d'onda~~ — **fatto** (vedi §5).
3. ~~Salvataggio multi-banco nel `.lpstudio`~~ — **fatto** (formato v2, vedi §7).
4. ~~EQ/effetti per traccia~~ — **fatto** (shelf + invii riverbero/delay per colonna, vedi §4/§5).
5. ~~Riverbero algoritmico vero~~ — **fatto** (Freeverb, vedi §4/§8).
6. ~~Copia/incolla impostazioni tra pad~~ — **fatto** (vedi §5).
7. **MIDI clock** sync in/out.
8. Consolidare in un **solo sorgente** (eliminare la duplicazione sorgente/generato, es. caricando i generi da file esterni con un mini-server opzionale).
9. Migrare la registrazione ad **AudioWorklet** quando servito via http (lossless PCM).
10. Packaging (Electron/PWA) se si vuole distribuire.
11. **EQ/effetti per singolo clip** (oggi sono per traccia/colonna, condivisi tra i pad della stessa colonna).
12. Autosave con trigger su ogni azione (oggi: esplicito solo su apri-set/genere, altrimenti timer a 20s — vedi §8).

## 10. Come riprendere in 5 minuti
1. Apri `_sorgente/launchpad-studio.html` in un editor: è l'app completa e leggibile.
2. Per provarla: aprila in Chrome (griglia vuota, carichi tu i suoni). Per i generi usa `Launchpad Studio.html`.
3. Per modificare: edita il sorgente, ri-assembla, verifica con `node --check` sugli `<script>`.
