import argparse
from pathlib import Path


class ArgsNamespace(argparse.Namespace):
    path: Path
    dry_run: bool


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
    return parser.parse_args(namespace=ArgsNamespace())
