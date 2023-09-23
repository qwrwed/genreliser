import argparse
import datetime
from pathlib import Path

from utils_python.main import deduplicate

from genreliser.utils import get_platform


class ArgsNamespace(argparse.Namespace):
    paths: list[Path]
    dry_run: bool
    logging_config_path: Path
    batch_file: Path | None
    json_data_output_path: Path
    failed_files_output_path: Path


def get_args():
    now_str = datetime.datetime.now().strftime(r"%Y-%m-%dT%H-%M-%S")

    parser = argparse.ArgumentParser()

    path_group = parser.add_mutually_exclusive_group(required=True)
    path_group.add_argument(
        "paths",
        metavar="FILES_OR_FOLDERS",
        type=Path,
        nargs="*",
        default=[],
        help="path(s) to music file(s) or folder(s)",
    )
    path_group.add_argument(
        "-a",
        "--batch-file",
        metavar="PATH",
        type=Path,
        help="path to text file containing one music file path per line",
    )

    parser.add_argument(
        "-l",
        "--logging-config-path",
        default=f"config/logging_{get_platform()}.cfg",
        help="Path to logging config file (default: %(default)r)",
        type=Path,
    )

    parser.add_argument(
        "-e",
        "--execute",
        dest="dry_run",
        action="store_false",
        help="update metadata in files (will dry-run if not provided)",
    )

    parser.add_argument(
        "-j",
        "--json-data-output-path",
        default=f"data/data_{now_str}.json",
        type=Path,
        help="file to write retrieved data to (default: %(default)r)",
    )
    parser.add_argument(
        "-f",
        "--failed-files-output-path",
        default=f"data/failed_{now_str}.txt",
        type=Path,
        help="file to write failed paths to (default: %(default)r)",
    )

    args = parser.parse_args(namespace=ArgsNamespace())

    if args.batch_file is not None:
        with open(args.batch_file) as f:
            args.paths.extend(
                deduplicate([Path(line.strip()) for line in f.readlines()])
            )
        args.batch_file = None

    return args
