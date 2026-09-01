"""P4 · 日志落盘（最小）。"""

from __future__ import annotations

import logging
from pathlib import Path

from qi.logging_setup import (
    BACKUP_COUNT,
    MAX_BYTES,
    configure_app_logging,
    log_file_path,
    logs_dir,
)
from qi.paths import ENV_DATA_DIR


def _reset_root_logging():
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    if hasattr(root, "_qi_app_logging_configured"):
        delattr(root, "_qi_app_logging_configured")


def test_configure_app_logging_writes_rotating_file(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    _reset_root_logging()
    try:
        path = configure_app_logging()
        assert path == tmp_path / "logs" / "qi.log"
        assert logs_dir() == tmp_path / "logs"
        assert log_file_path() == path
        assert path.parent.is_dir()

        logging.getLogger("qi.test_logging").info("hello-file-log")
        for h in logging.getLogger().handlers:
            h.flush()
        text = path.read_text(encoding="utf-8")
        assert "hello-file-log" in text

        # 幂等：再调不叠 handler
        n = len(logging.getLogger().handlers)
        configure_app_logging()
        assert len(logging.getLogger().handlers) == n

        # 轮转参数
        file_handlers = [
            h
            for h in logging.getLogger().handlers
            if h.__class__.__name__ == "RotatingFileHandler"
        ]
        assert len(file_handlers) == 1
        assert file_handlers[0].maxBytes == MAX_BYTES
        assert file_handlers[0].backupCount == BACKUP_COUNT
    finally:
        _reset_root_logging()


def test_open_logs_folder_creates_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    opened: list[Path] = []

    def fake_open(path=None):
        from qi.paths import resolve_data_root

        root = path or resolve_data_root()
        root.mkdir(parents=True, exist_ok=True)
        opened.append(root)
        return True, str(root)

    monkeypatch.setattr("qi.paths.open_data_folder", fake_open)
    from qi.logging_setup import open_logs_folder

    ok, detail = open_logs_folder()
    assert ok
    assert opened == [tmp_path / "logs"]
    assert (tmp_path / "logs").is_dir()
    assert detail == str(tmp_path / "logs")
