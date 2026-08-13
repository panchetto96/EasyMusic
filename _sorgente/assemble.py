#!/usr/bin/env python3
"""
assemble.py — genera "Launchpad Studio.html" (app con generi incorporati)
a partire dai pezzi presenti in questa cartella:

  launchpad-studio.html   = l'app BASE, senza generi (IL SORGENTE DA EDITARE)
  genres.json             = i dati dei 9 generi (audio Opus in base64)
  genre_ui.js             = il codice della barra "Genere" + funzione loadGenre
  drumkit_preset.json     = 64 pad di fabbrica per il kit Drums (audio Opus in base64)
  drumkit_preset_ui.js    = loadDrumKitPresetIfEmpty()
  catalog_ui.js           = pannello "Catalogo suoni" + barra kit personalizzati (+ Nuovo/Salva/Elimina/Esporta/Importa kit)

Inietta un blocco <script> (GENRES + genre_ui.js + DRUM_KIT_PRESET + drumkit_preset_ui.js + catalog_ui.js)
subito prima di </body> e scrive il file finale.

USO:
  python3 assemble.py                       # -> ../Launchpad Studio.html
  python3 assemble.py /percorso/out.html    # output personalizzato

Dopo la build, l'app finale NON va editata a mano: modifica launchpad-studio.html
(o gli altri sorgenti) e ri-esegui questo script.
"""
import sys, os, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC     = HERE / "launchpad-studio.html"
DATA    = HERE / "genres.json"
UI      = HERE / "genre_ui.js"
DKDATA  = HERE / "drumkit_preset.json"
DKUI    = HERE / "drumkit_preset_ui.js"
CATUI   = HERE / "catalog_ui.js"
OUT   = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "Launchpad Studio.html"

def main():
    for p in (SRC, DATA, UI, DKDATA, DKUI, CATUI):
        if not p.exists():
            sys.exit(f"ERRORE: manca {p.name} in {HERE}")

    src   = SRC.read_text(encoding="utf-8")
    ui    = UI.read_text(encoding="utf-8")
    dkui  = DKUI.read_text(encoding="utf-8")
    catui = CATUI.read_text(encoding="utf-8")
    # valida che genres.json / drumkit_preset.json siano JSON corretti e conta le clip
    genres = json.loads(DATA.read_text(encoding="utf-8"))
    nclip  = sum(len(g.get("clips", [])) for g in genres.values())
    data_text = DATA.read_text(encoding="utf-8").strip()
    drumkit = json.loads(DKDATA.read_text(encoding="utf-8"))
    ndrum   = len(drumkit)
    drumkit_text = DKDATA.read_text(encoding="utf-8").strip()

    block = ("\n<script>\nconst GENRES = " + data_text + ";\n" + ui.rstrip()
             + "\nconst DRUM_KIT_PRESET = " + drumkit_text + ";\n" + dkui.rstrip()
             + "\n" + catui.rstrip()
             + "\n</script>\n\n")

    idx = src.rfind("</body>")
    if idx == -1:
        sys.exit("ERRORE: </body> non trovato nel sorgente")
    out = src[:idx] + block + src[idx:]

    OUT.write_text(out, encoding="utf-8", newline="")  # newline="" evita che Windows traduca \n in \r\n
    mb = OUT.stat().st_size / 1e6
    print(f"OK: {OUT.name}  ({mb:.1f} MB)  — {len(genres)} generi, {nclip} clip, kit Drums {ndrum} pad")

if __name__ == "__main__":
    main()
