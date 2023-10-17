from __future__ import annotations

import logging
import re
import time
from functools import cached_property
from pathlib import Path
from pprint import pformat
from typing import Generic, Literal, Optional, TypeVar

from mutagen.easymp4 import EasyMP4
from utils_python import (
    logPrefixFilter,
    make_get_request_to_url,
    print_tqdm,
    run_on_path,
    run_on_paths,
)

from genreliser.acoustid_ import AcoustIDNotFoundError, get_acoustid
from genreliser.resolve import resolve_genre_list
from genreliser.utils import clean_string, combine_listdicts

LOGGER = logging.getLogger("genreliser")

print_std = print
print = print_tqdm


def pprint(x):
    print(pformat(x))


PATTERN_GENRE_FROM_DESCRIPTION = r"^.*?Genre:\s*(?P<genres>.+?)\s*$"
PATTERN_GENRES_FROM_LINE = r"#(\w+)"
PATTERN_FEAT_FROM_ARTIST = r"^(.+?)(?: f(?:ea)?t\.? (.+))?$"

SUFFIX_TAG_FUNCTIONS = {".m4a": EasyMP4}


class DataNotFoundError(Exception):
    ...


def get_tags(filepath: Path):
    if (suffix_tag_function := SUFFIX_TAG_FUNCTIONS.get(filepath.suffix)) is None:
        raise NotImplementedError(
            f"{filepath.name}: suffix {filepath.suffix} not supported - must be in {SUFFIX_TAG_FUNCTIONS.keys}"
        )
    return suffix_tag_function(filepath)


