"""P0：系统态失败可见（非 speech）。"""

from __future__ import annotations

import pytest
from qi.embodiment.system_notice import kind_from_llm_failure, notice_payload
from qi.llm.gateway import LLMGateway
from qi.llm.providers.openai_compat import OpenAICompatProvider


def test_notice_payload_kinds():
    for kind in (
        "missing_key",
        "unreachable",
        "empty",
        "timeout",
        "turn_busy",
        "queue_full",
        "delivery_timeout",
    ):
        p = notice_payload(kind)  # type: ignore[arg-type]
        assert p["kind"] == kind
        assert p["message"]


def test_kind_from_llm_failure():
    assert kind_from_llm_failure("missing_key") == "missing_key"
    assert kind_from_llm_failure("unreachable") == "unreachable"
    assert kind_from_llm_failure("empty") == "empty"
    assert kind_from_llm_failure(None) is None
    assert kind_from_llm_failure("other") is None


def test_provider_key_missing():
    p = OpenAICompatProvider("t", "http://x", "", {"fast": "m"})
    assert p.key_missing()
    p2 = OpenAICompatProvider("t", "http://x", "sk-real", {"fast": "m"})
    assert not p2.key_missing()


@pytest.mark.asyncio
async def test_gateway_missing_key_no_chat():
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
    out = await gw.call_detailed("conversation", [{"role": "user", "content": "hi"}])
    assert out.failure == "missing_key"
    assert out.text == ""
    assert gw.last_outcome.failure == "missing_key"
