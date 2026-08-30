"""P2：设置页试连通。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.config.llm_probe import (
    kind_from_probe_outcome,
    probe_result_payload,
    run_settings_llm_probe,
)
from qi.llm.gateway import LLMCallOutcome, LLMGateway


def test_probe_result_payload_ok():
    p = probe_result_payload(kind="ok")
    assert p["ok"] is True
    assert "通了" in p["message"]


def test_kind_from_probe_outcome():
    assert kind_from_probe_outcome(None) == "ok"
    assert kind_from_probe_outcome("missing_key") == "missing_key"
    assert kind_from_probe_outcome("unreachable", timed_out=True) == "timeout"


@pytest.mark.asyncio
async def test_gateway_probe_missing_key():
    gw = LLMGateway(
        {
            "llm": {
                "default_provider": "z",
                "custom_providers": {
                    "z": {
                        "base_url": "http://127.0.0.1:9",
                        "api_key": "",
                        "models": {"fast": "m"},
                    }
                },
                "model_routing": {"conversation": "z:fast"},
            }
        }
    )
    outcome, timed_out = await gw.probe(timeout_s=1.0)
    assert timed_out is False
    assert outcome.failure == "missing_key"
    assert gw.last_outcome.failure is None  # 不污染对话 last_outcome


@pytest.mark.asyncio
async def test_gateway_probe_ok_and_no_history_side_effect():
    gw = LLMGateway(
        {
            "llm": {
                "default_provider": "z",
                "custom_providers": {
                    "z": {
                        "base_url": "http://127.0.0.1:9",
                        "api_key": "sk-test",
                        "models": {"fast": "m"},
                    }
                },
                "model_routing": {"conversation": "z:fast"},
            }
        }
    )
    provider = next(iter(gw.providers.values()))
    provider.chat = AsyncMock(return_value="好")
    outcome, timed_out = await gw.probe(timeout_s=2.0)
    assert timed_out is False
    assert outcome.ok
    assert gw.last_outcome.failure is None
    provider.chat.assert_awaited_once()
    kwargs = provider.chat.await_args.kwargs
    assert kwargs.get("max_tokens", 0) >= 128



@pytest.mark.asyncio
async def test_gateway_probe_timeout():
    gw = LLMGateway(
        {
            "llm": {
                "default_provider": "z",
                "custom_providers": {
                    "z": {
                        "base_url": "http://127.0.0.1:9",
                        "api_key": "sk-test",
                        "models": {"fast": "m"},
                    }
                },
                "model_routing": {"conversation": "z:fast"},
            }
        }
    )
    provider = next(iter(gw.providers.values()))

    async def _slow(*_a, **_k):
        await asyncio.sleep(2.0)
        return "late"

    provider.chat = _slow
    outcome, timed_out = await gw.probe(timeout_s=0.05)
    assert timed_out is True
    assert not outcome.ok


@pytest.mark.asyncio
async def test_run_settings_llm_probe_maps_timeout():
    llm = MagicMock()
    llm.probe = AsyncMock(
        return_value=(LLMCallOutcome(text="", failure="unreachable"), True)
    )
    result = await run_settings_llm_probe(llm, timeout_s=1.0)
    assert result["ok"] is False
    assert result["kind"] == "timeout"
    assert "等太久" in result["message"]


@pytest.mark.asyncio
async def test_run_settings_llm_probe_ok():
    llm = MagicMock()
    llm.probe = AsyncMock(
        return_value=(LLMCallOutcome(text="hi", failure=None), False)
    )
    result = await run_settings_llm_probe(llm)
    assert result["ok"] is True
    assert result["kind"] == "ok"
