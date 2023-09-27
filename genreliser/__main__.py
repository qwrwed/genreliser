import logging

from genreliser.args import get_args
from genreliser.monstercat import MonstercatGenreliser
from genreliser.utils import setup_excepthook, setup_logging, write_at_exit

LOGGER = logging.getLogger("genreliser")


def main():
    args = get_args()
    setup_logging(args.logging_config_path)
    setup_excepthook(LOGGER)
    genreliser = MonstercatGenreliser()
    with write_at_exit(
        genreliser.json_data, args.json_data_output_path, overwrite=args.overwrite
    ), write_at_exit(
        genreliser.failed_files, args.failed_files_output_path, overwrite=args.overwrite
    ):
        for path in args.paths:
            LOGGER.info(f"{path=}")
            genreliser.genrelise_path(
                path,
                retry_failed=args.retry_failed,
            )


if __name__ == "__main__":
    main()
