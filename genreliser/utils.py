import json
import logging
import time
import urllib.request
from os import PathLike
from pathlib import Path
from pprint import pprint
from typing import Any, Callable, Optional
from urllib.error import HTTPError

from tqdm import tqdm
from utils_python.main import dump_data
from yt_dlp.utils import sanitize_filename

LOGGER = logging.getLogger("genreliser")


def dump_html(html):
    dump_data(html, "tmp.html")


def restrict_filename(filename):
    return sanitize_filename(filename, restricted=True)


def ensure_caps(s: str):
    """
    makes first letter of every word uppercase, but doesn't make anything else lowercase
    """
    if len(s) == 0:
        breakpoint()
        pass
    s_parts = []
    for s_part in s.split(" "):
        s_part_caps = s_part[0].upper()
        if len(s_part) > 1:
            s_part_caps += s_part[1:]
        s_parts.append(s_part_caps)
    s_caps = " ".join(s_parts)
    return s_caps


def sort_dict(d, sortkey=lambda x: x):
    return {key: dict(sorted(d[key].items(), key=sortkey)) for key in sorted(d)}


def noop(*_args, **_kwargs):
    pass


def run_on_path(
    path: PathLike,
    file_callback: Optional[Callable[[Path], Any]] = None,
    dir_callback: Optional[Callable[[Path], Any]] = None,
    depth=0,
):
    if not isinstance(path, Path):
        path = Path(path)
    if path.is_file():
        path_results = {"is_dir": False}
        if file_callback is not None:
            path_results["result"] = file_callback(path)
        return {path: path_results}
    elif path.is_dir():
        path_results = {"is_dir": True}
        if dir_callback is not None:
            path_results["result"] = dir_callback(path)
        subpath_results = {}
        subpaths = list(path.iterdir())
        with tqdm(subpaths, leave=depth == 0) as pbar:
            for i, subpath in enumerate(pbar):
                pbar.set_description(str(subpath))
                subpath_dict = run_on_path(
                    subpath, file_callback, dir_callback, depth + 1
                )
                subpath_results.update(subpath_dict)
                if i == len(subpaths) - 1:
                    pbar.set_description(repr(path))
            pbar.set_description(repr(path))
        path_results["contents"] = subpath_results
        return {path: path_results}
    else:
        raise TypeError(f"{path=!r} was not a file or a dir")


last_requests = {}


def get_from_url(url: str, src_key: str | None = None):
    LOGGER.info(f"requesting {url}")
    last_request = last_requests.get(src_key)
    if last_request is not None and time.time() - last_request <= 1:
        time.sleep(1)
    while True:
        try:
            last_requests[src_key] = time.time()
            req = urllib.request.Request(url)
            req.add_header(
                "User-Agent",
                "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7",
            )
            with urllib.request.urlopen(req) as url_open:
                res_bytes = url_open.read()
            break
        except HTTPError as exc:
            if exc.code == 429:  # TOO_MANY_REQUESTS
                time.sleep(1)
                continue
            elif exc.code == 404:  # NOT_FOUND
                return None
            else:
                LOGGER.info(
                    f"unhandled HTTP error code={exc.code!r} msg={exc.msg!r} url={exc.url!r}"
                )
                breakpoint()
                return None
    res_str = res_bytes.decode()
    try:
        return json.loads(res_str)
    except json.decoder.JSONDecodeError:
        return res_str
