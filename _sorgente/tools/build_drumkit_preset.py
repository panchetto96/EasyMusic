#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ricostruisce _sorgente/drumkit_preset.json: e' "l'insieme dei drum trovati nei
set" (confermato dall'utente il 13/08/2026) - qui prendiamo i clip con nome che
contiene "drum" dai generi gia' presenti in genres.json, fino a riempire 64 pad
(8x8), senza ripetere lo stesso genere piu' di 8 volte cosi' da avere varieta'.

USO: python build_drumkit_preset.py   (dopo build_genres.py)
"""
import json, re, pathlib

HERE = pathlib.Path(__file__).resolve().parent
SORGENTE = HERE.parent
GENRES_PATH = str(SORGENTE / 'genres.json')
OUT_PATH = str(SORGENTE / 'drumkit_preset.json')

DRUM_NAME_RE = re.compile(r'drum', re.IGNORECASE)


def main():
    with open(GENRES_PATH, encoding='utf-8') as f:
        genres = json.load(f)

    picked = []
    for gname in sorted(genres.keys()):
        clips = genres[gname]['clips']
        drum_clips = [c for c in clips if DRUM_NAME_RE.search(c['name'])]
        for c in drum_clips[:8]:
            picked.append({'name': gname + ' - ' + c['name'], 'mime': c['mime'], 'data': c['data']})
        if len(picked) >= 64:
            break

    picked = picked[:64]
    out = []
    for i, clip in enumerate(picked):
        r = i % 8
        c = i // 8
        out.append({'r': r, 'c': c, 'name': clip['name'], 'mime': clip['mime'], 'data': clip['data']})

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    print('drumkit_preset.json:', len(out), 'pad, generi usati:', len(set(o['name'].split(' - ')[0] for o in out)))


if __name__ == '__main__':
    main()
