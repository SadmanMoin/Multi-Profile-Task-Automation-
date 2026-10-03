"""Application logging. Workflow activity is stored separately in SQLite."""

from __future__ import annotations

import logging
import sys

from app.utils.paths import get_logs_dir
from app.utils.redact import redact_text


class RedactFilter(logging.Filter):
    """Replace secret-looking text before a record is written."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg = redact_text(message)
        record.args = ()
        return True


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("bta")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    log_path = get_logs_dir() / "app.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    redact_filter = RedactFilter()
    file_handler.addFilter(redact_filter)
    stream_handler.addFilter(redact_filter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"bta.{name}")
