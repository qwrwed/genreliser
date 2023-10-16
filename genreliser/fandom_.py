from __future__ import annotations

from functools import cached_property
from urllib.parse import quote

import fandom.error
import fandom.fandom
import fandom.util
from bs4 import BeautifulSoup
from fandom.FandomPage import STANDARD_URL, FandomPage
from utils_python import ensure_caps


def resolve_wiki(wiki: str):
    return wiki or fandom.fandom.WIKI or "runescape"


def resolve_language(language: str):
    return language or fandom.fandom.LANG or "en"


@fandom.util.cache
def search(
    query: str,
    wiki: str = fandom.fandom.WIKI,
    language: str = fandom.fandom.LANG,
    results: int = 10,
):
    search_params = lambda query: {
        "action": "query",
        "wiki": resolve_wiki(wiki),
        "lang": resolve_language(language),
        "srlimit": results,
        "list": "search",
        "srsearch": query,
    }

    raw_results = fandom.util._wiki_request(search_params(query))
    # breakpoint()

    try:
        search_results = [
            (d["title"], d["pageid"]) for d in raw_results["query"]["search"]
        ]
    except KeyError:
        raise fandom.fandom.FandomError(query, wiki, language)
    return list(search_results)


class EnhancedFandomPage(FandomPage):
    instances_by_title: dict[int, EnhancedFandomPage] = {}
    instances_by_id: dict[str, EnhancedFandomPage] = {}

    def __new__(cls, identifier: str | int, **_kwargs):
        # average time complexity is O(1), so just look in
        #  both dicts and return a new instance if not found
        return (
            cls.instances_by_title.get(identifier)
            or cls.instances_by_id.get(identifier)
            or super().__new__(cls)
        )

    def __init__(
        self,
        identifier: str | int,
        wiki: str = fandom.fandom.WIKI,
        language: str = fandom.fandom.LANG,
        redirect: bool = True,
        preload: bool = False,
    ):
        """
        Get a FandomPage object for the page in the sub fandom with the given identifier.
        If the identifier is a str, it will be interpreted as a title; if an int, it will be the pageid.
        """
        if self.__dict__:
            # we already initialised, so don't do it again
            return

        title = identifier if isinstance(identifier, str) else None
        pageid = identifier if isinstance(identifier, int) else None

        super().__init__(
            resolve_wiki(wiki),
            resolve_language(language),
            title,
            pageid,
            redirect,
            preload,
        )

        self.instances_by_id[self.pageid] = self
        self.instances_by_title[self.title] = self

    def __hash__(self) -> int:
        # allows pages to be used in places that require hashable values
        return hash(self.pageid)

    def __repr__(self):
        # now shows pageid and non-hardcoded class name
        title = getattr(self, "title", None)
        pageid = getattr(self, "pageid", None)
        url = getattr(self, "url", None)
        return fandom.util.stdout_encode(
            f"<{self.__class__.__name__} {title=} {pageid=} {url=}>"
        )

    def _FandomPage__load(self, redirect=True, preload=False):
        # now properly escapes special characters in title before setting `self.url`
        try:
            super()._FandomPage__load(redirect, preload)
        except fandom.error.PageError:
            self.title, title_old = ensure_caps(self.title), self.title
            super()._FandomPage__load(redirect, preload)
            self.instances_by_title[title_old] = self
        self.url = STANDARD_URL.format(
            lang=self.language, wiki=self.wiki, page=quote(self.title)
        )

    @property
    def id(self):
        return self.pageid

    @cached_property
    def html(self):
        # now cached
        return super().html

    @cached_property
    def soup(self):
        # now a cached property
        return BeautifulSoup(self.html, "html.parser")
