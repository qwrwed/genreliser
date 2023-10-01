from __future__ import annotations

import logging
import re
from functools import cache, cached_property
from pathlib import Path
from pprint import pformat
from urllib.parse import quote, urlparse, urlunparse

import fandom
from bs4 import BeautifulSoup
from fandom.error import PageError
from utils_python.main import deduplicate
from utils_python.tqdm import print_tqdm
from utils_python.typing import copy_signature

from genreliser.base import BaseGenreliser, MusicFile
from genreliser.utils import ensure_caps, get_from_url

print_std = print
print = print_tqdm


def pprint(*x):
    print(pformat(x))


LOGGER = logging.getLogger("genreliser")

# PATTERN_FIELDS_FROM_TITLE = r"^(?:\[(?P<genre>.*?)\] )?(?:(?:[-:] )?(?P<artist>.*?) - )?(?P<title>.*?)(?: \[(?P<extra>.*)\])?$"
PATTERN_FIELDS_FROM_TITLE = (
    r"^(?:\[(?P<genre>.*?)\] )?(?:(?:[-:] )?(?P<artist>.*?) - )?(?P<title>.*?)$"
)
PATTERN_FEAT_FROM_TITLE = r"( \(?feat\.? [\w\s]+)\)?"
PATTERN_FEAT_FROM_ARTIST = r"( feat\.? [\w\s]+)"
# TODO: merge feat patterns?


@cache
def get_monstercat_wiki_html(url: str):
    url_parsed = urlparse(url)
    path = quote(url_parsed.path)  # workaround for special characters in url
    url = urlunparse(url_parsed._replace(path=path))
    html = get_from_url(url, "monstercat_wiki")
    return html


def get_url_from_monstercat_wiki(
    possible_titles: list[str], possible_artists: list[str]
):
    fandom.set_wiki("Monstercat")
    # title = title.title()
    # artist = artist.title()
    title_page = None
    _title_artist_page = None
    for title in possible_titles[:]:
        if "feat" in title:
            possible_titles.append(re.sub(PATTERN_FEAT_FROM_TITLE, "", title))
    valid_title_pages = {}  # type: dict[str, fandom.FandomPage]
    for title in possible_titles:
        try:
            title_page = fandom.page(title)
            valid_title_pages[title] = title_page
        except PageError as _exc:
            new_title = ensure_caps(title)
            if new_title == title:
                continue
            LOGGER.info(f"changing capitalisation: {title!r} -> {new_title!r}")
            title = new_title
            try:
                title_page = fandom.page(title)
                LOGGER.info(f"got page: {title=}")
                valid_title_pages[title] = title_page
            except PageError as _exc2:
                LOGGER.info(f"page not found: {title=}")
                continue
    LOGGER.info(f"{valid_title_pages.keys()=}")
    if not valid_title_pages:
        raise ValueError(f"Could not find page for {possible_titles=}")

    disam: set[str] = set()
    non_disam: set[str] = set()
    for title, page in valid_title_pages.items():
        if "disambiguation" in get_monstercat_wiki_html(page.url):
            disam.add(title)
        else:
            non_disam.add(title)
    non_disam_count = len({t.lower() for t in non_disam})
    if non_disam_count > 1:
        LOGGER.warning(f"multiple non-disambiguating pages! {non_disam=}")
        title = max(non_disam, key=len)
        page = fandom.page(title)
        return page.url
    if non_disam_count == 1:
        title = non_disam.pop()
        page = fandom.page(title)
        return page.url

    disam_count = len({t.lower() for t in disam})
    if disam_count > 1:
        LOGGER.warning(f"multiple disambiguating pages! {disam=}")
        breakpoint()
        ...
    elif disam_count == 0:
        raise ValueError(f"Could not find page for {possible_titles=}")

    title_without_artist = disam.pop()
    for artist in possible_artists:
        artist = re.sub(PATTERN_FEAT_FROM_ARTIST, "", artist)
        for artist_orig_name, artist_rename in ARTIST_RENAMES.items():
            if artist_orig_name in artist:
                artist = artist.replace(artist_orig_name, artist_rename)
        new_title = f"{title_without_artist} ({artist})"
        LOGGER.info(f"disambiguating {title!r} -> {new_title!r}")
        title = new_title
        try:
            page = fandom.page(title)
            return page.url
        except PageError as _exc:
            continue
    raise ValueError(
        f"Could not disambiguate {title_without_artist=} for {possible_artists}"
    )


@cache
def get_genres_from_monstercat_wiki_html(html: str):
    main_soup = BeautifulSoup(html, "html.parser")
    genres_found = []
    for genre_section_soup in main_soup.find_all(
        "div", {"data-source": re.compile(".*[gG]enre.*")}
    ):
        for genre_soup in genre_section_soup.find_all("a"):
            for genre_entry in genre_soup.contents:
                genres = [genre.strip() for genre in genre_entry.split("|")]
                genres_found.extend(genres)
    return deduplicate(genres_found)


@cache
def get_titles_from_monstercat_wiki_html(html: str):
    main_soup = BeautifulSoup(html, "html.parser")
    results = []
    for sub_soup in main_soup.find_all(attrs={"data-source": "Name"}):
        for content in sub_soup.contents:
            if content not in results:
                if isinstance(content, str):
                    results.append(content)
    if len(results) > 1:
        LOGGER.warning("multiple titles found on wiki: %s", results)
        results = ["".join(results)]
    return results


Title = str
Artist = str
Url = str


class MonstercatGenreliser(BaseGenreliser):
    title_pattern = PATTERN_FIELDS_FROM_TITLE

    @copy_signature(BaseGenreliser.__init__)
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.music_file_type = MonstercatMusicFile
        self.wiki_resolutions = {}  # type: dict[tuple[Title, Artist], Url]

    def get_url_from_monstercat_wiki(
        self, possible_titles: list[str], possible_artists: list[str]
    ):
        for possible_title in possible_titles:
            for possible_artist in possible_artists:
                if seen_url := self.wiki_resolutions.get(
                    (possible_title, possible_artist)
                ):
                    return seen_url

        url = get_url_from_monstercat_wiki(possible_titles, possible_artists)
        for possible_title in possible_titles:
            for possible_artist in possible_artists:
                self.wiki_resolutions[(possible_title, possible_artist)] = url
        return url

    def get_fields_from_monstercat_wiki(self, possible_titles, possible_artists):
        url = self.get_url_from_monstercat_wiki(possible_titles, possible_artists)
        html = get_monstercat_wiki_html(url)
        return {
            "titles": get_titles_from_monstercat_wiki_html(html),
            "genres": get_genres_from_monstercat_wiki_html(html),
        }


ARTIST_RENAMES = {"Splitbreed": "SPLITBREED"}


GENRE_EXCLUSIONS = {"dance", "monstercat", "monsterccat"}


class MonstercatMusicFile(MusicFile[MonstercatGenreliser]):
    def __init__(self, filepath: Path, genreliser: MonstercatGenreliser) -> None:
        super().__init__(filepath, genreliser)
        self.sources.append("wiki")
        self.genre_exclusions.update(GENRE_EXCLUSIONS)

    @cached_property
    def fields_from_wiki(self):
        fields_combined = self.fields_combined
        return self.genreliser.get_fields_from_monstercat_wiki(
            [fields_combined["titles"][0]], [fields_combined["artists"][0]]
        )
