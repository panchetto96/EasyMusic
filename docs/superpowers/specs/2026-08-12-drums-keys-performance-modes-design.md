# Modalità performance Drums/Keys sui 4 tasti superiori (Session/Drums/Keys/User)

## Contesto

Il Launchpad Mini MK3 ha una fila di 8 tasti tondi sopra la griglia: Up, Down, Left, Right, Session, Drums, Keys, User. In Programmer Mode (quella usata da Launchpad Studio) inviano CC 91-98 da sinistra a destra — confermato empiricamente su hardware reale: **91=Up, 92=Down, 93=Left, 94=Right, 95=Session, 96=Drums, 97=Keys, 98=User** (tutti Control Change 0xB0).

Oggi tutti e 8 sono mappati genericamente a "ferma la colonna" (`stopTrackClip(d1-91,true)`), e nessuno dei 4 (Session/Drums/Keys/User) ha un LED acceso — sembrano "morti" anche se in realtà fanno qualcosa.

Nell'app ufficiale Novation, Session/Drums/Keys/User cambiano il *layout* dell'intera superficie (griglia clip Ableton / drum rack cromatico / tastiera a scala / custom). Questo non si applica 1:1 a Launchpad Studio, che usa l'intera griglia in modo esclusivo per il lancio di loop/campioni. La soluzione adottata reinterpreta lo *spirito* di ciascun tasto nel linguaggio di questa app, riusando quanto più possibile l'infrastruttura di riproduzione già esistente (one-shot con trim, pitch-shift per semitoni, velocity).

Up/Down/Left/Right restano invariati (stop colonna, comportamento attuale) — fuori scope.

## Stato globale nuovo

- `let perfMode = null;` — `null` (griglia normale) | `'drums'` | `'keys'`.
- `let drumKit = makeEmptyGrid();` — griglia 8×8 indipendente da `banks`, stessa forma di `clips[r][c]` (vedi sotto). Condivisa tra tutti i banchi/sessioni, non fa parte di `banks[]`.
- Nessun nuovo stato per Keys: usa `clips[selected.r][selected.c]` del banco attivo (qualunque esso sia).

Forma di un elemento `drumKit[r][c]` (identica ai clip normali, il campo `mode` è presente ma **ignorato** in performance — sempre trattato come one-shot):
```
{ buffer, name, raw, mime, mode, reversed, origBuffer, revBuffer, gain, pitch, choke, trimStart, trimEnd }
```
(nessun campo `steps` — il kit non partecipa allo step sequencer).

## Helper "griglia attiva"

