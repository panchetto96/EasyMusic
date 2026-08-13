# Modifiche suono — Fade, Tempo/Tono indipendenti, Filtro per pad

## Contesto

Oggi le uniche modifiche disponibili per un pad sono taglio (trim), pitch accoppiato alla velocità (resampling: cambiare pitch cambia anche quanto veloce suona il campione), reverse e BPM di origine — tutte nel pannello "Suoni & Set". Manca: un modo per sfumare l'entrata/uscita di un suono, per cambiare velocità o intonazione **indipendentemente** l'una dall'altra (vero time-stretch), e un filtro applicabile a un singolo pad invece che solo all'intero missaggio.

L'utente vuole una **nuova sezione separata da "Suoni & Set"**, dedicata a queste modifiche, mantenendo intatto tutto ciò che esiste già (compreso il vecchio Pitch accoppiato, utile come effetto creativo).

## Sezione 1 — Motore di time-stretch

Tempo e Tono indipendenti richiedono un algoritmo che oggi non esiste nel progetto (il resampling attuale non può separarli). Si usa **SoundTouch.js** (algoritmo WSOLA, collaudato), vendorizzata nel file assemblato — nessuna richiesta di rete a runtime, coerente con l'app autocontenuta in un solo file HTML.

**API di riferimento** (libreria core, elaborazione offline via `putSamples`/`receiveSamples`, non il wrapper AudioWorklet pensato per lo streaming in tempo reale — qui non serve, vedi Sezione 3):

```js
const st = new SoundTouch({ sampleRate: buffer.sampleRate });
st.tempo = 1.2;           // velocita', indipendente dal tono
st.pitchSemitones = -2;   // intonazione in semitoni, indipendente dalla velocita'
st.putSamples(interleavedInputSamples);
st.flush();
let offset = 0; const chunk = new Float32Array(4096);
while (st.receiveSamples(chunk, chunk.length) > 0) { /* accumula chunk in un buffer di output */ offset += chunk.length; }
```

