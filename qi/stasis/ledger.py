"""N0 资源账本：compute / token / storage / income（C2 动力学地基）。

复用 body_memory（key=resource_ledger）；与 ActionBudget 日限并存、不互相替代。
收入仅白名单源（R3）；滚动窗口余额供包 13/14 断粮判定。
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

BODY_MEMORY_KEY = "resource_ledger"

INCOME_SOURCES_WHITELIST: frozenset[str] = frozenset(
    {"effective_interaction", "online_presence"}
)
INCOME_SOURCES_REJECTED: frozenset[str] = frozenset(
    {"satisfaction", "valence_up", "user_pleased"}
)

INCOME_MIN_INTERVAL_SEC = 5.0
INCOME_DAILY_CAP = 200
# 第 3 批标定：单次收入量（事件次数仍受日帽）；支出按比例折算进 balance
EFFECTIVE_INTERACTION_AMOUNT = 25.0
ONLINE_PRESENCE_AMOUNT = 2.0
ONLINE_PRESENCE_MIN_INTERVAL_SEC = 30.0
TOKEN_SPEND_SCALE = 0.05  # 500 token 回复 ≈ 25 支出，约等于一次有效交互收入
STORAGE_ESTIMATE_EVERY_N_BEATS = 50
WINDOW_BEATS = 1000
MEM_RETRIEVAL_TOKEN_COST = 20
ATTEMPT_TOKEN_COST = 10  # 说话失败/空回复仍记尝试成本
COMPUTE_SPEND_PER_SEC = 0.1  # 认知秒 → 支出（原 1.0 易被 LLM 耗时打穿）


class ResourceLedger:
    """资源账本；snapshot/restore 与 ActionBudget 同构。"""

    def __init__(self) -> None:
        self.compute_seconds: float = 0.0
        self.token_budget: float = 0.0
        self.storage_bytes: int = 0
        self.income: float = 0.0  # 终身累计（展示用）
        self.starving: bool = False  # 包 13 写；本包占位
        self.last_interaction_credit_at: datetime | None = None
        self.income_day_count: int = 0
        self.income_day: str | None = None
        self._beat: int = 0
        # 滚动窗口事件：(beat, amount)
        self._spend_events: deque[tuple[int, float]] = deque()
        self._income_events: deque[tuple[int, float]] = deque()
        self._forced_balance: float | None = None

    @property
    def spend_window(self) -> float:
        return float(sum(a for _, a in self._spend_events))

    @property
    def income_window(self) -> float:
        return float(sum(a for _, a in self._income_events))

    @property
    def balance(self) -> float:
        if self._forced_balance is not None:
            return float(self._forced_balance)
        return self.income_window - self.spend_window

    def _prune(self) -> None:
        cutoff = self._beat - WINDOW_BEATS
        while self._spend_events and self._spend_events[0][0] <= cutoff:
            self._spend_events.popleft()
        while self._income_events and self._income_events[0][0] <= cutoff:
            self._income_events.popleft()

    def tick_window(self, beat: int) -> None:
        """推进当前拍号并老化窗口外旧账。"""
        self._beat = int(beat)
        self._prune()

    def add_compute(self, seconds: float) -> None:
        s = max(0.0, float(seconds))
        self.compute_seconds += s
        self.record_spend(s * COMPUTE_SPEND_PER_SEC)

    def add_token_cost(self, n: int) -> None:
        cost = max(0, int(n))
        self.token_budget += float(cost)
        # token_budget 记原始用量；balance 用折算支出（Q4 标定）
        self.record_spend(float(cost) * TOKEN_SPEND_SCALE)

    def record_spend(self, amount: float) -> None:
        a = float(amount)
        if a <= 0:
            return
        if self._forced_balance is not None:
            self._forced_balance = None  # 真实支出解除强制余额
        self._spend_events.append((self._beat, a))
        self._prune()

    def estimate_storage(self, bytes_: int) -> None:
        self.storage_bytes = max(0, int(bytes_))

    def _reset_income_day(self, now: datetime) -> None:
        day = now.strftime("%Y-%m-%d")
        if self.income_day != day:
            self.income_day = day
            self.income_day_count = 0

    def credit_income(
        self,
        source: str,
        amount: float = 1.0,
        *,
        now: datetime | None = None,
        min_interval_sec: float | None = None,
    ) -> bool:
        """仅白名单源；拒绝讨好源；防刷（间隔+日帽）。"""
        src = str(source or "")
        if src in INCOME_SOURCES_REJECTED or src not in INCOME_SOURCES_WHITELIST:
            return False
        amt = float(amount)
        if amt <= 0:
            return False
        now = now or datetime.now()
        self._reset_income_day(now)
        if self.income_day_count >= INCOME_DAILY_CAP:
            return False
        gap_need = (
            float(min_interval_sec)
            if min_interval_sec is not None
            else INCOME_MIN_INTERVAL_SEC
        )
        if self.last_interaction_credit_at is not None:
            gap = (now - self.last_interaction_credit_at).total_seconds()
            if gap < gap_need:
                return False
        if self._forced_balance is not None:
            self._forced_balance = None
        self.income += amt
        self.income_day_count += 1
        self.last_interaction_credit_at = now
        self._income_events.append((self._beat, amt))
        self._prune()
        return True

    def force_balance(self, value: float) -> None:
        """测试 / 包 14 注入断粮：固定 balance；窗口清空。"""
        self._spend_events.clear()
        self._income_events.clear()
        self._forced_balance = float(value)

    def snapshot(self) -> dict[str, Any]:
        return {
            "compute_seconds": self.compute_seconds,
            "token_budget": self.token_budget,
            "storage_bytes": self.storage_bytes,
            "income": self.income,
            "starving": self.starving,
            "last_interaction_credit_at": (
                self.last_interaction_credit_at.isoformat()
                if self.last_interaction_credit_at
                else None
            ),
            "income_day_count": self.income_day_count,
            "income_day": self.income_day,
            "beat": self._beat,
            "spend_events": list(self._spend_events),
            "income_events": list(self._income_events),
            "forced_balance": self._forced_balance,
        }

    def restore(self, data: dict[str, Any] | None) -> None:
        if not data:
            return
        self.compute_seconds = float(data.get("compute_seconds") or 0.0)
        self.token_budget = float(data.get("token_budget") or 0.0)
        self.storage_bytes = int(data.get("storage_bytes") or 0)
        self.income = float(data.get("income") or 0.0)
        self.starving = bool(data.get("starving") or False)
        raw_at = data.get("last_interaction_credit_at")
        if raw_at:
            try:
                self.last_interaction_credit_at = datetime.fromisoformat(str(raw_at))
            except ValueError:
                self.last_interaction_credit_at = None
        else:
            self.last_interaction_credit_at = None
        self.income_day_count = int(data.get("income_day_count") or 0)
        self.income_day = data.get("income_day")
        self._beat = int(data.get("beat") or 0)
        self._spend_events = deque(
            (int(b), float(a)) for b, a in (data.get("spend_events") or [])
        )
        self._income_events = deque(
            (int(b), float(a)) for b, a in (data.get("income_events") or [])
        )
        fb = data.get("forced_balance")
        self._forced_balance = None if fb is None else float(fb)
        self._prune()

    def description(self) -> str:
        return (
            f"账本：认知约 {self.compute_seconds:.1f}s，"
            f"token 估算 {int(self.token_budget)}，"
            f"库约 {self.storage_bytes} 字节；"
            f"累计收入 {self.income:.0f}，"
            f"窗口余额 {self.balance:.1f}"
            + ("（断粮占位）" if self.starving else "")
        )
