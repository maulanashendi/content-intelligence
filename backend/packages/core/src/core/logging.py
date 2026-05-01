import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pythonjsonlogger.json import JsonFormatter


def configure_logging(
    level: str = "INFO",
    file_path: Path | str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    handlers: list[logging.Handler] = []

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    handlers.append(stdout_handler)

    if file_path is not None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level)
