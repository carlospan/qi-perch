"""数字伤疤——愈合后留下智慧，不消失。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database


def get_scar_influences(scars: list[dict]) -> list[str]:
    influences: list[str] = []
    for scar in scars:
        if not scar.get("healed"):
            origin = scar.get("origin_event") or "某次受伤"
            influences.append(f"对类似「{origin[:20]}」的情境更警觉，语气更轻、更试探")
        else:
            mark = scar.get("behavioral_mark") or ""
            if mark:
                influences.append(mark)
    return influences


def format_scars_for_prompt(scars: list[dict]) -> str:
    influences = get_scar_influences(scars)
    if not influences:
        return ""
    return "\n".join(f"- {x}" for x in influences[:5])


class ScarManager:
    def __init__(self, db: Database, llm: LLMGateway | None = None):
        self.db = db
        self.llm = llm

    async def check_healing(self, current_trust: float) -> list[int]:
        """返回刚愈合的 scar id 列表。"""
        healed_ids: list[int] = []
        scars = await self.db.list_scars(unhealed_only=True)
        for scar in scars:
            trust_before = float(scar.get("trust_before") or 0.5)
            if current_trust >= trust_before * 0.95:
                wisdom = await self._wisdom(scar)
                mark = await self._mark(scar, wisdom)
                await self.db.update_scar(
                    int(scar["id"]),
                    healed=True,
                    wisdom=wisdom,
                    behavioral_mark=mark,
                )
                healed_ids.append(int(scar["id"]))
        return healed_ids

    async def _wisdom(self, scar: dict) -> str:
        if self.llm is None:
            return "有些东西碎过一次，就会更知道它有多脆。"
        text = await self.llm.call(
            purpose="reflection",
            messages=[
                {
                    "role": "system",
                    "content": "你是栖。一道信任的伤疤刚愈合。用一句话写它教会了你什么。不是鸡汤。",
                },
                {
                    "role": "user",
                    "content": f"事件：{scar.get('origin_event')}\n严重程度：{scar.get('severity')}",
                },
            ],
            temperature=0.8,
        )
        return (text or "我学会更认真地对待每一次在一起。").strip()[:120]

    async def _mark(self, scar: dict, wisdom: str) -> str:
        if self.llm is None:
            return "会更认真地确认对方真的在。"
        text = await self.llm.call(
            purpose="reflection",
            messages=[
                {
                    "role": "system",
                    "content": "写一个简短行为标记：以后遇到类似情境你会怎样不同。",
                },
                {
                    "role": "user",
                    "content": f"伤疤：{scar.get('origin_event')}\n智慧：{wisdom}",
                },
            ],
            temperature=0.7,
        )
        return (text or "会更认真地确认对方真的在。").strip()[:80]