```js
function activeGrid(){ return perfMode==='drums' ? drumKit : clips; }
```
Tutte le funzioni di editing pad (selectPad, renderPad, loadFileToPad, clearBtn, padMode/clipRev/clipGain/clipPitch/clipChoke handlers, trim slider handlers, drawWaveform, copyClipBtn/pasteClipBtn, toggleStep/clearSteps — questi ultimi due restano disabilitati/no-op se `perfMode==='drums'` dato che il kit non ha step sequencer) vengono aggiornate per leggere/scrivere tramite `activeGrid()` invece di `clips` direttamente. `renderAll()`/refreshAllLeds()` restano invariate nella firma ma il loro contenuto dipende da `activeGrid()`/`perfMode` per colori e stato.

`selected.r/selected.c` restano gli stessi indici (0-7,0-7) sia in modalità kit sia normale — semplicemente puntano a celle di array diversi a seconda di `perfMode`.

## Comportamento dei 4 tasti (onMidiMessage, note/CC 95-98)

```js
if(d1===95){ // Session
  if(perfMode!==null){ exitPerfMode(); } else { stopAll(); }
  return;
}
if(d1===96){ // Drums
  perfMode = (perfMode==='drums') ? null : 'drums';
  onPerfModeChanged();
  return;
}
if(d1===97){ // Keys
  perfMode = (perfMode==='keys') ? null : 'keys';
  onPerfModeChanged();
  return;
}
if(d1===98){ // User
  resyncAll();
  return;
}
```
`exitPerfMode()` = `perfMode=null; onPerfModeChanged();`. `onPerfModeChanged()` aggiorna la UI a schermo (banner Keys, bottone "Drums Kit" attivo/non attivo nella barra banchi), richiama `renderAll()` e `refreshAllLeds()` (che ora dipendono da `perfMode`), e se si sta uscendo da `'drums'` richiama anche `selectPad(selected.r,selected.c)` per ripopolare l'editor col contenuto del banco tornato attivo.

Selezionare un banco A/B/C/D (`switchBank`) mentre `perfMode!==null` chiama prima `exitPerfMode()`.

## Comportamento della griglia in ciascun perfMode

I loop dei banchi **continuano a suonare invariati** in tutti i casi (lo scheduler/i loop attivi non vengono toccati da un cambio di `perfMode`).

### `perfMode===null` (normale)
Invariato rispetto a oggi: `triggerDown`/`triggerUp` su `clips[r][c]` secondo il `mode` del clip.

### `perfMode==='drums'`
Note On sulla griglia (velocity `d2`) → riproduzione **sempre one-shot momentanea** di `drumKit[r][c]` (indipendentemente dal suo campo `mode`), usando la stessa logica di `playOnce` (rispetta trim/pitch/reversed/choke) ma con gain scalato da velocity: `gainFor(clip) * (d2/127)`. Note Off ignorato (il suono va sempre a compimento, come un vero drum hit). Polifonico: ogni pressione crea una voce indipendente in `oneShots`, nessun furto tra pad diversi a meno che l'utente imposti un `choke` sul kit stesso (già supportato da `applyChoke`).

### `perfMode==='keys'`
Suona **sempre** `clips[selected.r][selected.c]` del banco attivo (non `drumKit`), a un'intonazione aggiuntiva rispetto al pitch già impostato sul clip. Nuova funzione:
```js
function keysPitchOffset(r,c){ return (7-r)*5 + c; }  // isomorfa a quarte, riga 0=alto=piu' acuta
```
Note On (velocity `d2`) → avvia riproduzione **stile gate** (come `startGate`, non `playOnce`): parte con `loopStart/loopEnd` dal trim del clip, `playbackRate` include l'offset extra (`rateFor(clip) * 2^(keysPitchOffset(r,c)/12)`), gain scalato da velocity. Note Off → ferma quella voce con dissolvenza (come `stopGate`). Polifonico: serve una mappa di voci attive per pad analoga a `gateSrc` ma separata (es. `keysSrc`, stessa chiave `r*8+c`) per non confliggere con eventuali voci gate del banco normale.

Se `clips[selected.r][selected.c]` è vuoto, i tasti non fanno nulla (nessun errore). Le voci di `keysSrc` sono `BufferSource` indipendenti, scollegate da `trackState`: se il clip selezionato sta *anche* girando in loop sulla griglia normale, le due riproduzioni coesistono senza interferire (stessa logica già usata da `playOnce`/`oneShots`, che oggi convivono già con i loop).

## LED

- I 4 tasti superiori (95-98) vengono sempre accesi: Session colore neutro fisso; Drums e Keys più luminosi/colore acceso quando `perfMode` corrisponde, altrimenti dim; User colore neutro fisso. Nuovo helper `setTopLed(note,color,mode)` che manda `[status,note,color]` direttamente (note 91-98), riusato da `refreshAllLeds()`.
- `perfMode==='drums'`: i pad con `drumKit[r][c]` caricato si accendono con un colore dedicato fisso (distinto dai colori-categoria dei banchi, es. arancione), quelli vuoti spenti.
- `perfMode==='keys'`: tutta la griglia si accende di un colore uniforme dedicato (es. ciano), a prescindere dal contenuto — segnala "qui suoni, non lanci".
- `perfMode===null`: invariato (logica attuale di `updateLed`).

## Persistenza

`drumKit` viene serializzato/deserializzato esattamente come una griglia di `banks[b]` (stesso helper di serializzazione per-clip già usato da `saveBtn.onclick`/`buildAutosaveSnapshot`/`setInput.onchange`/`restoreAutosave`), aggiunto come campo facoltativo `drumKit:[...]` (stessa forma di un elemento di `out.banks`, lista di `{r,c,...}` per le celle non vuote) accanto a `banks` nel salvataggio `.lpstudio` e nell'autosave. File `.lpstudio` vecchi (v1/v2, senza `drumKit`) restano compatibili: kit vuoto di default, nessun bump di versione necessario (campo additivo, letto con `Array.isArray(data.drumKit)?...:[]`).

`perfMode` **non** viene salvato né incluso in Undo/Redo (`captureState`/`applyState`) — è stato di sessione/UI transitorio, stesso trattamento di `selected.r/selected.c` oggi. Il contenuto di `drumKit` invece **sì**: fa parte di `captureState`/`applyState` e dell'autosave (i suoi campi sono soggetti a `pushUndo()` esattamente come i clip di un banco: caricare/cancellare/modificare un pad del kit chiama `pushUndo()`).

## UI a schermo

- Nuovo bottone **"🥁 Drums Kit"** nella barra banchi, accanto ad A/B/C/D: al click, `perfMode = perfMode==='drums' ? null : 'drums'` (stesso toggle del tasto fisico), e chiama `onPerfModeChanged()`.
- Nuovo bottone **"🎹 Keys"** vicino: stesso toggle per `'keys'`.
- Banner testuale visibile quando `perfMode!==null` che spiega cosa sta succedendo (es. "🥁 Modalità Drums Kit — i pad suonano il kit dedicato" / "🎹 Modalità Keys — i pad suonano [nome clip selezionato] a intonazioni diverse").
- I click col mouse sulla griglia rispettano `perfMode` esattamente come i pad fisici (stessa funzione `triggerDown`/`triggerUp`, che ora ramifica su `perfMode` a monte del comportamento per-clip esistente).

## Testing (TDD, harness esistente)

Nuovi test in `scratchpad/test_perfmode_*.js`:
1. Tasti 95/96/97/98 cambiano `perfMode` correttamente (toggle Drums/Keys, Session esce o ferma tutto, User fa resync) — via `onMidiMessage`.
2. In `'drums'`, un Note On sulla griglia suona `drumKit[r][c]` (non `clips[r][c]`) come one-shot, gain scalato da velocity, a prescindere dal `mode` del kit.
3. In `'keys'`, Note On/Off sulla griglia avvia/ferma una voce gate sul clip selezionato, con `playbackRate` che riflette `keysPitchOffset(r,c)` sommato al pitch del clip.
4. I loop attivi di un banco continuano a suonare (playing=true, trackState invariato) mentre si entra/esce da `perfMode`.
5. Selezionare un banco (`switchBank`) mentre `perfMode!==null` esce automaticamente dall'overlay.
6. `.lpstudio` e autosave: round-trip di `drumKit` (salva/riapri, verifica contenuto), retrocompatibilità con file senza `drumKit`.
7. `captureState`/`applyState`: modificare il kit è annullabile; `perfMode` non fa parte dello stato annullabile.
8. LED: `updateLed`/nuovo `setTopLed` restituiscono colori diversi per `drumKit` popolato/vuoto e per stato attivo/inattivo di Drums/Keys.

Rebuild (`assemble.py`) e verifica byte-identica sorgente/generato dopo ogni fix, come da prassi del progetto.

## Fuori scope (esplicitamente escluso per ora)

- Scala musicale selezionabile per Keys (solo isomorfa a quarte, fissa).
- Editor "a schermo" separato per il kit diverso dal riuso dell'editor pad esistente.
- Persistenza di `perfMode` tra sessioni/autosave.
- Cambiare cosa fanno Up/Down/Left/Right (restano "ferma colonna").
