import argparse
import datetime
import json
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
    retry_failed: bool | None
    overwrite: bool


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
        "-o",
        "--overwrite",
        action="store_true",
        help="overwrite existing files if present",
    )

    parser.add_argument(
        "-f",
        "--failed-files-output-path",
        default=f"data/failed_{now_str}.json",
        type=Path,
        help="file to write failed paths to (default: %(default)r)",
    )

    handle_failed_group = parser.add_mutually_exclusive_group()
    handle_failed_group.add_argument(
        "-r", "--retry-failed", action="store_const", const=True, dest="retry_failed"
    )
    handle_failed_group.add_argument(
        "-s", "--skip-failed", action="store_const", const=False, dest="retry_failed"
    )

    args = parser.parse_args(namespace=ArgsNamespace())

    if args.retry_failed:
        raise NotImplementedError()

    if args.batch_file is not None:
        with open(args.batch_file) as f:
            file_lines = f.readlines()
            try:
                paths = json.loads(" ".join(file_lines))
                if not isinstance(paths, list):
                    raise ValueError(
                        f"Expected list from {args.batch_file}, got {type(paths)}"
                    )
            except json.decoder.JSONDecodeError:
                paths = [line.strip() for line in file_lines]
            args.paths.extend([Path(path) for path in deduplicate(paths)])
        args.batch_file = None

    return args
