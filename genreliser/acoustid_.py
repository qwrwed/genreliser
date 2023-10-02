import logging
import platform
from functools import cache

import acoustid

from genreliser.env import ACOUSTID_API_KEY
from genreliser.utils import make_get_request_to_url, restrict_filename

LOGGER = logging.getLogger("genreliser")


class AcoustIDNotFoundError(acoustid.AcoustidError):
    ...


def get_fpcalc_url():
    FALLBACK_URL = "https://github.com/acoustid/chromaprint/releases/latest"
    res = make_get_request_to_url(
        "https://api.github.com/repos/acoustid/chromaprint/releases/latest",
        src_key="github",
    )
    user_platform = platform.system().lower()
    platform_urls = [
        link["browser_download_url"]
        for link in res["assets"]
        if user_platform in link["name"]
    ]
    if len(platform_urls) == 1:
        return platform_urls[0]
    return FALLBACK_URL


@cache
def ensure_fpcalc():
    try:
        acoustid.fingerprint_file("")
    except acoustid.NoBackendError as exc:
        raise acoustid.NoBackendError(
            f"fpcalc not found. Download from {get_fpcalc_url()} and extract to current folder."
        ) from exc
    except Exception:
        pass


def get_acoustid(filepath):
    ensure_fpcalc()
    candidates = list(acoustid.match(ACOUSTID_API_KEY, filepath))
    LOGGER.info("candidates = %s", candidates)

    if len(candidates) > 1:
        LOGGER.warning(f"multiple acoustIDs for {filepath}")
        LOGGER.warning(candidates)
        scores = {}
        ids = {}
        for aid_score, res_acoustid, title, artist in candidates:
            ids[res_acoustid] = aid_score, res_acoustid, title, artist
            scores[res_acoustid] = 0
            for component in (title, artist):
                if component is None:
                    continue
                if restrict_filename(component).lower() in str(filepath).lower():
                    scores[res_acoustid] += 1

        best_aid = max(scores, key=scores.get)
        if scores[best_aid] == 0:
            LOGGER.warning("scores=%s", scores)
            LOGGER.warning("no acoustID match!")
            raise AcoustIDNotFoundError()
            # breakpoint()
        aid_score, res_acoustid, title, artist = ids[best_aid]
    elif len(candidates) == 1:
        aid_score, res_acoustid, title, artist = candidates[0]
    else:
        raise AcoustIDNotFoundError(f"no acoustID found for {filepath}")
    return {"acoustid": res_acoustid, "titles": [title], "artists": artist.split("; ")}


def get_acoustid_2(filepath):
    raise NotImplementedError()
    match_result = acoustid.match(
        ACOUSTID_API_KEY,
        filepath,
        parse=False,
    )
    if match_result["status"] != "ok":
        raise AcoustIDNotFoundError(match_result["error"]["message"])
    candidates = match_result["results"]

    if len(candidates) > 1:
        LOGGER.warning(f"multiple acoustIDs for {filepath}")
        LOGGER.warning(candidates)
        scores = {}
        ids = {}
        # for aid_score, res_acoustid, title, artist in candidates:
        for candidate in candidates:
            aid_score = candidate["score"]
            res_acoustid = candidate["id"]
            title
            ids[res_acoustid] = aid_score, res_acoustid, title, artist
            scores[res_acoustid] = 0
            for component in (title, artist):
                if component is None:
                    continue
                if restrict_filename(component).lower() in str(filepath).lower():
                    scores[res_acoustid] += 1

        best_aid = max(scores, key=scores.get)
        if scores[best_aid] == 0:
            LOGGER.warning(scores)
            LOGGER.warning("no acoustID match!")
            breakpoint()
        aid_score, res_acoustid, title, artist = ids[best_aid]
    elif len(candidates) == 1:
        aid_score, res_acoustid, title, artist = candidates[0]
    else:
        raise AcoustIDNotFoundError(f"no acoustID found for {filepath}")
    return {"acoustid": res_acoustid, "titles": [title], "artists": artist.split("; ")}
