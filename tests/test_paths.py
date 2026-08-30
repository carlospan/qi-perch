"""数据根解析（P2 · 大厂方案）。"""

from __future__ import annotations

from pathlib import Path

from qi import PROJECT_ROOT
from qi.paths import (
    ENV_DATA_DIR,
    legacy_repo_data,
    platform_data_root,
    resolve_data_root,
    resolve_under_data,
    strip_data_prefix,
)


def test_strip_data_prefix():
    assert strip_data_prefix(Path("data/qi.db")) == Path("qi.db")
    assert strip_data_prefix(Path("qi.db")) == Path("qi.db")
    assert strip_data_prefix(Path("data")) == Path()


def test_env_overrides_everything(monkeypatch, tmp_path):
    target = tmp_path / "forced"
    target.mkdir()
    monkeypatch.setenv(ENV_DATA_DIR, str(target))
    assert resolve_data_root() == target.resolve()


def test_legacy_repo_data_when_pyproject(monkeypatch):
    monkeypatch.delenv(ENV_DATA_DIR, raising=False)
    # 本仓库有 pyproject + data/ → 开发机无感
    legacy = legacy_repo_data()
    assert legacy is not None
    assert legacy == (PROJECT_ROOT / "data").resolve()
    assert resolve_data_root() == legacy


def test_platform_default_without_legacy(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_DATA_DIR, raising=False)
    # 假装无旧仓：把 legacy 掐掉
    monkeypatch.setattr("qi.paths.legacy_repo_data", lambda: None)
    root = resolve_data_root()
    assert root == platform_data_root().resolve()


def test_resolve_under_data_strips_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    assert resolve_under_data("data/qi.db") == (tmp_path / "qi.db").resolve()
    assert resolve_under_data("chroma") == (tmp_path / "chroma").resolve()


def test_load_config_anchors_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    # 避免读到仓库 data/settings.yaml 盖住 example
    monkeypatch.setenv("QI_CONFIG", str(
        PROJECT_ROOT / "qi" / "config" / "settings.example.yaml"
    ))
    from qi.config import load_config

    cfg = load_config()
    db = Path(cfg["database"]["path"])
    assert db == (tmp_path / "qi.db").resolve()
    chroma = Path(cfg["memory"]["chroma_path"])
    assert chroma == (tmp_path / "chroma").resolve()


def test_user_secrets_under_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    from qi.config.secrets import user_secrets_path

    assert user_secrets_path() == tmp_path / "user_secrets.env"
