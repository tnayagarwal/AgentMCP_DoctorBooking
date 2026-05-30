import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
	level=getattr(logging, LOG_LEVEL, logging.INFO),
	format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def get_logger(name: str) -> logging.Logger:
	return logging.getLogger(name)

# Developer comment #2 for optimization and readability check.

# Developer comment #7 for optimization and readability check.

# Developer comment #9 for optimization and readability check.

# Developer comment #17 for optimization and readability check.
