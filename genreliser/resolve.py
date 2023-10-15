from __future__ import annotations

import re
from functools import cache

from utils_python import deduplicate, ensure_caps

GENRE_SYNONYMS = {
    "Bass House": ["basshouse"],
    "Drum & Bass": ["dnb", "drumandbass", "drum and bass"],
    "Dancefloor Drum & Bass": ["dancefloor drum and bass"],
    "Glitch Hop / 110BPM": ["glitch hop or 110bpm", "glitch hop / 110 bpm"],
    "House": ["house music"],
    "EDM": ["edm"],
    "Electro House": ["electrohouse"],
    "Electro Pop": ["electropop"],
    "Melodic Bass": ["melodicbass"],
}

genre_synonyms_lookup = {}
for actual, synonyms in GENRE_SYNONYMS.items():
    genre_synonyms_lookup[actual.lower()] = actual
    for synonym in synonyms:
        genre_synonyms_lookup[synonym.lower()] = actual


# @cache
def resolve_genre(genre_input: str, genre_exclusions=None):
    if genre_exclusions is None:
        genre_exclusions = set()
    if genre_input is None or genre_input.lower() in genre_exclusions:
        return None
    genre = genre_synonyms_lookup.get(genre_input.lower(), ensure_caps(genre_input))
    genre = re.sub("([a-z])([A-Z])", "\\1 \\2", genre)
    return genre


def resolve_genre_list(genre_list: list[str], genre_exclusions=None):
    return deduplicate(
        [
            genre_resolved
            for genre in genre_list
            if (genre_resolved := resolve_genre(genre, genre_exclusions)) is not None
        ]
    )
