from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from functools import cache, cached_property
from pathlib import Path
from pprint import pformat
from urllib.parse import quote

import fandom
from fandom.error import PageError
from utils_python import copy_signature, deduplicate, flatten, print_tqdm

from genreliser.base import LOGGER, BaseGenreliser, MusicFile
from genreliser.fandom_ import EnhancedFandomPage
from genreliser.utils import ensure_one

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

WIKI_SEARCH_MATCH_RESULTS = 20


class WikiPageNotFoundError(Exception):
    ...


class MultipleResultsError(Exception):
    ...


def log_monstercat_search_string(query):
    LOGGER.info(
        "search query = 'https://monstercat.fandom.com/wiki/Special:Search?query=%s'",
        quote(query),
    )


SIMILARITY_THRESHOLD = 0.9
CHAR_DIFFERENCE_THRESHOLD = 3

SearchResult = tuple[str, int]


def get_wiki_page(page: str | int | fandom.FandomPage):
    if isinstance(page, (str, int)):
        return EnhancedFandomPage(page)
    elif isinstance(page, EnhancedFandomPage):
        return page
    raise TypeError(f"Cannot get FandomPage from {page}")


class MonstercatWikiPageInfo(dict):
    ignored_equality_keys = {"query", "query_similarity"}

    def __init__(
        self, page: str | int | fandom.FandomPage, search_query: str | None = None
    ) -> None:
        page = get_wiki_page(page)
        __normalize = lambda s: s.replace('"', "").lower()
        if search_query is None:
            query_similarity = None
        else:
            query_similarity = SequenceMatcher(
                None, __normalize(search_query), __normalize(page.title)
            ).ratio()

        if "disambiguation" in page.html:
            page_type = "disambiguation"
        else:
            if page.soup.find_all(
                "li", {"class": "category normal", "data-name": "Songs"}
            ):
                page_type = "song"
            else:
                page_type = "unknown"

        is_exact_match = query_similarity in {None, 1.0}

        super().__init__(
            {
                "page": page,
                "query": search_query,
                "query_similarity": query_similarity,
                "type": page_type,
                "is_exact_match": is_exact_match,
            }
        )

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, self.__class__):
            self_without_ignored_keys = {
                k: v for k, v in self.items() if k not in self.ignored_equality_keys
            }
            value_without_ignored_keys = {
                k: v
                for k, v in __value.items()
                if k not in __value.ignored_equality_keys
            }
            return self_without_ignored_keys == value_without_ignored_keys
        return super().__eq__(__value)

    def __lt__(self, __value: object) -> bool:
        sort_key = "query_similarity"
        if isinstance(__value, self.__class__):
            if __value[sort_key] is None:
                return True
            elif self[sort_key] is None:
                return False
            else:
                return self[sort_key] < __value[sort_key]

    def __hash__(self):
        return hash(self["id"])


def get_all_pages_from_title(
    title: str, disambiguators: list[str]
) -> list[MonstercatWikiPageInfo]:
    fandom.set_wiki("Monstercat")

    titles_to_search = [
        f"{title} ({disambiguator})" for disambiguator in disambiguators
    ]

    try:
        page = EnhancedFandomPage(title)
        page_info = MonstercatWikiPageInfo(page)
        if page_info["type"] == "song":
            return [page_info]
        elif page_info["type"] == "disambiguation":
            LOGGER.info("Found disambiguation page; will search with disambiguators")
    except PageError:
        LOGGER.info(
            "Did not find page; will search for title, then search with disambiguators"
        )
        titles_to_search.insert(0, f'"{title}"')
        titles_to_search.insert(0, f"{title}")

    page_infos: list[MonstercatWikiPageInfo] = []

    for title_searched in titles_to_search:
        log_monstercat_search_string(title_searched)
        search_results: list[SearchResult] = fandom.search(title_searched)

        for _title, page_id in search_results:
            page_info = MonstercatWikiPageInfo(page_id, search_query=title_searched)
            if page_info["type"] == "song":
                if page_info["is_exact_match"]:
                    return [page_info]
                page_infos.append(page_info)

    return page_infos


def get_page_from_titles(
    titles: list[str], disambiguators: list[str]
) -> EnhancedFandomPage:
    """
    Returns the closest page match given a list of possible titles and disambiguators
    """
    LOGGER.info("Finding page for titles=%s, disambiguators=%s", titles, disambiguators)
    page_infos = sorted(
        flatten([get_all_pages_from_title(title, disambiguators) for title in titles]),
        reverse=True,
    )
    if len(page_infos) == 0:
        raise WikiPageNotFoundError(f"No page found")

    exact_matches = [
        page_info for page_info in page_infos if page_info["is_exact_match"]
    ]
    if len(exact_matches) > 1:
        raise NotImplementedError(f"Multiple exact matches found: {exact_matches}")

    page_info = page_infos[0]
    match_type = "exact" if page_info["is_exact_match"] else "best"
    LOGGER.info("Found %s match: %s", match_type, page_info)

    return page_info["page"]


def get_page_from_known_fields(
    known_fields: dict[str, list[str] | dict[str, list[str]]]
) -> EnhancedFandomPage:
    fandom.set_wiki("Monstercat")
    titles = known_fields["titles"]
    try:
        artist = ensure_one(known_fields["artists"])
    except NotImplementedError as exc:
        breakpoint()
        pass
    disambiguators = []
    include_artist = True
    for extras_key, extras_values in known_fields["extras"].items():
        if extras_key in {"remix"}:  # {"remix", None}?
            include_artist = False
        disambiguators.extend(
            [extra for extra in extras_values if "monstercat" not in extra.lower()]
        )
    if include_artist:
        disambiguators.append(artist)

    page = get_page_from_titles(titles, disambiguators)
    return page


@cache
def get_genres_from_monstercat_page(page: EnhancedFandomPage):
    genres_found = []
    for genre_section_soup in page.soup.find_all(
        "div", {"data-source": re.compile(".*[gG]enre.*")}
    ):
        for genre_soup in genre_section_soup.find_all("a"):
            for genre_entry in genre_soup.contents:
                genres = [genre.strip() for genre in genre_entry.split("|")]
                genres_found.extend(genres)
    return deduplicate(genres_found)


@cache
def get_titles_from_monstercat_page(page: EnhancedFandomPage):
    results = []
    for sub_soup in page.soup.find_all(attrs={"data-source": "Name"}):
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

    def get_fields_from_monstercat_wiki(self, known_fields: dict[str, list[str]]):
        page = get_page_from_known_fields(known_fields)
        fields = {
            "titles": get_titles_from_monstercat_page(page),
            "genres": get_genres_from_monstercat_page(page),
            "extras": {"wiki_url": [page.url]},
        }
        LOGGER.info("got fields from monstercat wiki: %s", fields)
        return fields


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
        for required_field in ["titles", "artists"]:
            if required_field not in fields_combined:
                LOGGER.error(
                    "required field '%s' missing from fields_combined=%s",
                    required_field,
                    fields_combined,
                )
                return {}
        return self.genreliser.get_fields_from_monstercat_wiki(fields_combined)

    def get_fields_from_sources(self):
        """generates fields, removing titles from tag if not also from wiki"""
        fields = super().get_fields_from_sources()

        # trust the wiki over the title tag:
        #  remove any song titles from the title tag that aren't in the wiki
        self.__dict__["fields_from_title"]["titles"] = [
            title
            for title in self.__dict__["fields_from_title"]["titles"]
            if title in self.__dict__["fields_from_wiki"]["titles"]
        ]
        return fields
