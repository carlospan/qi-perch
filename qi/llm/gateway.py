"""统一的 LLM 调用入口。按 purpose 路由，失败时温柔地沉默。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from qi.llm.providers.openai_compat import OpenAICompatProvider

logger = logging.getLogger("qi.llm")

_DEFAULT_TEMPERATURES = {
    "conversation": 0.7,
    "consciousness": 0.85,
    "dream": 1.1,
    "narrative": 0.75,
    "reflection": 0.8,
    "creation": 0.95,
    "fact": 0.3,
}


class LLMGateway:
    """栖对外说话、对内思考时，都从这里经过。"""

    def __init__(self, config: dict):
        self.providers: dict[str, OpenAICompatProvider] = {}
        self.routing: dict = config.get("llm", {}).get("model_routing", {})
        self._default_provider = config.get("llm", {}).get("default_provider", "deepseek")
        self._init_providers(config)

    def _init_providers(self, config: dict) -> None:
        llm = config.get("llm", {})
        all_providers = {}
        all_providers.update(llm.get("providers") or {})
        all_providers.update(llm.get("custom_providers") or {})

        for name, cfg in all_providers.items():
            if not isinstance(cfg, dict):
                continue
            base_url = cfg.get("base_url", "")
            api_key = cfg.get("api_key", "")
            models = cfg.get("models") or {}
            if not base_url or not models:
                continue
            self.providers[name] = OpenAICompatProvider(
                name=name,
                base_url=base_url,
                api_key=api_key,
                models=models,
            )

    def _resolve(self, purpose: str) -> tuple[OpenAICompatProvider, str]:
        route = self.routing.get(purpose) or self.routing.get("conversation")
        if not route:
            route = f"{self._default_provider}:fast"

        if ":" in route:
            provider_name, tier = route.split(":", 1)
        else:
            provider_name, tier = route, "fast"

        provider = self.providers.get(provider_name)
        if provider is None:
            # 回退到任意已初始化的 provider
            if not self.providers:
                raise RuntimeError("没有可用的 LLM provider，请检查 qi/config/settings.yaml")
            provider = next(iter(self.providers.values()))
            logger.warning("provider %s 未找到，回退到 %s", provider_name, provider.name)

        model = provider.use_tier(tier)
        return provider, model

    async def call(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> str:
        """
        按用途调用模型。失败最多重试 2 次；全部失败返回空串，不抛到 brain。
        """
        if temperature is None:
            temperature = _DEFAULT_TEMPERATURES.get(purpose, 0.7)

        try:
            provider, model = self._resolve(purpose)
        except RuntimeError as e:
            logger.warning("LLM 路由失败 purpose=%s: %s", purpose, e)
            return ""

        last_error: Exception | None = None
        for attempt in range(3):  # 首次 + 2 次重试
            try:
                return await provider.chat(
                    messages=messages,
                    temperature=temperature,
                    model=model,
                )
            except Exception as e:
                last_error = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "LLM 调用失败 provider=%s purpose=%s attempt=%s: %s",
                    provider.name,
                    purpose,
                    attempt + 1,
                    e,
                )
                if attempt < 2:
                    await asyncio.sleep(wait)

        logger.warning(
            "LLM 全部重试失败 provider=%s purpose=%s: %s",
            provider.name,
            purpose,
            last_error,
        )
        return ""

    async def stream(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        if temperature is None:
            temperature = _DEFAULT_TEMPERATURES.get(purpose, 0.7)
        provider, model = self._resolve(purpose)
        async for chunk in provider.stream(messages, temperature=temperature, model=model):
            yield chunk
