# Launchpad Studio

Repository: `EasyMusic` (panchetto96/EasyMusic)

Campionatore e strumento da live-looping a griglia 8x8 che gira interamente nel browser, pensato per il Novation Launchpad Mini MK3: un solo file HTML, nessuna installazione, nessun server.

## Funzionalità

- **Griglia 8x8 di pad** (colonne = tracce, righe = scene) con 4 banchi (A-D), lancio di scene, preset/snapshot e feedback LED sul Launchpad fisico.
- **Controllo MIDI hardware**: connessione al Launchpad Mini MK3 in Programmer Mode, pad, scene e tasti superiori mappati su azioni dedicate (Drums, Play/Stop, registrazione, Re-sync).
- **Modalità pad** Loop / One-shot / Gate, quantizzazione del lancio (subito, movimento, battuta, frase), metronomo con pre-count, tap tempo.
- **Tempo e BPM**: sync BPM dei loop, BPM automatico agganciato al primo suono avviato, BPM di origine per pad con rilevamento assistito.
- **Editing per pad**: trim con forma d'onda, reverse, gain, pitch, tempo e tono indipendenti (time-stretch offline), fade in/out, filtro passa-basso, choke group, copia/incolla delle impostazioni tra pad.
- **Step sequencer** a 16 step per pad.
- **Mixer ed effetti**: volume/mute/solo per traccia, EQ shelf bassi/alti e invii a riverbero e delay per colonna; master con filtro, delay, riverbero (Freeverb) e limiter.
- **Catalogo suoni** con anteprima, drag and drop sui pad e riconoscimento della categoria del suono per parola chiave (drums, perc, bass, melodic, fx, vocal) con colori coerenti per categoria.
- **Generi e kit**: caricamento di generi precostruiti, kit Drums di 64 pad, kit personalizzati salvabili ed esportabili (`.lpkit`).
- **Registrazione**: da microfono su pad e del brano (mix master) in WAV o MP3.
- **Persistenza**: autosave periodico su IndexedDB con ripristino all'avvio, salvataggio/apertura di set `.lpstudio` multi-banco, Undo/Redo (30 livelli).

## Stack tecnologico

- **JavaScript vanilla, HTML e CSS** in un singolo file autocontenuto (nessun framework, nessuna dipendenza da installare).
- **Web Audio API**: grafo audio per traccia (gain, shelf EQ, invii), master con filtro e compressore/limiter, riverbero Freeverb (8 comb + 4 allpass), delay, decodifica con `decodeAudioData`, rendering offline per il time-stretch.
- **Web MIDI API** (`requestMIDIAccess`, con SysEx per la Programmer Mode) per input dei pad e output dei LED.
- **MediaRecorder** per la registrazione di microfono e brano.
- **IndexedDB** per autosave e kit personalizzati (l'audio supera i limiti di localStorage).
- **Librerie di terzi incluse**: lamejs (encoder MP3, LGPL) e SoundTouch.js (`_sorgente/soundtouch-vendor.js`, time-stretch).
- **Python 3** (solo libreria standard) per lo script di build; **ffmpeg** solo per rigenerare il catalogo audio.

## Architettura

L'app è un'unica pagina con sezioni di codice separate per responsabilita: stato (clip, banchi, tracce), I/O MIDI, griglia e mixer, caricamento suoni, transport/clock con scheduler a look-ahead (metronomo e step sequencer), registrazione, salvataggio set. I loop mantengono la fase calcolando l'offset di partenza da un tempo di riferimento comune.

Il file distribuibile `Launchpad Studio.html` è **generato**: `_sorgente/assemble.py` prende l'app base (`_sorgente/launchpad-studio.html`) e vi inietta i dati dei generi (`genres.json`, audio Opus in base64) e i moduli UI (`genre_ui.js`, `catalog_ui.js`, `drumkit_preset_ui.js`). Gli script in `_sorgente/tools/` ricostruiscono i dati audio dai pacchetti di loop di partenza.

```
_sorgente/
  launchpad-studio.html   app base: il sorgente da modificare
  genre_ui.js, catalog_ui.js, drumkit_preset_ui.js   moduli UI iniettati
  soundtouch-vendor.js    libreria time-stretch
  assemble.py             build
  tools/                  ricostruzione del catalogo audio
docs/superpowers/         specifiche e piani di implementazione delle funzioni
```

La cartella `docs/` contiene specifiche e piani di progettazione, non una build pubblicabile.

## Come si usa / avvio

Requisiti: Chrome o Edge (serve Web MIDI; il Launchpad è opzionale, i pad si suonano anche col mouse).

L'app completa (`Launchpad Studio.html`, circa 300 MB per i generi incorporati) e i set `.lpstudio` non sono nel repository perche troppo pesanti; i dati audio (`genres.json`, `drumkit_preset.json`) sono generati da loop di terze parti non redistribuibili. Due strade:

1. **Versione base, senza generi**: aprire `_sorgente/launchpad-studio.html` in Chrome o Edge e trascinare i propri file audio sui pad.
2. **Build completa** (richiede `genres.json` e `drumkit_preset.json` in `_sorgente/`, ricostruibili con gli script in `_sorgente/tools/`, vedi `_sorgente/tools/README.md`):
   ```
   cd _sorgente
   python assemble.py
   ```
   Produce `Launchpad Studio.html` nella root; si apre con doppio clic. Su Windows usare `python`, non `python3`.

Per usare il Launchpad: collegarlo via USB, aprire l'app e consentire l'accesso MIDI al browser.

## Manuale utente

[Manuale Launchpad Studio](Manuale%20Launchpad%20Studio.html) (HTML, in italiano): guida rapida, collegamento del Launchpad, modalita pad, mixer ed effetti, step sequencer, editing per clip. Da aprire nel browser dopo il clone.

## Sviluppo

Note di sviluppo, architettura dettagliata, formato dei file `.lpstudio`, limiti noti e backlog sono in [SVILUPPO.md](SVILUPPO.md). Istruzioni di build in [_sorgente/BUILD.md](_sorgente/BUILD.md).

## Note legali

I loop Novation usati come catalogo non sono redistribuibili; "Launchpad" è un marchio di Novation. Il progetto non e affiliato a Novation.
