import logging

from genreliser.args import get_args
from genreliser.monstercat import MonstercatGenreliser
from genreliser.utils import setup_excepthook, setup_logging

LOGGER = logging.getLogger("genreliser")


def main():
    args = get_args()
    setup_logging(args.logging_config_path)
    setup_excepthook(LOGGER)
    genreliser = MonstercatGenreliser()
    for path in args.paths:
        LOGGER.info(f"{path=}")
        genreliser.genrelise_path(
            path, failed_files_output_path=args.failed_files_output_path
        )


if __name__ == "__main__":
    main()
