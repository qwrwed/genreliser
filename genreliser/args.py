import argparse
import logging
from pathlib import Path

from genreliser.utils import get_platform


class ArgsNamespace(argparse.Namespace):
    path: Path
    dry_run: bool
    log_level: str
    logging_config_path: Path


def str_upper(value):
    return str(value).upper()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, default="./testing", nargs="?")
    parser.add_argument(
        "-e",
        "--execute",
        dest="dry_run",
        action="store_false",
        help="actually update metadata",
    )
    parser.add_argument(
        "-g",
        "--log-level",
        choices=logging._levelToName.values(),
        metavar="LOG_LEVEL",
        help="minimum level at which messages should be logged (choice of %(choices)s)",
        default="INFO",
        type=str_upper,
    )
    parser.add_argument(
        "-l",
        "--logging-config-path",
        default=f"config/logging-{get_platform()}.cfg",
        help="Path to logging config file (default: %(default)r)",
        type=Path,
    )
    return parser.parse_args(namespace=ArgsNamespace())
