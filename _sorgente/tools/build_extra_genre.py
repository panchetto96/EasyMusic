#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genere "Extra - Non catalogati": brani demo interi e file sciolti trovati nella
cartella dei pacchetti Novation, non riconducibili a un genere specifico ma
comunque richiesti visibili dal catalogo. Vedi build_genres.py per il contesto.

USO: python build_extra_genre.py   (dopo build_genres.py)
"""
import os, json
from build_genres import ROOT, OUT_PATH, LOG_PATH, transcode_to_mp3_b64, clean_name

LOOSE_FILES = ['Lombok.mp3', 'Neon.mp3', 'Osaka.mp3', 'P.Billy.mp3']
DEMO_DIRS = [
    r'Novation Anniversary 3rd Drop\Demos',
    r'Novation Anniversary Pack 2nd Drop\DEMOS',
]
AUD_EXT = {'.wav', '.mp3', '.aif', '.aiff', '.ogg', '.flac', '.m4a'}


def main():
    files = []
    for f in LOOSE_FILES:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            files.append(p)
    for d in DEMO_DIRS:
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                fp = os.path.join(p, fn)
                if os.path.isfile(fp) and os.path.splitext(fn)[1].lower() in AUD_EXT:
                    files.append(fp)

    with open(LOG_PATH, 'a', encoding='utf-8') as log:
        log.write(f'[Extra - Non catalogati] {len(files)} file da trascodificare\n')
        clips = []
        failures = []
        for i, fpath in enumerate(files):
            b64, err = transcode_to_mp3_b64(fpath)
            if b64 is None:
                failures.append((fpath, err))
                log.write(f'  FALLITO: {fpath}\n    {err}\n')
                continue
            clips.append({'name': clean_name(os.path.basename(fpath)), 'mime': 'audio/mpeg', 'data': b64})
            log.write(f'  ...{i+1}/{len(files)}\n')
        log.flush()

    genres_out = {}
    idx = 0
    part = 1
    title = 'Extra - Non catalogati'
    while idx < len(clips):
        chunk = clips[idx:idx + 64]
        gtitle = title if part == 1 else f'{title} ({part})'
        clips_rc = []
        for j, clip in enumerate(chunk):
            c = j // 8
            r = j % 8
            clips_rc.append({'r': r, 'c': c, 'name': clip['name'], 'mime': clip['mime'], 'data': clip['data']})
        genres_out[gtitle] = {'clips': clips_rc}
        idx += 64
        part += 1

    with open(OUT_PATH, encoding='utf-8') as f:
        existing = json.load(f)
    existing.update(genres_out)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, separators=(',', ':'))

    print('Generi extra scritti:', list(genres_out.keys()))
    print('Fallimenti:', len(failures))
    for fp, err in failures:
        print('  -', fp, '->', err)


if __name__ == '__main__':
    main()
