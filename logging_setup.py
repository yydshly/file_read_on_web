"""Application logging configuration.

One module for the whole project to import from. Uses a rotating file handler
so the log directory doesn't grow unbounded, plus a console handler that keeps
the existing terminal output behaviour.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_initialized = False


def init_logging(data_dir: Path, level: int = logging.INFO) -> Path:
    """Configure the root logger. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return data_dir / "logs"

    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if something already configured logging
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file), maxBytes=2 * 1024 * 1024, backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)
    root.addHandler(console)

    # Silence the most chatty libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _initialized = True
    return log_dir


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
