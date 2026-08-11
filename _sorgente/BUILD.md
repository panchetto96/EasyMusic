# Build — Launchpad Studio

L'app finale `../Launchpad Studio.html` è **generata** da questi file. Non editarla a mano.

## File in questa cartella
- `launchpad-studio.html` — l'app BASE (senza generi). **È il sorgente da editare** per modificare la logica dell'app.
- `genres.json` — i dati dei 9 generi (audio Opus in base64, ~76 MB, 348 clip).
- `genre_ui.js` — il codice della barra "Genere" + la funzione `loadGenre` (glue tra dati e app).
- `assemble.py` — lo script di build.

## Come rigenerare l'app
```
cd _sorgente
python assemble.py
```
Produce `../Launchpad Studio.html`. Per un output alternativo: `python assemble.py /percorso/out.html`.

Su Windows **usa `python`, non `python3`**: qui `python3` è intercettato dall'App Execution Alias di Windows e prova ad aprire il Microsoft Store invece di eseguire lo script (verificato: `python3 --version` fallisce con exit code 49, `python --version` funziona). Su Mac/Linux di solito è il contrario ed è `python3` quello giusto — usa quello disponibile sul tuo sistema.

`assemble.py` inietta un `<script>` (con `const GENRES = ` + `genres.json` + `genre_ui.js`) subito prima di `</body>` nel sorgente. Rigenera l'app **identica al byte** a quella attuale.

## Flusso di lavoro tipico
1. Modifica `launchpad-studio.html` (logica app) — oppure `genre_ui.js` / `genres.json`.
2. Controlla la sintassi: `node --check genre_ui.js` (e, per l'app, estrai gli `<script>` e passali a `node --check`).
3. Esegui `python assemble.py` (vedi nota Windows sopra).
4. Apri `../Launchpad Studio.html` in Chrome per provare.

## Note
- Serve solo Python 3 (nessuna dipendenza esterna). `node` è utile per il controllo sintassi.
- Rigenerare `genres.json` dai loop Novation grezzi non è necessario per lavorare sull'app: vedi `../SVILUPPO.md` §6.
