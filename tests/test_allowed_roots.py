"""允许根配置（P2 · disk/write 共用）。"""

from __future__ import annotations

import json
from pathlib import Path

from qi.action.allowed_roots import (
    FILENAME,
    load_allowed_roots,
    normalize_under_roots,
    save_allowed_roots,
    set_roots_override,
    snapshot_for_settings,
)
from qi.action.disk import normalize_under_root as disk_norm
from qi.paths import ENV_DATA_DIR


def test_default_empty_without_d(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    monkeypatch.setattr(
        "qi.action.allowed_roots._d_drive_exists", lambda: False
    )
    set_roots_override(None)
    assert load_allowed_roots(data_root=tmp_path) == []
    snap = snapshot_for_settings()
    # snapshot uses resolve_data_root via env
    assert snap["empty"] is True


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    set_roots_override(None)
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    saved = save_allowed_roots([a, b, a], data_root=tmp_path)
    assert len(saved) == 2
    path = tmp_path / FILENAME
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["roots"]) == 2
    loaded = load_allowed_roots(data_root=tmp_path)
    assert {p.resolve() for p in loaded} == {a.resolve(), b.resolve()}


def test_normalize_under_any_root(tmp_path):
    r1 = tmp_path / "r1"
    r2 = tmp_path / "r2"
    r1.mkdir()
    r2.mkdir()
    f = r2 / "note.txt"
    f.write_text("x", encoding="utf-8")
    roots = [r1, r2]
    assert normalize_under_roots(str(f), roots=roots) == f.resolve()
    assert normalize_under_roots(str(tmp_path / "out.txt"), roots=roots) is None


def test_disk_uses_override_via_default_allowed_root(monkeypatch, tmp_path):
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    assert disk_norm(str(tmp_path / "x.txt")) == (tmp_path / "x.txt").resolve()
    assert disk_norm(str(tmp_path.parent / "nope.txt")) is None


def test_wipe_memory_keeps_allowed_roots(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    roots_file = tmp_path / FILENAME
    roots_file.write_text(
        json.dumps({"roots": [str(tmp_path)]}), encoding="utf-8"
    )
    (tmp_path / "qi.db").write_bytes(b"x")
    from qi.data_lifecycle import wipe_memory_artifacts

    ok, _ = wipe_memory_artifacts(tmp_path)
    assert ok
    assert roots_file.is_file()
    assert not (tmp_path / "qi.db").exists()
