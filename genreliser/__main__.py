import logging
from pathlib import Path

from genreliser.args import get_args
from genreliser.monstercat import MonstercatGenreliser
from genreliser.utils import (
    read_dict_from_file,
    read_list_from_file,
    setup_excepthook,
    setup_logging,
    write_at_exit,
)

LOGGER = logging.getLogger("genreliser")


def main():
    args = get_args()
    setup_logging(args.logging_config_path)
    setup_excepthook(LOGGER, "received KeyboardInterrupt; exiting.")

    previous_failed_files = read_list_from_file(args.failed_files_path, element_fn=Path)
    previous_json_data = read_dict_from_file(args.json_data_path, key_fn=Path)
    LOGGER.info(previous_failed_files)
    genreliser = MonstercatGenreliser(
        previous_failed_files, previous_json_data, args.retry
    )
    with write_at_exit(
        genreliser.json_data,
        args.json_data_path,
        overwrite=True,
        default_encode=str,
    ), write_at_exit(
        genreliser.failed_files,
        args.failed_files_path,
        overwrite=True,
        default_encode=str,
    ):
        for path in args.paths:
            LOGGER.info(f"{path=}")
            genreliser.genrelise_path(path)


if __name__ == "__main__":
    main()
