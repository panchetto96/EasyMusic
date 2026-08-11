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
per traccia: BufferSource -> Gain(fade) -> trackGains[c] -> masterGain -> masterFilter(lowpass)
             -> masterLimiter(comp) -> destination
                                    \-> fxDelaySend->delay(+feedback)->masterLimiter
                                    \-> fxReverbSend->convolver->masterLimiter
                                    \-> recDest (MediaStreamDestination, per la registrazione)
```
- **Phase-lock**: i loop partono con un offset calcolato da `startTime` così restano in fase anche lanciati a tempi diversi. `resyncAll` ri-ancora `startTime` e li fa ripartire da zero insieme.
- **Limiter** sul master evita il clipping quando si sommano più loop.

### MIDI (Launchpad Mini MK3, Programmer Mode)
- SysEx Programmer: `F0 00 20 29 02 0D 0E 01 F7`; Live: `...0E 00 F7`.
- Griglia 8×8 = note 11..88: `note = 11 + (7-row)*10 + col`.
- Colonna destra (scene) = note 19,29,...,89 → `launchScene`.
- Fila superiore = 91..98 → stop colonna.
- LED: Note On, canale 1 statico (0x90), 2 flash (0x91), 3 pulse (0x92); velocity = indice palette Novation.
- **Windows tranello**: la porta che controlla i LED è la SECONDA interfaccia (`MIDIIN2/MIDIOUT2 (LPMiniMK3 MIDI)`), NON quella dal nome pulito (che è la DAW). Vedi `pick()`.

## 5. Funzioni implementate (checklist)
Connessione/LED, auto-detect porta, Test LED, Reset device (Live). Griglia 8×8 con drag&drop. Mixer per traccia (volume/M/S/stop). Master + filtro passa-basso + **delay** + **riverbero** + limiter. Transport: Play/Stop, BPM, **Tap tempo**, **Sync BPM** (time-stretch a resampling), quantizzazione (Subito/Movimento/Battuta/Frase), metronomo, **Pre-count**. Modalità pad **Loop/One-shot/Gate** — **default sempre Loop per ogni pad, su tutti i suoni** (jukebox, set, file trascinati): nessuna euristica indovina la modalità dal nome del file, one-shot/gate solo se scelti esplicitamente dall'utente (o salvati così in un `.lpstudio`). Scelta di design voluta: per uno strumento da live-looping la prevedibilità conta più della comodità di un auto-detect. **Scene launch** (righe) + **Re-sync** + Stop tutto. **Preset/snapshot** (8). **Banking** (4 banchi). **Step sequencer** (16 step per pad). Per-clip: **Reverse, Gain, Pitch, Choke group**. Registrazione **microfono→pad** e **brano→WAV/MP3** (MediaRecorder + encode; MP3 via lamejs non bloccante). Salva/Apri **.lpstudio**. **Colore per categoria**: al caricamento di un genere o di un set, `recomputeTrackColors()` deduce dal nome dei clip (prefisso senza il numero finale, es. "Drums" da "Drums_07") quali colonne sono lo stesso tipo di strumento e gli assegna lo stesso colore (pad + LED Launchpad); colonne vuote o non riconoscibili restano ciascuna col proprio colore. Non scatta sui pad caricati a mano trascinando un file (nessuna categoria nota per confrontarli). **Trim per clip**: cursori Inizio/Fine + forma d'onda (canvas, min/max per pixel) sul pad selezionato; usa `loopStart`/`loopEnd` nativi di `AudioBufferSourceNode` per loop/gate e `start(when, offset, duration)` per one-shot/step; persistito in `.lpstudio` e nell'autosave (`trimStart`/`trimEnd` in secondi). **Transizione morbida**: caricare un genere o un set non ferma più di colpo (`stopAllSmooth`, dissolvenza del master ~1.2s invece di `stopAll()` secco). **Autosave** (IndexedDB, non localStorage — l'audio supera di gran lunga i ~5-10MB che localStorage reggerebbe): salvataggio periodico (ogni 20s se `audioCtx` esiste) più esplicito dopo apertura set/genere; salva **tutti e 4 i banchi** (a differenza di `.lpstudio` che salva solo l'attivo); al riavvio chiede conferma prima di ripristinare.

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
JSON: `{version, bpm, bars, quantMode, phraseBars?, master, filter?, revWet?, revSize?, dlyWet?, dlyFb?, dlyTime?, snapshots, tracks:[{volume,muted,solo}], clips:[{r,c,name,mime,mode,reversed,gain,pitch,choke,steps,data(base64 audio)}]}`. Il caricamento ripristina master/volumi traccia, filtro e FX (reverb/delay) esattamente come salvati (i campi `?` sono opzionali, per compatibilità con set salvati da versioni precedenti: se assenti si usano i default di fabbrica). `quantMode` viene comunque forzato a `'off'` al caricamento — scelta intenzionale per ripartire subito in fase, non in coda. Salva solo il **banco attivo**.

## 8. Limiti noti
- Audio jukebox **compresso** (Opus). Qualità piena solo caricando i WAV originali o i set FLAC PRO.
- **Time-stretch** = resampling (cambia intonazione), non pitch-preserving.
- Registrazione via **MediaRecorder** = internamente Opus (pulita ma non PCM bit-perfect). L'AudioWorklet PCM funziona solo via http/localhost, non da `file://`.
- **Banchi B/C/D** non salvati nel .lpstudio (solo l'attivo) — ma **sono** salvati nell'autosave IndexedDB (vedi §5).
- **Step sequencer**: 16 step / 1 battuta, parte solo con transport in Play.
- **Autosave** presente (IndexedDB, ogni 20s + su apertura set/genere) **e Undo/Redo** (Ctrl+Z/Ctrl+Y o i pulsanti, 30 livelli, pila in memoria — vedi §5): insieme coprono sia il crash/chiusura accidentale sia l'errore mentre lavori. L'Undo non registra la riproduzione/cosa sta suonando in quel momento, solo il contenuto della griglia e i parametri di mix/tempo/FX.
- Due file da tenere allineati (sorgente + generato) tramite lo script di assemblaggio.
- **Build risolta:** `_sorgente/assemble.py` + `genres.json` + `genre_ui.js` sono presenti e rigenerano `Launchpad Studio.html` **identico al byte** (verificato con `cmp`). Non serve più tenere allineati a mano sorgente e file generato: si edita `_sorgente/` e si lancia `assemble.py` (vedi §6). Gli script che generano `genres.json` dai loop Novation grezzi (`build_parts.py` ecc.) non sono conservati, ma non servono per lavorare sull'app perché `genres.json` è già presente (vedi §6, "Rigenerare i dati dei generi").
- Il "riverbero" è rumore bianco filtrato (`makeIR`, inviluppo esponenziale casuale), non un IR reale né un algoritmo tipo Freeverb: cambia timbro ad ogni regolazione della dimensione e non è riproducibile.
- **Legale**: i loop Novation NON sono redistribuibili in un software venduto — per vendere l'app va spedita **senza suoni** (o con suoni licenziati per software). "Launchpad"/"Ableton" sono marchi: serve un nome proprio. lamejs è LGPL (attribuzione).

## 9. Backlog (prossimi passi consigliati)

1. ~~Auto-save + Undo~~ — **fatto** (IndexedDB + stack in memoria, vedi §5/§8).
2. ~~Start/trim per clip con forma d'onda~~ — **fatto** (vedi §5).
3. Salvataggio **multi-banco** nel `.lpstudio` — parzialmente coperto: l'**autosave** salva già tutti e 4 i banchi, ma il file `.lpstudio` scaricabile continua a salvare solo il banco attivo.
4. **MIDI clock** sync in/out.
5. Consolidare in un **solo sorgente** (eliminare la duplicazione sorgente/generato, es. caricando i generi da file esterni con un mini-server opzionale).
6. Migrare la registrazione ad **AudioWorklet** quando servito via http (lossless PCM).
7. Packaging (Electron/PWA) se si vuole distribuire.

## 10. Come riprendere in 5 minuti
1. Apri `_sorgente/launchpad-studio.html` in un editor: è l'app completa e leggibile.
2. Per provarla: aprila in Chrome (griglia vuota, carichi tu i suoni). Per i generi usa `Launchpad Studio.html`.
3. Per modificare: edita il sorgente, ri-assembla, verifica con `node --check` sugli `<script>`.
