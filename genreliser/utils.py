import json
import logging
import platform
import sys
import time
import urllib.request
from collections.abc import Iterable
from contextlib import contextmanager
from logging.config import fileConfig
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import HTTPError

from tqdm import tqdm
from utils_python.main import deduplicate, dump_data, serialize_data
from yt_dlp.utils import sanitize_filename

LOGGER = logging.getLogger("genreliser")


def noop(*_args, **_kwargs):
    pass


def identity(e):
    return e


@contextmanager
def write_at_exit(
    obj,
    filepath: Path | str | None,
    indent: int | None = 4,
    overwrite: bool = False,
    default_encode: Callable = str,
    no_warning=False,
):
    if filepath is None:
        yield
        return

    if not isinstance(filepath, Path):
        filepath = Path(filepath)

    if not filepath.parent.is_dir():
        raise NotADirectoryError(filepath)

    if filepath.exists():
        if overwrite:
            if not no_warning:
                LOGGER.warning("file '%s' exists and will be overwritten", filepath)
        else:
            raise FileExistsError(filepath)
    LOGGER.info("will write %s to '%s'", type(obj), filepath)

    try:
        yield

    finally:
        obj_str = truncate_str(str(obj), 30)
        LOGGER.info(f"writing {obj_str} to {filepath}")
        dump_data(serialize_data(obj, indent=indent, default=default_encode), filepath)


def truncate_str(s: str, max_length: int, end="..."):
    if max_length <= len(end):
        raise ValueError(
            f"truncate_str(): {max_length=} must be greater than {len(end)=}"
        )
    if len(s) > max_length:
        return s[: max_length - len(end)] + end
    return s


def setup_excepthook(logger: logging.Logger, keyboardinterrupt_log_str):
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            if keyboardinterrupt_log_str:
                logger.info(keyboardinterrupt_log_str)
            else:
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
        else:
            logger.critical(
                "Exception occured:", exc_info=(exc_type, exc_value, exc_traceback)
            )

    sys.excepthook = handle_exception


def setup_logging(config_path: Path | str) -> None:
    if not isinstance(config_path, Path):
        config_path = Path(config_path)
    if not config_path.is_file():
        path = config_path if config_path.is_absolute() else config_path.resolve()
        raise FileNotFoundError(f"No such file or directory: '{path}")
    fileConfig(config_path, disable_existing_loggers=False)


def str_upper(value):
    return str(value).upper()


def get_platform() -> str:
    return platform.system().lower()


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


def read_list_from_file(
    filepath: Path, element_fn=identity, deduplicate_list=True, optional=True
):
    if not filepath.is_file():
        if optional:
            return []
        raise FileNotFoundError(f"Tried to read from {filepath}, but it was not a file")

    with open(filepath) as f:
        file_lines_str = f.readlines()

    try:
        file_lines_list = json.loads(" ".join(file_lines_str))
        if not isinstance(file_lines_list, list):
            raise ValueError(
                f"Expected list from {filepath}, got {type(file_lines_list)}"
            )
    except json.decoder.JSONDecodeError:
        file_lines_list = [line.strip() for line in file_lines_str]

    if deduplicate_list:
        file_lines_list = deduplicate(file_lines_list)

    results = []
    for line in file_lines_list:
        try:
            result = element_fn(line)
        except TypeError as exc:
            raise TypeError(
                f"Failed to call {element_fn.__name__ or element_fn}({line})"
            ) from exc
        results.append(result)

    return results


def read_dict_from_file(
    filepath: Path, key_fn=identity, value_fn=identity, optional=True
):
    if not filepath.is_file():
        if optional:
            return {}
        raise FileNotFoundError(f"Tried to read from {filepath}, but it was not a file")

    with open(filepath) as f:
        file_contents = f.read()

    if not file_contents:
        return {}

    try:
        json_data = json.loads(file_contents)
    except json.decoder.JSONDecodeError as exc:
        raise ValueError(f"Could not load {filepath} as JSON") from exc
    if not isinstance(json_data, dict):
        raise ValueError(f"Expected dict from {filepath}, got {type(json_data)}")

    return {key_fn(key): value_fn(value) for key, value in json_data.items()}


def run_on_path(
    path: Path,
    file_callback: Optional[Callable[[Path], Any]] = None,
    dir_callback: Optional[Callable[[Path], Any]] = None,
    depth=0,
):
    if not isinstance(path, Path):
        path = Path(path)
    path_results: dict[str, Any]
    if path.is_file():
        path_results = {"is_dir": False}
        if file_callback is not None:
            path_results["result"] = file_callback(path)
        return {path: path_results}
    if path.is_dir():
        path_results = {"is_dir": True}
        if dir_callback is not None:
            path_results["result"] = dir_callback(path)
        subpath_results: dict[Path, dict[str, Any]] = {}
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
    raise TypeError(f"{path=!r} was not a file or a dir")


last_requests: dict[str | None, float] = {}


def make_get_request_to_url(url: str, src_key: str | None = None):
    LOGGER.info(f"making GET request to {url}")
    last_request = last_requests.get(src_key)
    # TODO: remove src_key, get website from url instead
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
            if exc.code == 404:  # NOT_FOUND
                return None
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


def is_iterable(obj, excluded_types=None):
    if excluded_types is None:
        excluded_types = [str]
    return isinstance(obj, Iterable) and not isinstance(obj, excluded_types)


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
