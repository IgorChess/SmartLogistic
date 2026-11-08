import logging
import sys


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
