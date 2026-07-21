"""工作记忆：此刻脑中正想着的对话片段。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    role: str  # "user" | "qi"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now()


class WorkingMemory:
    """维护最近 N 条对话。溢出的不丢，交还给调用方去沉淀。"""

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._messages: list[Message] = []

    def add(self, role: str, content: str) -> Message | None:
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        overflow = None
        if len(self._messages) > self.max_size:
            overflow = self._messages.pop(0)
        return overflow

    def get_context(self) -> list[dict]:
        return [
            {
                "role": "assistant" if m.role == "qi" else "user",
                "content": m.content,
            }
            for m in self._messages
        ]

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def load_from_db(self, messages: list[dict]) -> None:
        self._messages = [
            Message(
                role=m["role"],
                content=m["content"],
                timestamp=_parse_timestamp(m.get("timestamp")),
            )
            for m in messages[-self.max_size :]
        ]
