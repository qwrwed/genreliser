import logging

from genreliser.args import get_args
from genreliser.monstercat import MonstercatGenreliser
from genreliser.utils import setup_excepthook, setup_logging

LOGGER = logging.getLogger("genreliser")


def main():
    args = get_args()
    setup_logging(args.logging_config_path)
    setup_excepthook(LOGGER)
    LOGGER.info(f"{args.path=}")
    genreliser = MonstercatGenreliser()
    genreliser.genrelise_path(args.path)


if __name__ == "__main__":
    main()
