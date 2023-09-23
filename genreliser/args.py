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
    failed_files_output_path: Path


def get_args():
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
        help="actually update metadata",
    )

    parser.add_argument(
        "-f",
        "--failed-files-output-path",
        default=datetime.datetime.now().strftime(r"data/failed_%Y-%m-%dT%H-%M-%S.txt"),
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
