"""记忆导出 / 清空（P2 · 不含钥匙与模型）。"""

from __future__ import annotations

import zipfile

from qi.data_lifecycle import (
    export_memory_backup,
    list_memory_artifacts,
    wipe_memory_artifacts,
)
from qi.paths import ENV_DATA_DIR


def test_export_zip_contains_memory_not_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    monkeypatch.setattr(
        "qi.data_lifecycle.open_data_folder",
        lambda path=None: (True, str(path or tmp_path)),
    )
    (tmp_path / "qi.db").write_bytes(b"sqlite-fake")
    chroma = tmp_path / "chroma"
    chroma.mkdir()
    (chroma / "chunk.bin").write_bytes(b"vec")
    (tmp_path / "user_secrets.env").write_text("API_KEY=secret\n", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    (models / "bge.bin").write_bytes(b"weights")

    ok, msg, zip_path = export_memory_backup(tmp_path, open_folder=False)
    assert ok, msg
    assert zip_path is not None and zip_path.is_file()
    assert zip_path.parent == tmp_path / "backups"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = {n.replace("\\", "/") for n in zf.namelist()}
    assert "qi.db" in names
    assert any(n.startswith("chroma/") for n in names)
    assert "user_secrets.env" not in names
    assert not any(n.startswith("models/") for n in names)


def test_wipe_keeps_secrets_and_models(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    (tmp_path / "qi.db").write_bytes(b"x")
    (tmp_path / "qi.db-wal").write_bytes(b"w")
    chroma = tmp_path / "chroma"
    chroma.mkdir()
    (chroma / "a").write_text("1", encoding="utf-8")
    (tmp_path / "checkpoint").mkdir()
    (tmp_path / "checkpoint" / "c.json").write_text("{}", encoding="utf-8")
    secrets = tmp_path / "user_secrets.env"
    secrets.write_text("K=1\n", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    (models / "m.bin").write_bytes(b"m")
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "old.zip").write_bytes(b"z")

    ok, detail = wipe_memory_artifacts(tmp_path)
    assert ok, detail
    assert not (tmp_path / "qi.db").exists()
    assert not (tmp_path / "qi.db-wal").exists()
    assert not chroma.exists()
    assert not (tmp_path / "checkpoint").exists()
    assert secrets.is_file()
    assert (models / "m.bin").is_file()
    assert (backups / "old.zip").is_file()


def test_export_empty_fails(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    ok, msg, path = export_memory_backup(tmp_path, open_folder=False)
    assert not ok
    assert path is None
    assert "没有" in msg
    assert list_memory_artifacts(tmp_path) == []
