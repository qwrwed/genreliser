from __future__ import annotations

import logging
import re
import time
from functools import cached_property
from os import PathLike
from pathlib import Path
from pprint import pformat
from typing import Generic, Optional, TypeVar

from mutagen.easymp4 import EasyMP4
from utils_python.tqdm import print_tqdm

from genreliser.acoustid_ import get_acoustid
from genreliser.resolve import resolve_genre_list
from genreliser.utils import combine_listdicts, get_from_url, run_on_path

LOGGER = logging.getLogger("genreliser")

print_std = print
print = print_tqdm


def pprint(x):
    print(pformat(x))


PATTERN_GENRE_FROM_DESCRIPTION = r"^.*?Genre:\s*(?P<genres>.+?)\s*$"
PATTERN_GENRES_FROM_LINE = r"#(\w+)"


class BaseGenreliser:
    title_pattern: Optional[str] = None
    description_pattern_genre: str = PATTERN_GENRE_FROM_DESCRIPTION

    def __init__(self) -> None:
        self.music_file_type = MusicFile
        self.genres_to_files = {}
        self.files_without_genres = set()

        self.artists_to_files = {}
        self.files_without_artists = set()

        self.files_to_titles = {}
        self.files_without_titles = set()

        # self.file_cache: dict[Path, MusicFile] = {}

    @property
    def results(self):
        return {
            "genres_to_files": self.genres_to_files,
            "files_without_genres": list(self.files_without_genres),
            "artists_to_files": self.artists_to_files,
            "files_without_artists": list(self.files_without_artists),
            "files_to_titles": {str(k): v for k, v in self.files_to_titles.items()},
            "files_without_titles": list(self.files_without_titles),
        }

    def genrelise_file(self, filepath: Path):
        if filepath.suffix != ".m4a":
            # not implemented
            return
        LOGGER.info(filepath)
        music_file = self.music_file_type(filepath, genreliser=self)
        music_file.get_fields_from_sources()
        # fields_from_sources = music_file.get_fields_from_sources()
        pprint(music_file.fields_from_sources)
        pprint(music_file.fields_combined)
        # breakpoint()
        # if fields_from_sources:
        #     print(filepath)
        #     print(pformat(fields_from_sources))
        #     print()
        # exit()

    def genrelise_path(self, path: PathLike):
        return run_on_path(
            path,
            file_callback=self.genrelise_file,
            # dir_callback=self.run_on_dir,
        )

    def run_on_file(self, file: PathLike):
        if not isinstance(file, Path):
            file = Path(file)
        time.sleep(0.1)
        return f"f {file.stem=}"

    def run_on_dir(self, file: PathLike):
        if not isinstance(file, Path):
            file = Path(file)
        return f"d {file.stem=}"


def get_aliases_musicbrainz(d: dict, fields: list[str] | None = None):
    if fields is None:
        fields = [
            "name",
            # "sort-name",
        ]
    aliases = []
    for alias_data in d["aliases"]:
        for field in fields:
            if (alias := alias_data.get(field)) is not None and alias not in aliases:
                aliases.append(alias_data[field])
    return aliases


GenreliserType = TypeVar("GenreliserType", bound=BaseGenreliser)


