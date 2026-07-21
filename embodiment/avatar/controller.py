"""情绪 → Avatar 视觉状态。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from embodiment.avatar.states import AvatarState, Effect, Expression, Posture

if TYPE_CHECKING:
    from core.emotion import EmotionState


class AvatarController:
    """把内在状态画到脸上。"""

    def __init__(self):
        self.current_state = AvatarState()
        self._talking = False
        self._thinking = False

    def set_talking(self, is_talking: bool) -> None:
        self._talking = is_talking

    def set_thinking(self, is_thinking: bool) -> None:
        self._thinking = is_thinking

    def map_state(
        self,
        emotion: EmotionState,
        mode: str,
        season: str = "spring",
        now: datetime | None = None,
    ) -> AvatarState:
        now = now or datetime.now()
        state = AvatarState()

        if self._talking:
            state.posture = Posture.TALKING
        elif self._thinking:
            state.posture = Posture.THINKING
        elif mode == "dreaming" or (now.hour < 6 and emotion.energy < 0.3):
            state.posture = Posture.SLEEPING
        elif emotion.valence > 0.5 and emotion.arousal > 0.4:
            state.posture = Posture.HAPPY
        else:
            state.posture = Posture.IDLE

        if emotion.energy < 0.3:
            state.expression = Expression.SLEEPY
        elif emotion.arousal > 0.7:
            state.expression = Expression.SURPRISED
        elif emotion.curiosity > 0.7:
            state.expression = Expression.CURIOUS
        elif emotion.valence > 0.5:
            state.expression = Expression.HAPPY
        elif emotion.valence > 0.2:
            state.expression = Expression.SOFT_SMILE
        elif emotion.valence < -0.2:
            state.expression = Expression.QUIET
        else:
            state.expression = Expression.NEUTRAL

        if mode == "dreaming":
            state.effect = Effect.DREAM_BUBBLES
        elif self._thinking and emotion.curiosity > 0.6:
            state.effect = Effect.THINKING_SPARKLES
        elif season == "autumn":
            state.effect = Effect.SEASON_LEAVES
        elif season == "winter":
            state.effect = Effect.SNOW
        else:
            state.effect = Effect.NONE

        self.current_state = state
        return state
