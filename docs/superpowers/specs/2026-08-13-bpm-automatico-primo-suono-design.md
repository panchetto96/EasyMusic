# BPM automatico agganciato al primo suono che parte

## Contesto

Oggi il BPM di progetto è un valore unico impostato a mano (campo numerico + TAP), e "Sync BPM" (checkbox opzionale) fa sì che i clip con un BPM di origine noto (`clip.sourceBpm`, impostato quando si carica un genere/kit) vengano ri-accelerati/rallentati per allinearsi al BPM di progetto — la matematica è già tutta in `clipRate()`/`rateFor()`/`applyRates()`.

L'utente vuole che questo non sia più opzionale: il **primo loop che parte** (dopo uno Stop tutto o un Re-sync) stabilisce da solo il BPM di progetto, e tutti gli altri suoni con un BPM di origine noto — anche di generi/kit diversi, mischiati nello stesso banco — si adattano automaticamente. Nessun tasto da accendere.

## Meccanismo di riferimento

```js
let tempoReferenceSet = false;   // vero se il BPM di progetto e' gia' "agganciato" a un suono dall'ultimo stopAll/resyncAll
function tryEstablishTempoReference(clip){
  if(tempoReferenceSet || !clip || !clip.sourceBpm) return;
  bpm = clip.sourceBpm;
  document.getElementById('bpm').value = bpm;
  document.getElementById('bpmVal').textContent = bpm;
  tempoReferenceSet = true;
  applyRates();   // riallinea SUBITO qualunque cosa stia gia' suonando (con sourceBpm noto)
}
```

- Chiamata in **un solo punto**: l'inizio di `scheduleClip(r,c,when)` — la funzione che *sia* la pressione diretta di un pad Loop (via `triggerDown`) *sia* il lancio scena (via `launchScene`, un `scheduleClip` per colonna) già attraversano. Nessun altro hook necessario.
- Solo i pad in modalità **Loop** possono stabilire il riferimento (chiamano `scheduleClip`). One-shot (`playOnce`) e Gate (`startGate`) non lo chiamano mai — restano semplicemente *adattati* al riferimento attivo se hanno un `sourceBpm` (già oggi calcolano la loro velocità con `rateFor(clip)`, che userà il nuovo `bpm` non appena è stabilito), ma non possono diventare loro stessi il riferimento.
- **Lancio scena**: `launchScene` itera le colonne 0→7 chiamando `scheduleClip` in ordine — la prima colonna con un clip che ha un `sourceBpm` noto vince "gratis", senza bisogno di logica di priorità esplicita.
- **Reset**: `stopAll()` e `resyncAll()` impostano entrambi `tempoReferenceSet=false`. Nessuno dei due ricalcola subito un nuovo riferimento da quello che sta (eventualmente) già suonando — per scelta esplicita, resyncAll non ferma l'audio ma "scioglie" comunque l'aggancio: il prossimo suono che parte (anche uno già in corso, se lo ripremi) lo ristabilisce da zero.
- `clipRate()` perde la dipendenza dal checkbox: `return (clip && clip.sourceBpm) ? bpm/clip.sourceBpm : 1;` — l'adattamento è sempre attivo per qualunque clip con un BPM di origine noto, indipendentemente da chi ha stabilito il riferimento.
- Limite noto e accettato (non risolto in questa iterazione): se un pad Loop viene premuto mentre *altri* loop stanno già suonando sotto un vecchio riferimento appena sciolto (es. subito dopo un Re-sync), l'istante di partenza (`nextBoundary()`) viene calcolato **prima** che `scheduleClip` stabilisca il nuovo riferimento, quindi usa ancora il BPM precedente per quel singolo calcolo — una imprecisione di fase minima, autocorretta al giro successivo. Non è la pressione "a freddo" (nulla in riproduzione), che è il caso comune e non ne risente.

## BPM di origine per ogni pad (manuale + rilevamento assistito)

Oggi solo i clip caricati da un genere/kit hanno un `sourceBpm`. File trascinati a mano e registrazioni dal microfono non ce l'hanno mai, quindi non possono mai partecipare all'aggancio (né come riferimento né come adattati).

- Nuovo campo **"BPM di origine"** (numero) nel pannello di modifica, accanto a Pitch: editabile per **qualunque** pad, imposta/corregge `clip.sourceBpm` a mano. Vuoto = comportamento di oggi (velocità nativa, mai riferimento, mai adattato).
- Nuovo tasto **"🔍 Rileva BPM"** accanto al campo: analizza il buffer del pad selezionato e propone un valore nel campo (che resta comunque modificabile). Algoritmo "best effort" via autocorrelazione sull'inviluppo del segnale:

