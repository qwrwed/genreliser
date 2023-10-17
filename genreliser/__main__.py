from __future__ import annotations

import logging
from contextlib import nullcontext
from functools import partial
from pathlib import Path

from utils_python import (
    read_dict_from_file,
    read_list_from_file,
    setup_config_logging,
    setup_excepthook,
    write_at_exit,
)

from genreliser.args import get_args
from genreliser.monstercat import MonstercatGenreliser

LOGGER = logging.getLogger("genreliser")


def main():
    args = get_args()
    setup_config_logging(args.logging_config_path)
    setup_excepthook(LOGGER, "received KeyboardInterrupt; exiting.")

    previous_failed_files = read_list_from_file(args.failed_files_path, element_fn=Path)
    LOGGER.info(
        "found %s previous_failed_files from '%s'",
        len(previous_failed_files),
        args.failed_files_path,
    )

    previous_json_data = read_dict_from_file(args.json_data_path, key_fn=Path)
    LOGGER.info(
        "found %s previous_json_data from '%s'",
        len(previous_json_data),
        args.json_data_path,
    )

    genreliser = MonstercatGenreliser(
        previous_failed_files, previous_json_data, args.retry
    )

    if args.readonly:
        data_ctx = failed_ctx = nullcontext
    else:
        data_ctx = partial(
            write_at_exit,
            genreliser.json_data,
            args.json_data_path,
            overwrite=True,
            default_encode=str,
        )
        failed_ctx = partial(
            write_at_exit,
            genreliser.failed_files,
            args.failed_files_path,
            overwrite=True,
            default_encode=str,
        )

    with data_ctx(), failed_ctx():
        genreliser.genrelise_paths(args.paths)


if __name__ == "__main__":
    main()
