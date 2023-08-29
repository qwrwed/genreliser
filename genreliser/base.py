import logging
import time
from functools import cached_property
from os import PathLike
from pathlib import Path
from pprint import pprint

from acoustid_ import get_acoustid
from env import ACOUSTID_API_KEY
from mutagen.easymp4 import EasyMP4
from utils import get_from_url, run_on_path
from utils_python.tqdm import print_tqdm

LOGGER = logging.getLogger("genreliser")

print_std = print
print = print_tqdm


class MusicFile:
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.tags = EasyMP4(self.filepath)
        self.tag_title = self.tags["title"]
        self.tag_description = self.tags["description"]

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
                "artist",
                "date",
                "genre",
                "title",
                "label",
                "file_name",
            }:
                continue
            if not isinstance(v, list):
                v = [v]
            res_tags_filtered[f"{k}s"] = v
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
        title_aliases = []
        for alias in res_json.get("aliases", []):
            for field in ["name"]:  # TODO: add "sort-name"?
                if alias.get(field) is not None and field not in title_aliases:
                    title_aliases.append(alias[field])
        artists = []
        artist_aliases = {}
        for artist_credit in res_json["artist-credit"]:
            artist_name = artist_credit["name"]
            artists.append(artist_name)
            artist_aliases[artist_name] = []
            for alias in artist_credit["artist"]["aliases"]:
                artist_aliases[artist_name].append(alias["name"])
        res_tags_processed = {
            # "mbid": res_json["id"],
            # "isrcs": res_json["isrcs"],
            "artists": [
                artist_credit["name"] for artist_credit in res_json["artist-credit"]
            ],
            "artist-aliases": artist_aliases,
            "titles": [res_json["title"]],
            "title-aliases": title_aliases,
            "genres": [genre["name"] for genre in res_json["genres"]],
            "dates": [res_json.get("first-release-date")],
        }
        res_tags_processed = {
            k: v for k, v in res_tags_processed.items() if v and set(v) != {None}
        }
        return res_tags_processed


class BaseGenreliser:
    def __init__(self) -> None:
        self.genres_to_files = {}
        self.files_without_genres = set()

        self.artists_to_files = {}
        self.files_without_artists = set()

        self.files_to_titles = {}
        self.files_without_titles = set()

        self.retrieved_fields = {}

        self.file_cache: dict[Path, MusicFile] = {}

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

    def get_fields_from_title(self, path: Path):
        self.retrieved_fields["title"] = {}

    def get_fields_from_description(self, description: str):
        self.retrieved_fields["description"] = {}

    def get_fields_from_acousticbrainz(self, acoustid: str):
        self.retrieved_fields["acousticbrainz"] = {}

    def get_fields_from_musicbrainz(self, acoustid: str):
        self.retrieved_fields["musicbrainz"] = {}

    def get_fields(self, filepath: Path):
        self.get_fields_from_title(filepath)
        self.get_fields_from_description(filepath)
        self.get_fields_from_acousticbrainz(filepath)
        self.get_fields_from_musicbrainz(filepath)

    def genrelise_file(self, filepath: Path):
        LOGGER.info(filepath)
        if filepath.suffix != ".m4a":
            # not implemented
            return
        music_file = MusicFile(filepath)
        print(music_file.fields_from_acousticbrainz)
        print(music_file.fields_from_musicbrainz)
        # pprint(dict(tags))
        # self.get_fields()
        exit()

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