```js
// Stima "best effort" del tempo di un AudioBuffer: inviluppo (RMS a finestre di ~10ms) -> autocorrelazione
// sull'intervallo di lag corrispondente a 60-200 BPM -> il lag col picco piu' alto e' il periodo del beat.
// Funziona bene su loop ritmici con transienti chiari, male su contenuto non percussivo (voce, ambient):
// e' un suggerimento di partenza, non una certezza — l'utente lo conferma o corregge nel campo.
function detectBpm(buffer){
  const sr=buffer.sampleRate, data=buffer.getChannelData(0);
  const hop=Math.round(sr*0.01);   // finestre da ~10ms
  const env=[]; for(let i=0;i<data.length;i+=hop){ let s=0; for(let j=i;j<Math.min(i+hop,data.length);j++) s+=data[j]*data[j]; env.push(Math.sqrt(s/hop)); }
  const envRate=sr/hop;
  const minLag=Math.round(envRate*60/200), maxLag=Math.round(envRate*60/60);   // 60-200 BPM
  let bestLag=-1, bestScore=-Infinity;
  for(let lag=minLag; lag<=maxLag && lag<env.length; lag++){
    let score=0; for(let i=0;i<env.length-lag;i++) score+=env[i]*env[i+lag];
    if(score>bestScore){ bestScore=score; bestLag=lag; }
  }
  if(bestLag<=0) return null;
  return Math.round(60/(bestLag/envRate));
}
```

Il tasto chiama `detectBpm(clip.buffer)` sul pad selezionato e, se restituisce un numero, lo scrive nel campo "BPM di origine" (senza salvarlo finché l'utente non conferma/modifica e — se il pad viene da un genere caricato — preme "Salva modifica" per renderlo persistente per quel genere, oppure resta comunque nel clip in memoria per gli altri banchi/kit).

## UI

- Il checkbox **"Sync BPM"** sparisce dalla vista (stesso trattamento già usato per Gain/Choke: `display:none`, codice/handler lasciati intatti, non più raggiungibile dall'utente) — il comportamento che attivava è ora sempre attivo.
- Campo **BPM** e tasto **TAP** restano pienamente modificabili in ogni momento, come oggi.

## Persistenza

Nessun lavoro aggiuntivo: `clip.sourceBpm` è già serializzato in ogni percorso di salvataggio esistente (autosave, Salva/Apri set, kit personalizzati, "Salva modifica" per genere) — impostarlo a mano o via rilevamento è indistinguibile, per il resto del sistema, da un `sourceBpm` arrivato da un genere.

## Testing (TDD, harness esistente)

1. `tryEstablishTempoReference`: stabilisce `bpm`/`tempoReferenceSet` la prima volta con un clip che ha `sourceBpm`; no-op se già stabilito, se il clip è vuoto, o se non ha `sourceBpm`.
2. Pressione di un pad Loop con `sourceBpm` mentre `tempoReferenceSet===false` aggiorna `bpm` e il campo a schermo.
3. Un secondo Loop (diverso `sourceBpm`) premuto dopo che il riferimento è già stabilito **non** cambia `bpm`, ma la sua `rateFor()` riflette il rapporto verso il `bpm` corrente.
4. `stopAll()` e `resyncAll()` azzerano `tempoReferenceSet`; il prossimo Loop premuto ristabilisce un nuovo riferimento.
5. Lancio scena con più colonne: vince la prima colonna (da sinistra) con `sourceBpm` noto tra quelle lanciate.
6. One-shot/Gate non chiamano mai `tryEstablishTempoReference` (restano solo "adattati").
7. `clipRate()` applica il rapporto BPM a prescindere da qualunque stato `syncBpm` residuo (il checkbox non esiste più come influenza sul comportamento).
8. `detectBpm()`: su un segnale sintetico con periodicità nota (es. un click ogni N campioni) restituisce un BPM vicino a quello atteso; su rumore bianco senza struttura ritmica non deve lanciare eccezioni (può restituire `null` o un valore qualunque, non è garantita l'accuratezza).
9. Campo "BPM di origine" modificabile per un pad senza `sourceBpm` pregresso (file trascinato): impostarlo lo rende da quel momento un candidato valido per l'aggancio.

Rebuild (`assemble.py`) e verifica in Chrome vero (Playwright) dopo l'implementazione, come da prassi del progetto — in particolare: due loop di generi diversi lanciati in sequenza si sincronizzano davvero all'ascolto/ai tempi di scheduling, e Stop tutto/Re-sync sciolgono davvero l'aggancio.

## Fuori scope (esplicitamente escluso per ora)

- Tono preservato durante l'aggancio automatico (richiederebbe un motore di time-stretch indipendente dal pitch — il progetto "B", non ancora costruito). Per ora il tono cambia insieme alla velocità, come già faceva Sync BPM manuale.
- Correzione perfetta della fase quando un Loop viene lanciato mentre altri suonano sotto un riferimento appena sciolto (vedi limite noto sopra) — l'utente ha già Re-sync per correggere manualmente.
- Rilevamento BPM per Gate/One-shot (il tasto "Rileva BPM" funziona su qualunque pad selezionato, ma l'aggancio automatico resta comunque riservato ai Loop).
- Persistenza di `tempoReferenceSet` tra sessioni (è stato transitorio, si azzera a ogni ricarica pagina, come `perfMode`).
