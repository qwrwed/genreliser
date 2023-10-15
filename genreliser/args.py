import argparse
import datetime
from pathlib import Path
from typing import Literal

from utils_python import get_platform, read_list_from_file


class ArgsNamespace(argparse.Namespace):
    paths: list[Path]
    # dry_run: bool
    logging_config_path: Path
    json_data_path: Path
    failed_files_path: Path
    retry: Literal["failed", "passed", "all"] | None


def get_args():
    now_str = datetime.datetime.now().strftime(r"%Y-%m-%dT%H-%M-%S")

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "paths",
        metavar="FILES_OR_FOLDERS",
        type=Path,
        nargs="*",
        default=[],
        help="path(s) to: music file(s), folder(s), or file(s) containing list of paths",
    )

    parser.add_argument(
        "-l",
        "--logging-config-path",
        default=f"config/logging_{get_platform()}.cfg",
        help="Path to logging config file (default: %(default)r)",
        type=Path,
    )

    # parser.add_argument(
    #     "-e",
    #     "--execute",
    #     dest="dry_run",
    #     action="store_false",
    #     help="update metadata in files (will dry-run if not provided)",
    # )

    parser.add_argument(
        "-j",
        "--json-data-path",
        default=f"data/data_{now_str}.json",
        type=Path,
        help="file to write retrieved data to (default: %(default)r)",
    )

    parser.add_argument(
        "-f",
        "--failed-files-path",
        default=f"data/failed_{now_str}.json",
        type=Path,
        help="file to write failed paths to (default: %(default)r)",
    )

    parser.add_argument(
        "-r",
        "--retry",
        choices={"failed", "passed", "all"},
        type=lambda s: s.lower(),
        help="retry some or all previous files",
    )

    # TODO: readonly mode?

    args = parser.parse_args(namespace=ArgsNamespace())

    paths_new = []
    for path in args.paths:
        if not path.is_file():
            paths_new.append(path)
        try:
            paths_new.extend(read_list_from_file(path, element_fn=Path))
        except UnicodeDecodeError:
            paths_new.append(path)
    args.paths = paths_new

    return args
