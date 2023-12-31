from __future__ import annotations

import logging
import re
import unicodedata

import unidecode
from utils_python import dump_data
from yt_dlp.utils import sanitize_filename

LOGGER = logging.getLogger("genreliser")


def char_filter(string):
    # https://stackoverflow.com/a/46041974
    latin = re.compile("[a-zA-Z]+")
    for char in unicodedata.normalize("NFC", string):
        decoded = unidecode.unidecode(char)
        if latin.match(decoded):
            yield char
        else:
            yield decoded


def clean_string(string):
    # https://stackoverflow.com/a/46041974
    return "".join(char_filter(string))


def ensure_one(l, allow_zero=False):
    if len(l) > 1:
        raise NotImplementedError(f"Cannot handle list of length > 1: {l}")
    elif len(l) < 1:
        if allow_zero:
            return None
        else:
            raise NotImplementedError(f"Cannot handle list of length < 1: {l}")
    return l[0]


def dump_html(html):
    dump_data(html, "tmp.html")


def restrict_filename(filename):
    return sanitize_filename(filename, restricted=True)


def combine_listdicts(*listdicts: dict[str, list | str | dict]):
    if len(listdicts) == 1:
        listdicts = listdicts[0]
    combined: dict[str, list | str] = {}
    for listdict in listdicts:
        for k, v in listdict.items():
            if isinstance(v, list) and isinstance(combined.get(k, []), list):
                existing = combined.setdefault(k, [])
                new = [ve for ve in v if ve not in existing and ve is not None]
                existing.extend(new)
            elif isinstance(v, dict) and isinstance(combined.get(k, []), dict):
                existing = combined.setdefault(k, {})
                new = combine_listdicts(existing, v)
                existing.update(new)
            else:
                if k in combined:
                    raise ValueError(
                        f"cannot combine {k}:{v} as it conflicts with existing {k}: {combined.get(k)}"
                    )
                if v is not None:
                    combined[k] = v
    return combined
