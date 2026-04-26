import logging
from logging.handlers import RotatingFileHandler


def configure_logging(config):
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not config.log_file:
        return

    handler = RotatingFileHandler(
        config.log_file,
        maxBytes=1_000_000,
        backupCount=3,
    )
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.getLogger("").addHandler(handler)
