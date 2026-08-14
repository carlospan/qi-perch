"""统一的 LLM 调用入口。按 purpose 路由，失败时温柔地沉默。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from qi.llm.providers.openai_compat import OpenAICompatProvider

logger = logging.getLogger("qi.llm")

# 失败语义：unreachable=到不了模型；empty=管道通了但没话
LLMFailureKind = Literal["unreachable", "empty"]


@dataclass(frozen=True)
class LLMCallOutcome:
    """一次调用的结果——文本 + 可选失败级别。"""

    text: str
    failure: LLMFailureKind | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None and bool(self.text.strip())


_DEFAULT_TEMPERATURES = {
    "conversation": 0.7,
    "consciousness": 0.85,
    "dream": 1.1,
    "narrative": 0.75,
    "reflection": 0.8,
    "creation": 0.95,
    "fact": 0.3,
    "look": 0.5,
}

# last_outcome 初始成功态（failure=None）；仅 conversation 用途会刷新它
_SUCCESS_IDLE = LLMCallOutcome(text="", failure=None)


class LLMGateway:
    """栖对外说话、对内思考时，都从这里经过。"""

    def __init__(self, config: dict):
        self.providers: dict[str, OpenAICompatProvider] = {}
        self.routing: dict = config.get("llm", {}).get("model_routing", {})
        self._default_provider = config.get("llm", {}).get("default_provider", "sensenova")
        self.last_outcome: LLMCallOutcome = _SUCCESS_IDLE
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
            key = str(api_key).strip()
            if not key or key == "no-key" or (
                key.startswith("${") and key.endswith("}")
            ):
                logger.warning(
                    "LLM provider %s 的 api_key 为空或未展开，对话可能沉默；"
                    "请检查 settings.yaml / 环境变量",
                    name,
                )
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

    def _remember_if_conversation(self, purpose: str, outcome: LLMCallOutcome) -> None:
        """只让对话用途刷新 last_outcome，免得后台编织/梦盖掉脑要读的级别。"""
        if purpose == "conversation":
            self.last_outcome = outcome

    async def call_detailed(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> LLMCallOutcome:
        """
        按用途调用模型，带回失败分级。
        异常路径最多重试 2 次；EMPTY（成功但空白）不重试。
        """
        if temperature is None:
            temperature = _DEFAULT_TEMPERATURES.get(purpose, 0.7)

        try:
            provider, model = self._resolve(purpose)
        except RuntimeError as e:
            logger.warning("LLM 路由失败 purpose=%s: %s", purpose, e)
            outcome = LLMCallOutcome(text="", failure="unreachable")
            self._remember_if_conversation(purpose, outcome)
            return outcome

        last_error: Exception | None = None
        for attempt in range(3):  # 首次 + 2 次重试
            try:
                raw = await provider.chat(
                    messages=messages,
                    temperature=temperature,
                    model=model,
                )
                text = (raw or "").strip()
                if not text:
                    outcome = LLMCallOutcome(text="", failure="empty")
                    logger.warning(
                        "LLM 返回空内容 provider=%s purpose=%s",
                        provider.name,
                        purpose,
                    )
                else:
                    outcome = LLMCallOutcome(text=text, failure=None)
                self._remember_if_conversation(purpose, outcome)
                return outcome
            except Exception as e:
                last_error = e
                wait = 2**attempt  # 1s, 2s, 4s
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
        outcome = LLMCallOutcome(text="", failure="unreachable")
        self._remember_if_conversation(purpose, outcome)
        return outcome

    async def call(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> str:
        """
        按用途调用模型。失败最多重试 2 次；全部失败返回空串，不抛到 brain。
        兼容旧调用方；分级细节见 call_detailed / last_outcome。
        """
        outcome = await self.call_detailed(purpose, messages, temperature)
        return outcome.text

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
