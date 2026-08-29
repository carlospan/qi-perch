"""OpenAI 兼容端点的统一 provider（modelscope / sensenova / tokenrhythm / ark 等）。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI


class OpenAICompatProvider:
    """一块通用的嘴巴——换 base_url 就能换模型。"""

    def __init__(self, name: str, base_url: str, api_key: str, models: dict[str, str]):
        self.name = name
        self.models = models
        self.api_key = api_key or ""
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "no-key")
        self._active_model: str = models.get("fast") or next(iter(models.values()))

    def key_missing(self) -> bool:
        key = str(self.api_key).strip()
        return (not key) or key == "no-key" or (
            key.startswith("${") and key.endswith("}")
        )

    def use_tier(self, tier: str) -> str:
        """按档位取出模型名；没有该档则回退到 fast / 第一个。"""
        if tier in self.models:
            return self.models[tier]
        return self.models.get("fast") or next(iter(self.models.values()))

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        model: str | None = None,
    ) -> str:
        chosen = model or self._active_model
        kwargs: dict = {
            "model": chosen,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # GLM-5.3 / flash 强制思考；默认 effort 过高时易把 completion 额度耗在
        # reasoning_content 上导致 content 为空。低强度即可稳定出正文。
        if chosen.lower().startswith("glm"):
            kwargs["reasoning_effort"] = "low"
        response = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content or ""

    async def stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        chosen = model or self._active_model
        kwargs: dict = {
            "model": chosen,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if chosen.lower().startswith("glm"):
            kwargs["reasoning_effort"] = "low"
        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
