import re
from functools import cache

from base import BaseGenreliser

# from unsorted import TagNotFoundError
from utils import ensure_caps


class MonstercatGenreliser(BaseGenreliser):
    def get_fields_from_wiki(self):
        self.retrieved_fields["wiki"] = {}


ARTIST_RENAMES = {"Splitbreed": "SPLITBREED"}
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

GENRE_EXCLUSIONS = {"dance", "monstercat", "monsterccat"}

genre_synonyms_lookup = {}
for actual, synonyms in GENRE_SYNONYMS.items():
    genre_synonyms_lookup[actual.lower()] = actual
    for synonym in synonyms:
        genre_synonyms_lookup[synonym.lower()] = actual


@cache
def resolve_genre(genre_input: str):
    if genre_input is None or genre_input.lower() in GENRE_EXCLUSIONS:
        return None
    genre = genre_synonyms_lookup.get(genre_input.lower(), ensure_caps(genre_input))
    genre = re.sub("([a-z])([A-Z])", "\\1 \\2", genre)
    return genre


def resolve_genre_list(genre_list: list[str]):
    return [
        resolve_genre(genre) for genre in genre_list if resolve_genre(genre) is not None
    ]


@cache
def get_fields_from_title(title: str):
    # pattern = "\s*(?:\[.*?\])?"
    # pattern = "^(?:\[(.*?)\] (?:[-:] )?)?(.*?) - (.*?)(?: \[.*\])?$"
    # pattern = "^(?:\[(.*?)\] (?:(?:[-:] )?)?(.*?) - )?(.*?)(?: \[(.*)\])?$"
    pattern = "(?:\[(.*?)\] )?(?:(?:(?:[-:] )?)?(.*?) - )?(.*)(?: \[(.*)\])?"
    match = re.search(pattern, title)
    fields = {}
    if match:
        if match.group(1):
            fields["genres"] = [resolve_genre(match.group(1))]
        if match.group(2):
            fields["artists"] = [match.group(2)]
        if match.group(3):
            fields["titles"] = [match.group(3)]
        if match.group(4):
            fields["extras"] = [match.group(4)]
    else:
        raise TagNotFoundError(f"didn't get any fields from {title=!r}")
    return fields


@cache
def get_fields_from_description(description: str):
    # tqdm.write(description)
    match = re.search("^.*?Genre:\s*(.+?)\s*$", description, flags=re.MULTILINE)
    if not match:
        return {}
    genre_line = match.group(1)
    if "#" in genre_line:
        genre_list = re.findall("#(\w+)", genre_line)
    else:
        genre_list = [genre_line]
    genre_list_resolved = resolve_genre_list(genre_list)
    # genre = resolve_genre()
    # title = None
    return {
        "genres": genre_list_resolved,
        # "title": title,
    }
