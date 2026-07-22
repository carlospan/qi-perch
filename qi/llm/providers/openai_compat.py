"""OpenAI 兼容端点的统一 provider。deepseek / agnes-ai / 自定义共用。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI


class OpenAICompatProvider:
    """一块通用的嘴巴——换 base_url 就能换模型。"""

    def __init__(self, name: str, base_url: str, api_key: str, models: dict[str, str]):
        self.name = name
        self.models = models
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "no-key")
        self._active_model: str = models.get("fast") or next(iter(models.values()))

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
        response = await self._client.chat.completions.create(
            model=chosen,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""

    async def stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        chosen = model or self._active_model
        stream = await self._client.chat.completions.create(
            model=chosen,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
