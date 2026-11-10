import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = (
        "%(asctime)s %(levelname)s [%(name)s] "
        "%(filename)s:%(lineno)d - %(message)s"
    )

    handlers: list[logging.Handler] = [
        logging.StreamHandler()
    ]

    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        log_file_path = Path(os.getenv("LOG_FILE_PATH", "logs/app.log"))
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        handlers.append(
            RotatingFileHandler(
                filename=log_file_path,
                maxBytes=int(os.getenv("LOG_FILE_MAX_BYTES", "10485760")),
                backupCount=int(os.getenv("LOG_FILE_BACKUP_COUNT", "5")),
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
    )