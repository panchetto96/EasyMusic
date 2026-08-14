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

## Riconoscimento categoria (drums/perc/bass/melodic/fx/vocal)

`build_genres.py` definisce `CATEGORY_KEYWORD_MAP`/`category_of_name()`: riconosce
la categoria di un suono dal suo NOME (parola chiave, non solo dal nome esatto),
cosi' "Drums 1"/"Acoustic Drums"/"Kick"/"Snare" finiscono tutti in 'drums' anche
se non si chiamano allo stesso modo. Deve restare IDENTICO a
`CATEGORY_KEYWORD_MAP`/`categoryOf` in `_sorgente/launchpad-studio.html` (stesso
nome delle categorie, stesse parole chiave) - altrimenti build/repack lato Python
e l'app a runtime classificano lo stesso suono in modo diverso.

`build_pack()` (dentro `build_genres.py`) alinea ogni categoria all'inizio di una
colonna nuova, cosi' una colonna non mescola mai due categorie diverse - fix del
14/08/2026 (prima, una categoria con un numero di file non multiplo di 8 lasciava
che la successiva riempisse il resto della colonna).

```
python repack_genres_by_category.py   # riordina genres.json GIA' ESISTENTE per
                                       # categoria, SENZA ritrascodificare (secondi,
                                       # non minuti) - usalo se genres.json e' stato
                                       # generato prima del fix del 14/08/2026, o se
                                       # sospetti colonne con categorie miste
python build_drumkit_preset.py        # rilancialo dopo: usa lo stesso
                                       # riconoscimento per parola chiave (non piu'
                                       # solo "il nome contiene 'drum'"), prende
                                       # quindi anche Kick/Snare/HiHat/Beat/ecc.
```

## Cosa NON fanno

Non toccano i file `.lpstudio` in `Launchpad Sets/` (quelli sono già
snapshot completi e indipendenti, si aprono con "Apri set" nell'app — non
serve/non c'entra questa pipeline). Non toccano `_Archivio/` o
`Registrazioni/`, se esistono altrove.
