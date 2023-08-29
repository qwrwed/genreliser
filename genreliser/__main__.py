from args import get_args
from monstercat import MonstercatGenreliser
from utils_python.tqdm import setup_tqdm_logger

LOGGER = setup_tqdm_logger("genreliser")


def main():
    args = get_args()
    LOGGER.info(f"{args.path=}")
    genreliser = MonstercatGenreliser()
    genreliser.genrelise_path(args.path)


if __name__ == "__main__":
    main()
