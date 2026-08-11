#!/usr/bin/env python3
"""
assemble.py — genera "Launchpad Studio.html" (app con generi incorporati)
a partire dai tre pezzi presenti in questa cartella:

  launchpad-studio.html  = l'app BASE, senza generi (IL SORGENTE DA EDITARE)
  genres.json            = i dati dei 9 generi (audio Opus in base64)
  genre_ui.js            = il codice della barra "Genere" + funzione loadGenre

Inietta un blocco <script> (const GENRES = {...}; + genre_ui.js) subito prima
di </body> e scrive il file finale.

USO:
  python3 assemble.py                       # -> ../Launchpad Studio.html
  python3 assemble.py /percorso/out.html    # output personalizzato

Dopo la build, l'app finale NON va editata a mano: modifica launchpad-studio.html
(o genre_ui.js / genres.json) e ri-esegui questo script.
"""
import sys, os, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC   = HERE / "launchpad-studio.html"
DATA  = HERE / "genres.json"
UI    = HERE / "genre_ui.js"
OUT   = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "Launchpad Studio.html"

def main():
    for p in (SRC, DATA, UI):
        if not p.exists():
            sys.exit(f"ERRORE: manca {p.name} in {HERE}")

    src  = SRC.read_text(encoding="utf-8")
    ui   = UI.read_text(encoding="utf-8")
    # valida che genres.json sia JSON corretto e conta le clip
    genres = json.loads(DATA.read_text(encoding="utf-8"))
    nclip  = sum(len(g.get("clips", [])) for g in genres.values())
    data_text = DATA.read_text(encoding="utf-8").strip()

    block = "\n<script>\nconst GENRES = " + data_text + ";\n" + ui.rstrip() + "\n</script>\n\n"

    idx = src.rfind("</body>")
    if idx == -1:
        sys.exit("ERRORE: </body> non trovato nel sorgente")
    out = src[:idx] + block + src[idx:]

    OUT.write_text(out, encoding="utf-8", newline="")  # newline="" evita che Windows traduca \n in \r\n
    mb = OUT.stat().st_size / 1e6
    print(f"OK: {OUT.name}  ({mb:.1f} MB)  — {len(genres)} generi, {nclip} clip")

if __name__ == "__main__":
    main()