class MusicFile(Generic[GenreliserType]):
    def __init__(self, filepath: Path, genreliser: GenreliserType) -> None:
        self.filepath = filepath
        self.genreliser = genreliser
        self.tags = EasyMP4(self.filepath)
        self.tag_title: str = self.tags["title"][0]
        self.tag_description: str = self.tags["description"][0]
        self.acoustid_fields = {}
        self.sources = [
            # "acousticbrainz",
            "musicbrainz",
            "title",
            "description",
            # "tags",
        ]
        self.genre_exclusions = set()

    @cached_property
    def acoustid(self):
        self.acoustid_fields = get_acoustid(self.filepath)
        return self.acoustid_fields["acoustid"]

    @cached_property
    def fields_from_acousticbrainz(self):
        url = f"https://acousticbrainz.org/api/v1/{self.acoustid}/low-level"
        res_json = get_from_url(url, src_key="acousticbrainz")
        if res_json is None:
            return {}, {}
        res_metadata = res_json["metadata"]
        res_tags_all = res_metadata["tags"]
        res_tags_filtered = {}
        for k, v in res_tags_all.items():
            if k not in {
                "genre",
                "album",
                "albumartist",
                # "artist", # single string incl. "feat"
                "artists",
                "date",
                "title",
                "label",
                "file_name",
            }:
                continue
            if not isinstance(v, list):
                v = [v]
            if not k.endswith("s"):
                k = f"{k}s"
            res_tags_filtered[k] = v
        return res_tags_filtered

    @cached_property
    def fields_from_musicbrainz(self):
        includes = [
            "artists",
            "releases",
            "discids",
            "media",
            "genres",
            "artist-credits",
            "isrcs",
            "work-level-rels",
            "annotation",
            "aliases",
            "tags",
            "ratings",
            "area-rels",
            "artist-rels",
            "label-rels",
            "place-rels",
            "event-rels",
            "recording-rels",
            "release-rels",
            "release-group-rels",
            "series-rels",
            "url-rels",
            "work-rels",
            "instrument-rels",
        ]
        # includes = ["genres", "artists", "isrcs"]
        url = f"https://musicbrainz.org/ws/2/recording/{self.acoustid}?inc={'+'.join(includes)}&fmt=json"
        res_json = get_from_url(url, src_key="musicbrainz")
        title_aliases = get_aliases_musicbrainz(res_json)
        res_tags_processed = {
            # "mbid": res_json["id"],
            # "isrcs": res_json["isrcs"],
            "artists": [
                artist_credit["name"] for artist_credit in res_json["artist-credit"]
            ],
            "artist-aliases": {
                artist_credit["name"]: get_aliases_musicbrainz(artist_credit["artist"])
                for artist_credit in res_json["artist-credit"]
            },
            "titles": [res_json["title"]],
            "title-aliases": title_aliases,
            "genres": [genre["name"] for genre in res_json["genres"]],
            "dates": [res_json.get("first-release-date")],
        }
        res_tags_processed = {
            k: v for k, v in res_tags_processed.items() if v and set(v) != {None}
        }
        return res_tags_processed

    @cached_property
    def fields_from_description(self):
        match = re.search(
            self.genreliser.description_pattern_genre,
            self.tag_description,
            flags=re.MULTILINE,
        )
        if "genre" in self.tag_description.lower():
            # LOGGER.info(self.tag_description)
            # breakpoint()
            pass
        if not match:
            return {}
        genre_line = match.group(1)
        if "#" in genre_line:
            genre_list = re.findall(PATTERN_GENRES_FROM_LINE, genre_line)
        else:
            genre_list = [genre_line]
        return {
            "genres": genre_list,
        }

    @cached_property
    def fields_from_tags(self):
        fields = {}
        for field_name in ["genre", "artist", "title"]:
            field_name_plural = f"{field_name}s"
            if field_name in self.tags:
                fields[field_name_plural] = self.tags[field_name]
            elif field_name_plural in self.tags:
                fields[field_name_plural] = self.tags[field_name_plural]
        return fields

    @cached_property
    def fields_from_title(self):
        fields_from_title = {}
        title_pattern = self.genreliser.title_pattern
        if title_pattern is None:
            return fields_from_title
        extras = []

        def capture_and_kill(match: re.Match):
            # https://stackoverflow.com/a/36196325
            extras.extend([m for m in match.groups() if m is not None])
            return ""

        tag_title_no_extras = re.sub(
            r"\s+\[([^\]]+)]|\s+\(([^)]+)\)", capture_and_kill, self.tag_title
        )
        match = re.search(title_pattern, tag_title_no_extras)
        for field_name in ["genre", "artist", "title"]:
            try:
                field_match = match.group(field_name)
            except IndexError:
                if field_name != "extra":
                    LOGGER.warning(
                        f"pattern {title_pattern!r} has no field {field_name}"
                    )
                continue
            if field_match := match.group(field_name):
                fields_from_title[f"{field_name}s"] = [field_match]
        extras_categorised = {}
        for extra in extras:
            if "release" in extra.lower():
                extras_categorised.setdefault("release", []).append(extra)
            elif "feat." in extra.lower():
                extras_categorised.setdefault("feat", []).append(extra)
            elif "mix" in extra.lower():
                extras_categorised.setdefault("remix", []).append(extra)
            else:
                extras_categorised.setdefault(None, []).append(extra)
        fields_from_title["extras"] = extras_categorised
        return fields_from_title

    def get_fields_from_sources(self):
        fields = {
            source: fields
            for source in self.sources
            if (fields := getattr(self, f"fields_from_{source}")) is not None
        }
        return fields

    @property
    def fields_from_sources(self):
        return {
            key: value
            for key in [f"fields_from_{source}" for source in self.sources]
            if (value := self.__dict__.get(key)) is not None
        }

    @property
    def fields_combined(self):
        fields_combined = combine_listdicts(self.fields_from_sources.values())
        genres_resolved = resolve_genre_list(
            fields_combined.get("genres", []), self.genre_exclusions
        )
        fields_combined["genres"] = genres_resolved
        return fields_combined
