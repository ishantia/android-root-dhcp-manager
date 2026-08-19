"""
Structured Logging Subsystem for Android Root DHCP Manager.
Supports subsystem tagging, file rotation/logging, and console output.
"""

import enum
import logging
import os
import sys
from pathlib import Path
from typing import Optional


class Subsystem(str, enum.Enum):
    ROOT = "ROOT"
    NETWORK = "NETWORK"
    DHCP = "DHCP"
    DNSMASQ = "DNSMASQ"
    CLIENT = "CLIENT"
    CONFIG = "CONFIG"
    TUI = "TUI"
    SYSTEM = "SYSTEM"


class SubsystemFormatter(logging.Formatter):
    """Custom log formatter incorporating subsystem tag."""

    def format(self, record: logging.LogRecord) -> str:
        subsystem = getattr(record, "subsystem", Subsystem.SYSTEM.value)
        record.subsystem_tag = f"[{subsystem}]"
        return super().format(record)


_default_log_dir = Path.home() / ".config" / "android-root-dhcp-manager" / "logs"
_log_file_path = _default_log_dir / "app.log"
_logger_initialized = False


def setup_logger(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    console_output: bool = False,
) -> logging.Logger:
    global _logger_initialized, _log_file_path
    logger = logging.getLogger("dhcp_manager")
    logger.setLevel(level)

    # Avoid duplicate handlers
    if _logger_initialized and logger.handlers:
        return logger

    fmt = "%(asctime)s [%(levelname)s] %(subsystem_tag)s %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = SubsystemFormatter(fmt, datefmt=date_fmt)

    target_path = log_file or _log_file_path
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(target_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Warning: Could not create log file at {target_path}: {e}\n")

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    _logger_initialized = True
    return logger


def set_log_level(level: int) -> None:
    logger = logging.getLogger("dhcp_manager")
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


class SubsystemAdapter(logging.LoggerAdapter):
    """Adapter to effortlessly log messages tagged with a specific subsystem."""

    def __init__(self, logger: logging.Logger, subsystem: Subsystem):
        super().__init__(logger, {"subsystem": subsystem.value})

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        extra["subsystem"] = self.extra["subsystem"]
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(subsystem: Subsystem = Subsystem.SYSTEM) -> SubsystemAdapter:
    base_logger = setup_logger()
    return SubsystemAdapter(base_logger, subsystem)
