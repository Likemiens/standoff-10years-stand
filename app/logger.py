from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import project_path


def setup_logger(config: dict[str, Any]) -> logging.Logger:
    logger = logging.getLogger("standoff")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    if not config.get("logging", {}).get("enabled", True):
        logger.addHandler(logging.NullHandler())
        return logger

    log_path = project_path(config["logging"].get("path", "./logs/events.log"))
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger
