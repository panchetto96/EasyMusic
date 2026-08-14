#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ricostruisce _sorgente/genres.json a partire dai pacchetti Novation Anniversary
(1st/2nd/3rd Drop), trascodificando ogni campione WAV/AIF/M4A/MP3 in MP3
128kbps/44.1kHz stereo e incorporandolo come base64, nello schema che
l'app/assemble.py si aspettano: GENRES[title] = {bpm, clips:[{r,c,name,mime,data}]}.

Scritto il 13/08/2026 dopo un evento di perdita dati che ha svuotato la
cartella di lavoro originale (D:\\MUSIC\\Launchpad Studio) - questo script
E' la rete di sicurezza per quell'evenienza: se genres.json/drumkit_preset.json
spariscono di nuovo, bastano questi 3 script (questo + build_drumkit_preset.py
+ build_extra_genre.py) per rigenerarli, SENZA bisogno di ricostruire nulla
a memoria/conversazione. I pacchetti Novation grezzi devono restare disponibili
in ROOT (sono su OneDrive in questo momento, quindi gia' al sicuro in cloud).

USO:
  python build_genres.py                       # tutti i 25 pacchetti
  python build_genres.py "Acid Techno" "Legacy" # solo alcuni (utile per riprovare dopo un fallimento)

Richiede ffmpeg. Se non e' su PATH, imposta FFMPEG sotto o la variabile
d'ambiente LPSTUDIO_FFMPEG.
"""
import os, sys, re, json, base64, subprocess, tempfile, pathlib

HERE = pathlib.Path(__file__).resolve().parent          # _sorgente/tools
SORGENTE = HERE.parent                                   # _sorgente

ROOT = os.environ.get('LPSTUDIO_MUSIC_ROOT', r'C:\Users\panco\OneDrive\Desktop\music')
FFMPEG = os.environ.get('LPSTUDIO_FFMPEG',
    r'C:\Users\panco\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe')
OUT_PATH = str(SORGENTE / 'genres.json')
LOG_PATH = str(pathlib.Path(tempfile.gettempdir()) / 'lpstudio_build_genres_log.txt')

AUD_EXT = {'.wav', '.mp3', '.aif', '.aiff', '.ogg', '.flac', '.m4a'}

# categoria (per il bucketing colonne) dal nome della sottocartella
CATEGORY_MAP = {
    'bass': 'bass', 'drums': 'drums', 'drum': 'drums', 'percussion': 'perc',
    'percussion loops': 'perc', 'melodic': 'melodic', 'music loops': 'melodic',
    'fx': 'fx', 'vocal': 'vocal', 'vocals': 'vocal', 'extra': 'extra',
    'acoustic drum loops': 'drums', 'novation bass loops': 'bass',
    'novation drum loops': 'drums', 'novation fx': 'fx', 'novation melodic loops': 'melodic',
}
CATEGORY_ORDER = ['drums', 'perc', 'bass', 'melodic', 'fx', 'vocal', 'extra']

# Riconoscimento categoria dal NOME del singolo campione (non dalla cartella), per parola chiave -
# deve restare identico a CATEGORY_KEYWORD_MAP/categoryOf in _sorgente/launchpad-studio.html, cosi'
# lo stesso suono viene classificato allo stesso modo sia lato Python (build/repack) sia a runtime
# nell'app (colorazione colonne, validazione drag&drop dal catalogo). Usato da
# build_drumkit_preset.py e da repack_genres_by_category.py.
CATEGORY_KEYWORD_MAP = [
    ('drums', re.compile(r'\b(?:drum|drums|kick|snare|hat|hihat|clap|tom|cymbal|ride|crash|rim|beat|beats)\d*\b')),
    ('perc', re.compile(r'\b(?:perc|percs|percussion|shaker|tambourine|conga|bongo|cajon|djembe)\d*\b')),
    ('bass', re.compile(r'\b(?:bass|subbass|bassline)\d*\b')),
    ('vocal', re.compile(r'\b(?:vocal|vocals|vox|voice|chant|acapella)\d*\b')),
    ('melodic', re.compile(r'\b(?:synth|lead|melodic|melody|melo|pluck|arp|arpeggio|piano|keys|key|chord|chords|stab|string|strings|guitar|flute|brass|organ|choir|riff)\d*\b')),
    ('fx', re.compile(r'\b(?:fx|riser|sweep|impact|whoosh|uplifter|downlifter|transition|noise|texture|atmosphere|ambience)\d*\b')),
]
KNOWN_KEYWORD_CATEGORIES = {cat for cat, _ in CATEGORY_KEYWORD_MAP}
_TRAILING_NUM_RE = re.compile(r'[\s_]*\d+[A-Za-z]?(-\d+)?\s*$')


def category_of_name(name):
    n = (name or '').strip().lower()
    normalized = re.sub(r'[^a-z0-9]+', ' ', n).strip()
    for cat, rx in CATEGORY_KEYWORD_MAP:
        if rx.search(normalized):
            return cat
    stripped = _TRAILING_NUM_RE.sub('', n).strip()
    return stripped or n

# (percorso relativo a ROOT, titolo genere pulito, bpm o None)
PACKS = [
    (r'Novation Anniversary 3rd Drop\80s Synthpop (Dm, 87bpm)', '80s Synthpop', 87),
    (r'Novation Anniversary 3rd Drop\Acid Techno (Ab, 131bpm)', 'Acid Techno', 131),
    (r'Novation Anniversary 3rd Drop\Aerial Pop (Bm, 150bpm)', 'Aerial Pop', 150),
    (r'Novation Anniversary 3rd Drop\EBM Energy (Fm, 120bpm)', 'EBM Energy', 120),
    (r'Novation Anniversary 3rd Drop\Hard Hit Trap (Em, 148bpm)', 'Hard Hit Trap', 148),
    (r'Novation Anniversary 3rd Drop\Horror Trap (Fm, 146bpm)', 'Horror Trap', 146),
    (r'Novation Anniversary 3rd Drop\Indie Hip Hop (Amaj, 84bpm)', 'Indie Hip Hop', 84),
    (r'Novation Anniversary 3rd Drop\Industrial Techno (Gm, 140bpm)', 'Industrial Techno', 140),
    (r'Novation Anniversary 3rd Drop\Japanese LoFi Hip Hop (Ebm, 82bpm)', 'Japanese LoFi Hip Hop', 82),
    (r'Novation Anniversary 3rd Drop\Middle Eastern Electronic (Dbm, 99bpm)', 'Middle Eastern Electronic', 99),
    (r'Novation Anniversary Pack 2nd Drop\East Coast Hip Hop', 'East Coast Hip Hop', None),
    (r'Novation Anniversary Pack 2nd Drop\Industrial Techno', 'Industrial Techno (Classic)', None),
    (r'Novation Anniversary Pack 2nd Drop\Japanese LoFi', 'Japanese LoFi', None),
    (r'Novation Anniversary Pack 2nd Drop\Modern Hip Hop', 'Modern Hip Hop', None),
    (r'Novation Anniversary Pack 2nd Drop\Phonk Hip Hop', 'Phonk Hip Hop', None),
    (r'Novation Anniversary Pack 2nd Drop\Retro Disco', 'Retro Disco', 120),
    (r'Novation Anniversary Pack 2nd Drop\Trip Hop', 'Trip Hop', None),
    (r'Novation Anniversary Pack 2nd Drop\Vaporwave', 'Vaporwave', None),
    (r'Novation Anniversary Pack 2nd Drop\World Flute Trap', 'World Flute Trap', None),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation Acoustic Drums Soundpack', 'Acoustic Drums', None),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation Analog Synthwave Soundpack (Bbm, 134bpm)', 'Analog Synthwave', 134),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation Belgian New Beat Soundpack (Fm, 113bpm)', 'Belgian New Beat', 113),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation FX Soundpack', 'FX Soundpack', None),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation Hyperpop Soundpack (Gm, 150bpm)', 'Hyperpop', 150),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation Legacy Soundpack (Cm, 125bpm)', 'Legacy', 125),
    (r'Novation Anniversary Soundpack 1\Novation Anniversary Soundpack 1st Drop\Novation Old School Hip-Hop Soundpack (Em, 107bpm)', 'Old School Hip-Hop', 107),
]


def categorize(subfolder_name):
    key = subfolder_name.strip().lower()
    return CATEGORY_MAP.get(key, 'extra')


def transcode_to_mp3_b64(src_path):
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-i', src_path,
             '-ar', '44100', '-ac', '2', '-codec:a', 'libmp3lame', '-b:a', '128k', tmp_path],
            capture_output=True, timeout=120
        )
        if proc.returncode != 0:
            return None, proc.stderr.decode('utf-8', 'ignore')
        with open(tmp_path, 'rb') as f:
            data = f.read()
        if len(data) == 0:
            return None, 'output vuoto'
        return base64.b64encode(data).decode('ascii'), None
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def clean_name(filename):
    return os.path.splitext(filename)[0].strip()


def build_pack(rel_path, title, bpm, log):
    pack_dir = os.path.join(ROOT, rel_path)
    buckets = {c: [] for c in CATEGORY_ORDER}
    for sub in sorted(os.listdir(pack_dir)):
        sub_path = os.path.join(pack_dir, sub)
        if not os.path.isdir(sub_path) or sub == '__MACOSX':
            continue
        cat = categorize(sub)
        files = []
        for dirpath, dirnames, filenames in os.walk(sub_path):
            for fn in sorted(filenames):
                if os.path.splitext(fn)[1].lower() in AUD_EXT:
                    files.append(os.path.join(dirpath, fn))
        buckets[cat].extend(sorted(files))

    # Ogni categoria inizia su una colonna nuova (mai due categorie diverse nella
    # stessa colonna): fix del 14/08/2026, prima una categoria con un numero di file
    # non multiplo di 8 lasciava che la successiva riempisse il resto della colonna
    # (es. 5 file "drums" + i primi 3 "perc" finivano tutti nella colonna 0).
    placements = []   # (colonna_globale, riga, percorso_file)
    col_offset = 0
    for cat in CATEGORY_ORDER:
        files = buckets[cat]
        if not files:
            continue
        for i, fpath in enumerate(files):
            placements.append((col_offset + i // 8, i % 8, fpath))
        col_offset += (len(files) + 7) // 8

    log.write(f'[{title}] {len(placements)} file da trascodificare\n')
    log.flush()

    clip_by_pos = {}
    failures = []
    for i, (gc, r, fpath) in enumerate(placements):
        b64, err = transcode_to_mp3_b64(fpath)
        if b64 is None:
            failures.append((fpath, err))
            log.write(f'  FALLITO: {fpath}\n    {err}\n')
            log.flush()
            continue
        clip_by_pos[(gc, r)] = {'name': clean_name(os.path.basename(fpath)), 'mime': 'audio/mpeg', 'data': b64}
        if (i + 1) % 10 == 0:
            log.write(f'  ...{i+1}/{len(placements)}\n')
            log.flush()

    genres_out = {}
    part = 1
    for part_start_col in range(0, col_offset, 8):
        clips_rc = []
        for local_c in range(8):
            gc = part_start_col + local_c
            if gc >= col_offset:
                break
            for r in range(8):
                clip = clip_by_pos.get((gc, r))
                if clip:
                    clips_rc.append({'r': r, 'c': local_c, 'name': clip['name'], 'mime': clip['mime'], 'data': clip['data']})
        if not clips_rc:
            part += 1
            continue
        gtitle = title if part == 1 else f'{title} ({part})'
        entry = {'clips': clips_rc}
        if bpm is not None:
            entry['bpm'] = bpm
        genres_out[gtitle] = entry
        part += 1

    return genres_out, failures


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    genres = {}
    all_failures = []
    with open(LOG_PATH, 'a', encoding='utf-8') as log:
        for rel_path, title, bpm in PACKS:
            if only and title not in only:
                continue
            g, failures = build_pack(rel_path, title, bpm, log)
            genres.update(g)
            all_failures.extend(failures)

    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding='utf-8') as f:
            existing = json.load(f)
    else:
        existing = {}
    existing.update(genres)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, separators=(',', ':'))

    print('Generi scritti in questa run:', list(genres.keys()))
    print('Fallimenti:', len(all_failures))
    for fp, err in all_failures:
        print('  -', fp, '->', err)
    print('Log completo:', LOG_PATH)


if __name__ == '__main__':
    main()
