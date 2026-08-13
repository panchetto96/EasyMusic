# Script di ricostruzione del catalogo audio

Scritti il 13/08/2026 dopo un evento che ha svuotato la cartella di lavoro
originale (`D:\MUSIC\Launchpad Studio`), inclusi `genres.json` e
`drumkit_preset.json` — mai tracciati da git perché troppo pesanti (vedi
`.gitignore`). Prima di questi script, ricostruire quei due file avrebbe
richiesto la conversazione originale con tutto il contesto della sessione;
ora basta rilanciarli.

**Precondizione:** i pacchetti audio Novation Anniversary (1st/2nd/3rd Drop)
devono essere disponibili in una cartella locale (di default
`C:\Users\panco\OneDrive\Desktop\music` — già sincronizzata su OneDrive,
quindi al sicuro anche se questo PC ha un problema). Se sono altrove, imposta
la variabile d'ambiente `LPSTUDIO_MUSIC_ROOT`.

**Precondizione:** `ffmpeg` deve essere raggiungibile. Il percorso di default
punta all'installazione via `winget install Gyan.FFmpeg` fatta durante il
recupero; se ffmpeg è altrove o su PATH, imposta `LPSTUDIO_FFMPEG=ffmpeg`.

## Uso

```
cd _sorgente/tools
python build_genres.py              # ~25 pacchetti-genere -> genres.json (qualche minuto)
python build_extra_genre.py         # demo/brani sciolti -> genere "Extra - Non catalogati"
python build_drumkit_preset.py      # kit Drums 64 pad, preso dai generi appena scritti
cd ..
python assemble.py                  # produce ../Launchpad Studio.html
```

Se un pacchetto specifico fallisce (rete, file corrotto, ecc.), si può
rilanciare solo quello: `python build_genres.py "Acid Techno"`.

## Cosa NON fanno

Non toccano i file `.lpstudio` in `Launchpad Sets/` (quelli sono già
snapshot completi e indipendenti, si aprono con "Apri set" nell'app — non
serve/non c'entra questa pipeline). Non toccano `_Archivio/` o
`Registrazioni/`, se esistono altrove.
