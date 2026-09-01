"""栖 · 应用日志（控制台 + 数据根落盘轮转）。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from qi.paths import under_data

_QI_LOGGING_FLAG = "_qi_app_logging_configured"

LOG_FILE_NAME = "qi.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3
DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


def logs_dir() -> Path:
    return under_data("logs")


def log_file_path() -> Path:
    return logs_dir() / LOG_FILE_NAME


def configure_app_logging(*, level: int = logging.INFO) -> Path:
    """
    配置根 logger：StreamHandler + RotatingFileHandler → 数据根 logs/qi.log。
    可重复调用（幂等）；返回主日志文件路径。
    """
    root = logging.getLogger()
    log_path = log_file_path()
    if getattr(root, _QI_LOGGING_FLAG, False):
        return log_path

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(DEFAULT_FORMAT)
    root.setLevel(level)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    setattr(root, _QI_LOGGING_FLAG, True)
    return log_path


def open_logs_folder() -> tuple[bool, str]:
    """在本机文件管理器中打开 logs/。"""
    from qi.paths import open_data_folder

    return open_data_folder(logs_dir())
