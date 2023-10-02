import logging

from utils_python import dump_data
from yt_dlp.utils import sanitize_filename

LOGGER = logging.getLogger("genreliser")


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
