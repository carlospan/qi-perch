"""P2：用户密钥文件（设置页最小钥匙）。"""

from __future__ import annotations

import os

from qi.config.secrets import (
    SECRET_API_KEY,
    SECRET_API_KEY_ALIAS,
    SECRET_BASE_URL,
    SECRET_MODEL,
    apply_secrets_to_environ,
    apply_user_llm_overrides,
    mask_api_key,
    read_secrets_file,
    settings_llm_snapshot,
    write_secrets_file,
)


def test_mask_api_key():
    assert mask_api_key("") == ""
    assert "••••" in mask_api_key("sk-abcdefghijklmnop")
    assert mask_api_key("short")[-2:] == "rt"


def test_write_read_secrets_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "user_secrets.env"
    write_secrets_file(
        api_key="sk-test-key-12345678",
        base_url="https://example.com/v1",
        model="demo-model",
        path=path,
    )
    data = read_secrets_file(path)
    assert data[SECRET_API_KEY] == "sk-test-key-12345678"
    assert data[SECRET_API_KEY_ALIAS] == "sk-test-key-12345678"
    assert data[SECRET_BASE_URL] == "https://example.com/v1"
    assert data[SECRET_MODEL] == "demo-model"
    text = path.read_text(encoding="utf-8")
    assert "sk-test-key-12345678" in text

    write_secrets_file(api_key="", base_url="", model="", path=path)
    data2 = read_secrets_file(path)
    assert SECRET_API_KEY not in data2
    assert SECRET_BASE_URL not in data2
    assert SECRET_MODEL not in data2


def test_write_preserves_unset_fields(tmp_path):
    path = tmp_path / "user_secrets.env"
    write_secrets_file(api_key="sk-keep-me-abcdef", path=path)
    write_secrets_file(base_url="https://only-base", path=path)
    data = read_secrets_file(path)
    assert data[SECRET_API_KEY] == "sk-keep-me-abcdef"
    assert data[SECRET_BASE_URL] == "https://only-base"


def test_apply_secrets_and_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "user_secrets.env"
    monkeypatch.setattr(
        "qi.config.secrets.user_secrets_path", lambda: path
    )
    for k in (SECRET_API_KEY, SECRET_API_KEY_ALIAS, SECRET_BASE_URL, SECRET_MODEL):
        monkeypatch.delenv(k, raising=False)

    write_secrets_file(
        api_key="sk-snap-key-99999999",
        base_url="https://snap.test/v1",
        model="snap-m",
        path=path,
    )
    apply_secrets_to_environ()
    assert os.environ[SECRET_API_KEY] == "sk-snap-key-99999999"
    snap = settings_llm_snapshot()
    assert snap["has_key"] is True
    assert "9999" in snap["api_key_masked"] or "••••" in snap["api_key_masked"]
    assert snap["base_url"] == "https://snap.test/v1"
    assert snap["model"] == "snap-m"
    assert "sk-snap-key-99999999" not in snap["api_key_masked"]


def test_apply_user_llm_overrides(monkeypatch):
    monkeypatch.setenv(SECRET_API_KEY, "sk-override-aaaaaaaa")
    monkeypatch.setenv(SECRET_BASE_URL, "https://override/v1")
    monkeypatch.setenv(SECRET_MODEL, "override-model")
    cfg = {
        "llm": {
            "default_provider": "ark",
            "custom_providers": {
                "ark": {
                    "base_url": "https://old",
                    "api_key": "",
                    "models": {"fast": "old-fast", "strong": "old-strong"},
                }
            },
        }
    }
    out = apply_user_llm_overrides(cfg)
    z = out["llm"]["custom_providers"]["ark"]
    assert z["api_key"] == "sk-override-aaaaaaaa"
    assert z["base_url"] == "https://override/v1"
    assert z["models"]["fast"] == "override-model"
    assert z["models"]["strong"] == "override-model"


def test_notice_missing_key_mentions_gear():
    from qi.embodiment.system_notice import notice_payload

    p = notice_payload("missing_key")
    assert p["action"] == "open_settings"
    assert "齿轮" in p["message"]
