#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Riordina i clip GIA' presenti in _sorgente/genres.json cosi' che ogni colonna
contenga una sola categoria (drums/perc/bass/melodic/fx/vocal/altro), senza
ritrascodificare nulla: i dati audio (base64) restano quelli gia' incorporati,
si spostano solo le posizioni (r,c) e, quando serve, un clip cambia "genere
titolo" (es. "Acid Techno" -> "Acid Techno (2)") se non ci sta piu' nella
griglia 8x8 originale.

Perche' serve: build_genres.py (prima del fix del 14/08/2026) impacchettava i
campioni di ogni categoria in sequenza senza mai "chiudere" la colonna al
cambio di categoria, quindi la coda di una categoria e la testa della
successiva finivano nella stessa colonna (es. "DRUMS 1..5" + "PERC 2..4" nella
colonna 0 di "Acid Techno"). genres.json era gia' stato generato con quel
bug prima che venisse trovato e corretto in build_genres.py - questo script
ripara i dati gia' esistenti senza dover rilanciare ffmpeg su ~1245 campioni.

USO: python repack_genres_by_category.py            # tutti i generi
     python repack_genres_by_category.py "Acid Techno"   # solo alcuni (per titolo BASE, senza "(N)")
"""
import json, re, sys, pathlib
from build_genres import category_of_name, CATEGORY_ORDER, KNOWN_KEYWORD_CATEGORIES

HERE = pathlib.Path(__file__).resolve().parent
SORGENTE = HERE.parent
GENRES_PATH = str(SORGENTE / 'genres.json')

PART_SUFFIX_RE = re.compile(r'^(.*) \((\d+)\)$')


def base_title(gtitle):
    m = PART_SUFFIX_RE.match(gtitle)
    return m.group(1) if m else gtitle


def part_number(gtitle):
    m = PART_SUFFIX_RE.match(gtitle)
    return int(m.group(2)) if m else 1


def repack_one(base, entries):
    """entries: lista di (gtitle, entry_dict) che condividono lo stesso titolo base,
    gia' esistenti in genres.json. Ritorna un nuovo dict {gtitle: entry} che le sostituisce."""
    entries = sorted(entries, key=lambda t: part_number(t[0]))
    # Ogni campo diverso da 'clips' (bpm, tracks, master, filter, revWet, revSize,
    # dlyWet, dlyFb, dlyTime, ecc.) viene preservato cosi' com'era, dalla prima parte
    # che lo contiene - fix del 14/08/2026, la prima versione di questo script copiava
    # solo 'clips'+'bpm' e scartava silenziosamente tutti gli altri (es. 'tracks',
    # che azzera l'EQ/invii per traccia al caricamento: senza, l'EQ della traccia
    # precedente restava "attaccata" al genere appena caricato).
    extra_fields = {}
    for _, e in entries:
        for k, v in e.items():
            if k != 'clips' and k not in extra_fields:
                extra_fields[k] = v

    # Ricostruisce l'ordine originale di lettura (parte, colonna, riga) - e' l'ordine
    # in cui build_genres.py aveva messo i file, quindi gia' raggruppato per categoria
    # di CARTELLA anche se il bug ne mischiava due nella stessa colonna finale.
    all_clips = []
    for gtitle, e in entries:
        for cl in sorted(e['clips'], key=lambda c: (c['c'], c['r'])):
            all_clips.append(cl)

    # Bucket per categoria (dal nome, parola chiave), preservando l'ordine di
    # prima apparizione e l'ordine relativo dei clip al loro interno. Solo le
    # categorie RICONOSCIUTE per parola chiave (drums/perc/bass/melodic/fx/
    # vocal) vengono allineate a una colonna propria: sono un numero fisso e
    # piccolo di bucket, quindi lo spreco di slot vuoti a fine colonna e'
    # trascurabile. I nomi non riconosciuti (fallback sul nome ripulito, es.
    # sigle come "1-1"/"2-3" in generi con naming non standard) NON vengono
    # allineati uno per uno: fossero trattati come le categorie note, ogni
    # nome unico occuperebbe un'intera colonna da solo (7 slot su 8 sprecati),
    # facendo esplodere il genere in molte varianti "(N)" quasi vuote - provato
    # e scartato: "Middle Eastern Electronic" passava da 1 a 5 varianti.
    # Restano quindi impacchettati in sequenza tutti insieme, come faceva il
    # codice originale, in un unico blocco finale dopo le categorie note.
    known_buckets = {}
    fallback_clips = []
    known_order = []
    for cl in all_clips:
        cat = category_of_name(cl['name'])
        if cat in KNOWN_KEYWORD_CATEGORIES:
            if cat not in known_buckets:
                known_buckets[cat] = []
                known_order.append(cat)
            known_buckets[cat].append(cl)
        else:
            fallback_clips.append(cl)

    ordered_known_cats = [c for c in CATEGORY_ORDER if c in known_buckets] or known_order

    clip_by_pos = {}   # (colonna_globale, riga) -> clip
    col_offset = 0
    for cat in ordered_known_cats:
        clips = known_buckets[cat]
        for i, cl in enumerate(clips):
            clip_by_pos[(col_offset + i // 8, i % 8)] = cl
        col_offset += (len(clips) + 7) // 8
    # Blocco finale non allineato: pacchettamento sequenziale, come il codice originale.
    for i, cl in enumerate(fallback_clips):
        clip_by_pos[(col_offset + i // 8, i % 8)] = cl
    col_offset += (len(fallback_clips) + 7) // 8

    out = {}
    part = 1
    for part_start_col in range(0, col_offset, 8):
        clips_rc = []
        for local_c in range(8):
            gc = part_start_col + local_c
            if gc >= col_offset:
                break
            for r in range(8):
                match = clip_by_pos.get((gc, r))
                if match:
                    clips_rc.append({'r': r, 'c': local_c, 'name': match['name'], 'mime': match['mime'], 'data': match['data']})
        if not clips_rc:
            part += 1
            continue
        gtitle = base if part == 1 else f'{base} ({part})'
        # extra_fields (bpm/tracks/master/filter/...) va su OGNI parte, non solo la prima:
        # l'app carica una parte alla volta come genere indipendente, quindi ciascuna deve
        # gia' portare le proprie impostazioni di mix di default.
        entry = {'clips': clips_rc, **extra_fields}
        out[gtitle] = entry
        part += 1

    return out


def main():
    only = set(sys.argv[1:]) if len(sys.argv) > 1 else None

    with open(GENRES_PATH, encoding='utf-8') as f:
        genres = json.load(f)

    groups = {}
    for gtitle, entry in genres.items():
        b = base_title(gtitle)
        groups.setdefault(b, []).append((gtitle, entry))

    new_genres = dict(genres)
    changed_bases = []
    for base, entries in groups.items():
        if only and base not in only:
            continue
        old_titles = [t for t, _ in entries]
        repacked = repack_one(base, entries)
        for t in old_titles:
            del new_genres[t]
        new_genres.update(repacked)
        if sorted(old_titles) != sorted(repacked.keys()):
            changed_bases.append((base, old_titles, list(repacked.keys())))

    with open(GENRES_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_genres, f, ensure_ascii=False, separators=(',', ':'))

    total_clips_before = sum(len(e['clips']) for e in genres.values())
    total_clips_after = sum(len(e['clips']) for e in new_genres.values())
    print(f'Generi riordinati: {len(groups) if not only else len(only)}')
    print(f'Clip totali prima: {total_clips_before}  dopo: {total_clips_after}  (deve combaciare)')
    if changed_bases:
        print('Generi che hanno cambiato numero di varianti "(N)":')
        for base, old, new in changed_bases:
            print(f'  {base}: {old} -> {new}')
    else:
        print('Nessun genere ha cambiato il proprio insieme di varianti "(N)".')


if __name__ == '__main__':
    main()