Il bundle browser-compatibile esatto (nome del file, se serve un adattamento per l'iniezione stile `genre_ui.js`) va verificato/vendorizzato in fase di implementazione — lo spec fissa la libreria e il contratto, non il file esatto da scaricare.

- **Applicazione**: OFFLINE, non in tempo reale. Quando l'utente cambia Tempo o Tono e rilascia lo slider, l'app prende il buffer **originale** del clip (mai quello già elaborato, per non degradare la qualità ad ogni modifica successiva — stesso principio già usato da Reverse con `origBuffer`), lo passa per SoundTouch coi parametri correnti (tempo E pitchSemitones assieme, se entrambi sono stati modificati), e sostituisce il buffer di riproduzione del clip col risultato.
- **Quando parte**: al rilascio dello slider (`pointerup`/`change`), non ad ogni pixel trascinato — l'elaborazione richiede un tempo reale di calcolo, non è istantanea come il taglio. Durante l'elaborazione lo slider resta usabile ma il pad mostra un piccolo indicatore "Elaborazione…" (stesso stile testuale già usato altrove, es. lo stato "Carico…" del caricamento genere).
- **Cache**: il clip tiene sempre `origBuffer` (mai toccato) oltre al buffer attivo (`buffer`, quello effettivamente suonato) — esattamente come Reverse già fa con `origBuffer`/`revBuffer`. Se l'utente ha sia Reverse che Tempo/Tono attivi, l'ordine di applicazione è: parte da `origBuffer`, applica time-stretch, poi reverse (o viceversa — l'ordine non cambia il risultato percettivo per un effetto simmetrico come reverse, ma va scelto uno standard: qui reverse si applica **dopo** il time-stretch, così il time-stretch lavora sempre su audio "diritto").

## Sezione 2 — Nuova sezione UI "Modifiche suono"

Sezione collassabile separata (stesso stile `<details class="sec-details">` già usato per le altre), posizionata subito dopo "Suoni & Set", per il pad attualmente selezionato:

- **Fade in** — slider, secondi (0–2s)
- **Fade out** — slider, secondi (0–2s)
- **Tempo** — slider percentuale, 50%–200% (100% = nessuna modifica), rallenta/velocizza indipendente dal tono
- **Tono** — slider in semitoni, -12/+12 (0 = nessuna modifica) — stesso range del Pitch esistente, per coerenza con l'interfaccia già nota
- **Filtro** — knob singolo (0–1), stesso comportamento del filtro master ma solo su questo pad

Il vecchio **Pitch** (accoppiato, resampling) resta esattamente dov'è oggi in "Suoni & Set", invariato — è un effetto creativo diverso da "Tono", non va confuso né sostituito.

## Sezione 3 — Fade in/out e Filtro (tempo reale, nessuna elaborazione offline)

A differenza di Tempo/Tono, questi due sono economici e si applicano **live**, senza toccare il buffer:

- **Fade in/out**: rampa di guadagno lineare sul `GainNode` del pad, applicata all'avvio (`start`) e allo stop della riproduzione. Regolabile mentre il suono sta girando (il prossimo avvio/stop userà il nuovo valore), stesso principio già usato per gli altri controlli non distruttivi.
- **Filtro**: un `BiquadFilterNode` (tipo lowpass) inserito nella catena audio del pad tra la sorgente e il `GainNode` esistente, stessa curva di frequenza del filtro master (`20 * Math.pow(1000, filterVal)`, val 0–1) — coerenza con l'interfaccia già esistente. Live-regolabile via `setTargetAtTime`, come il filtro master.

## Sezione 4 — Interazione col BPM automatico

Il controllo **Tempo** e il motore di aggancio automatico del BPM (`sourceBpm`/`clipRate`/`tryEstablishTempoReference`) devono restare coerenti. Quando l'utente rallenta/velocizza un pad col nuovo controllo Tempo, **`clip.sourceBpm` si aggiorna automaticamente** di conseguenza (es. un pad a `sourceBpm=120` rallentato del 20% con Tempo diventa `sourceBpm=96`), così l'aggancio automatico continua a calcolare correttamente la velocità finale di quel pad rispetto agli altri.

Formalmente: `sourceBpmEffettivo = sourceBpmOriginale × tempoFactor` (dove `tempoFactor` è il moltiplicatore di velocità impostato dal nuovo controllo Tempo, es. 1.2 = 20% più veloce — coerente con l'esempio sopra: 120 rallentato del 20%, tempoFactor=0.8, dà 120×0.8=96). **Correzione 14/08/2026**: la prima stesura di questo spec riportava qui una divisione (`/tempoFactor`), in contraddizione con l'esempio sopra — la review del Task 4 ha trovato l'incoerenza e verificato che la moltiplicazione è quella corretta (coerente con `applyTimeStretch`: un buffer compresso da un tempoFactor>1 suona nativamente più veloce, quindi il suo BPM nativo aumenta, non diminuisce). Il valore **originale** (prima di qualunque Tempo manuale) resta comunque recuperabile: se l'utente riporta il controllo Tempo al centro (1.0), `sourceBpm` torna al valore di partenza — serve quindi tenere in memoria anche `sourceBpmOriginale` sul clip, non solo quello effettivo.

Il controllo **Tono** (pitch indipendente) **non** tocca `sourceBpm` — cambia solo l'intonazione, non la velocità percepita, quindi non ha nulla a che fare con l'aggancio del tempo.

## Sezione 5 — Persistenza

I nuovi valori (`fadeIn`, `fadeOut`, `tempoStretch`, `toneShift`, `filterCutoff`) si salvano con lo stesso meccanismo già esistente per taglio/pitch/reverse/BPM di origine — nessuna infrastruttura nuova:

- **Autosave** (IndexedDB): aggiunge i nuovi campi alla serializzazione già esistente per clip.
- **"Salva set"** (`.lpstudio`): stesso trattamento, nuovi campi nell'oggetto clip serializzato.
- **"Salva modifica"** (override per genere): stesso trattamento — se il pad viene da un genere caricato, i nuovi valori si salvano/riapplicano insieme a taglio/pitch/reverse/BPM di origine.
- **"Copia/Incolla impostazioni"**: i nuovi campi si aggiungono all'elenco già copiato (oggi: modo/gain/pitch/trim/choke/reverse).
- Il buffer **elaborato** (risultato del time-stretch) non va serializzato separatamente: si salva solo `origBuffer` (raw, come oggi) + i parametri (`tempoStretch`, `toneShift`) — al caricamento, l'app riapplica il time-stretch da capo sui parametri salvati, esattamente come già fa oggi per Reverse (salva il raw, riapplica reverse al caricamento).

## Testing (TDD, harness esistente)

1. Fade in/out: avviare un pad con fadeIn>0 pianifica una rampa di guadagno da 0 al livello target sulla durata impostata; fadeOut analogo allo stop.
2. Filtro per pad: cambiare il valore inserisce/aggiorna un `BiquadFilterNode` nella catena audio di quel pad, senza toccare altri pad né il filtro master.
3. Time-stretch: applicare Tempo=1.2 produce un buffer più corto (stessa intonazione, contenuto compresso in meno tempo); applicare Tono=+2 semitoni produce un buffer di durata invariata ma pitch shiftato (verificabile solo indirettamente nell'harness, es. controllando che `SoundTouch` sia stato chiamato coi parametri giusti — un vero controllo di qualità audio serve fatto a orecchio in Chrome).
4. Riportare Tempo/Tono a 0 (nessuna modifica) ripristina esattamente `origBuffer` come buffer attivo, senza rielaborazione.
5. Cambiare Tempo aggiorna `sourceBpm` proporzionalmente; riportare Tempo a 1.0 ripristina `sourceBpmOriginale`.
6. Cambiare Tono NON tocca `sourceBpm`.
7. Reverse + Tempo/Tono insieme: l'ordine di applicazione (time-stretch poi reverse) è deterministico e testabile.
8. Persistenza: autosave, Salva set, Salva modifica, Copia/Incolla portano tutti i 4 nuovi campi (`fadeIn`, `fadeOut`, `tempoStretch`, `toneShift`) più `filterCutoff` (dove applicabile) — stesso pattern dei test già esistenti per trim/pitch/sourceBpm.

Rebuild (`assemble.py`) e verifica in Chrome vero (Playwright) dopo l'implementazione, come da prassi del progetto — in particolare: il tempo di elaborazione di un time-stretch non blocca l'interfaccia, e l'audio risultante è effettivamente ascoltabile e coerente (velocità/tono cambiati come atteso).

## Fuori scope (esplicitamente escluso per ora)

- Time-stretch in tempo reale durante la riproduzione (richiederebbe un AudioWorklet dedicato — scartato per complessità, vedi Sezione 1).
- Filtro passa-alto/passa-banda per pad (solo passa-basso singolo knob, come il filtro master).
- Fade con curve non lineari (solo rampa lineare, come già fa il resto del progetto per le dissolvenze esistenti).
- Applicare Tempo/Tono al kit Drums (drumKit) — questa iterazione copre solo i banchi normali (`clips`), coerente con come "BPM di origine"/aggancio automatico sono già scoped solo ai banchi.
