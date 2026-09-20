from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from colorama import Fore, Style, init as colorama_init

from .config import LOG_DIR, LOG_FILE

colorama_init(autoreset=True)


def setup_logging(verbose: bool = True) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("backup_v2")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        logger.handlers.clear()
    logger.propagate = False

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    class ColorFmt(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            color = {
                logging.DEBUG: Style.DIM,
                logging.INFO: Fore.GREEN + "✓",
                logging.WARNING: Fore.YELLOW + "➡",
                logging.ERROR: Fore.RED + "✗",
                logging.CRITICAL: Fore.RED + Style.BRIGHT + "✗",
            }.get(record.levelno, "")
            if record.levelno == logging.INFO:
                return f"{color} {record.getMessage()}{Style.RESET_ALL}"
            return f"{color} {super().format(record)}{Style.RESET_ALL}"

    console_handler.setFormatter(ColorFmt("%(message)s"))
    logger.addHandler(console_handler)
    return logger

