import logging
import pprint
from pprint import pprint

import acoustid
from env import ACOUSTID_API_KEY
from utils import restrict_filename

LOGGER = logging.getLogger("genreliser")


class AcoustIDNotFoundError(Exception):
    ...


def get_acoustid(filepath):
    candidates = list(acoustid.match(ACOUSTID_API_KEY, filepath))

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
            LOGGER.warning(scores)
            LOGGER.warning("no acoustID match!")
            breakpoint()
        aid_score, res_acoustid, title, artist = ids[best_aid]
    elif len(candidates) == 1:
        aid_score, res_acoustid, title, artist = candidates[0]
    else:
        raise AcoustIDNotFoundError(f"no acoustID found for {filepath}")
    return {"acoustid": res_acoustid, "titles": [title], "artists": artist.split("; ")}