class BaseGenreliser:
    title_pattern: Optional[str] = None
    description_pattern_genre: str = PATTERN_GENRE_FROM_DESCRIPTION

    def __init__(
        self,
        previous_failed_files=None,
        previous_json_data=None,
        retry: Literal["failed", "passed", "all"] | None = None,
    ) -> None:
        self.music_file_type = MusicFile
        self.genres_to_files = {}
        self.files_without_genres = set()

        self.artists_to_files = {}
        self.files_without_artists = set()

        self.files_to_titles = {}
        self.files_without_titles = set()

        self.failed_files: list[Path] = previous_failed_files or []
        self.json_data: dict[Path, dict] = previous_json_data or {}

        self.retry = retry

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

    def genrelise_file(
        self,
        filepath: Path,
    ):
        with logPrefixFilter(LOGGER, msg_prefix=f"['{filepath.name}']: "):
            LOGGER.info("starting...")

            if filepath in self.failed_files:
                if self.retry in {"failed", "all"}:
                    self.failed_files.pop(self.failed_files.index(filepath))
                else:
                    LOGGER.info(
                        "skipping; already in self.failed_files and self.retry=%s",
                        self.retry,
                    )
                    return

            if filepath in self.json_data and self.retry not in {"passed", "all"}:
                LOGGER.info(
                    "skipping; already in self.json_data and self.retry=%s",
                    self.retry,
                )
                return

            filepath_str = str(filepath)

            music_file = self.music_file_type(filepath, genreliser=self)

            try:
                fields = music_file.get_fields_from_sources()
                if not fields or not any(fields.values()):
                    LOGGER.error(f"No data found")
                    self.failed_files.append(str(filepath))
                    return
            except Exception as exc:
                LOGGER.exception(exc, exc_info=not isinstance(exc, DataNotFoundError))
                self.failed_files.append(str(filepath))
                return
            fields_combined = music_file.fields_combined
            LOGGER.info("got combined fields: %s", fields_combined)
            self.json_data[filepath_str] = fields_combined

            LOGGER.info("...finished")

    def genrelise_path(
        self,
        path: Path,
    ):
        return run_on_path(
            path,
            file_callback=self.genrelise_file,
            # dir_callback=self.run_on_dir,
        )

    def genrelise_paths(
        self,
        paths: list[Path],
    ):
        return run_on_paths(
            paths,
            file_callback=self.genrelise_file,
            # dir_callback=self.run_on_dir,
        )

    def run_on_file(self, file: Path):
        if not isinstance(file, Path):
            file = Path(file)
        time.sleep(0.1)
        return f"f {file.stem=}"

    def run_on_dir(self, file: Path):
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
    def __init__(
        self,
        filepath: Path,
        genreliser: GenreliserType,
        logger: logging.Logger = LOGGER,
    ) -> None:
        self.filepath = filepath
        self.logger = logger
        self.genreliser = genreliser
        self.tags = get_tags(self.filepath)
        self.tag_title: str = self.tags["title"][0]
        self.tag_description: str = self.tags["description"][0]
        self.acoustid_fields = {}
        self.sources = [
            # "acousticbrainz",
            # "musicbrainz",
            "title",
            # "description",
            # "tags",
        ]
        self.genre_exclusions = set()

    def __repr__(self) -> str:
        return f"<{self.__module__}.{self.__class__.__name__} '{self.filepath}'>"

    # @cached_property
    @property
    def acoustid(self):
        try:
            self.acoustid_fields = get_acoustid(self.filepath)
            return self.acoustid_fields["acoustid"]
        except AcoustIDNotFoundError as exc:
            LOGGER.warning(exc, exc_info=1)
            return None

    # @cached_property
    @property
    def fields_from_acousticbrainz(self):
        if self.acoustid is None:
            return {}
        url = f"https://acousticbrainz.org/api/v1/{self.acoustid}/low-level"
        res_json = make_get_request_to_url(url, src_key="acousticbrainz")
        if res_json is None:
            return {}
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
        LOGGER.info("got fields from acousticbrainz: %s", res_tags_filtered)
        return res_tags_filtered

    # @cached_property
    @property
    def fields_from_musicbrainz(self):
        if self.acoustid is None:
            return {}
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
        res_json = make_get_request_to_url(url, src_key="musicbrainz")
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
        LOGGER.info("got fields from musicbrainz: %s", res_tags_processed)
        return res_tags_processed

    # @cached_property causes memory leak
    @property
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
        res = {
            "genres": genre_list,
        }
        LOGGER.info("got fields from description: %s", res)
        return res

    # @cached_property causes memory_leak
    @property
    def fields_from_tags(self):
        fields = {}
        for field_name in ["genre", "artist", "title"]:
            field_name_plural = f"{field_name}s"
            if field_name in self.tags:
                fields[field_name_plural] = self.tags[field_name]
            elif field_name_plural in self.tags:
                fields[field_name_plural] = self.tags[field_name_plural]
        LOGGER.info("got fields from tags: %s", fields)
        return fields

    @cached_property
    def fields_from_title(self):
        fields_from_title = {}
        title_pattern = self.genreliser.title_pattern
        if title_pattern is None:
            return fields_from_title
        extras = []

        tag_title_clean = clean_string(self.tag_title)

        def capture_and_kill(match: re.Match):
            # https://stackoverflow.com/a/36196325
            extras.extend([m for m in match.groups() if m is not None])
            return ""

        tag_title_no_extras = re.sub(
            r"\s+\[([^\]]+)]|\s+\(([^)]+)\)", capture_and_kill, tag_title_clean
        )
        while "  " in tag_title_no_extras:
            tag_title_no_extras = tag_title_no_extras.replace("  ", " ")
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

        if artist_fields := fields_from_title.get("artists"):
            artist_fields[0], feat = re.search(
                PATTERN_FEAT_FROM_ARTIST, artist_fields[0]
            ).groups()
            if feat:
                extras_categorised.setdefault("feat", []).append(feat)

        title = fields_from_title["titles"][0]
        title_extra_sep = " - "
        if title_extra_sep in title:
            fields_from_title["titles"].extend(title.split(title_extra_sep))

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
        LOGGER.info("got fields from title: %s", fields_from_title)
        return fields_from_title

    def get_fields_from_sources(self):
        """generates fields"""
        fields = {
            source: fields
            for source in self.sources
            if (fields := getattr(self, f"fields_from_{source}")) is not None
        }
        return fields

    @property
    def fields_from_sources(self):
        """retrieves already-generated fields"""
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
        if genres_resolved:
            fields_combined["genres"] = genres_resolved
        fields_combined["sources"] = self.sources
        return fields_combined
