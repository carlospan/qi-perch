"""TTS —— 可选声音。默认 edge-tts。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState


class TTSProvider(ABC):
    @abstractmethod
    async def speak(self, text: str, speed: float = 1.0, pitch: float = 1.0) -> bytes: ...


def emotion_to_voice_params(emotion: EmotionState) -> tuple[float, float]:
    speed = 1.0
    pitch = 1.0
    if emotion.valence > 0.3:
        speed += 0.1 * emotion.valence
        pitch += 0.05 * emotion.valence
    elif emotion.valence < -0.2:
        speed += 0.1 * emotion.valence
        pitch += 0.05 * emotion.valence
    if emotion.arousal > 0.6:
        speed += 0.05
    if emotion.energy < 0.3:
        speed -= 0.05
    return max(0.8, min(1.2, speed)), max(0.9, min(1.1, pitch))


class EdgeTTSProvider(TTSProvider):
    def __init__(self, voice: str = "zh-CN-XiaoyiNeural"):
        self.voice = voice

    async def speak(self, text: str, speed: float = 1.0, pitch: float = 1.0) -> bytes:
        import edge_tts

        rate_str = f"{int((speed - 1) * 100):+d}%"
        pitch_str = f"{int((pitch - 1) * 100):+d}Hz"
        communicate = edge_tts.Communicate(
            text, self.voice, rate=rate_str, pitch=pitch_str
        )
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    async def speak_to_file(
        self, text: str, output_path: str, speed: float = 1.0, pitch: float = 1.0
    ) -> str:
        audio = await self.speak(text, speed, pitch)
        Path(output_path).write_bytes(audio)
        return output_path


def create_tts(config: dict) -> TTSProvider | None:
    voice_cfg = config.get("voice") or {}
    if not voice_cfg.get("enabled", False):
        return None
    provider = voice_cfg.get("provider", "edge-tts")
    if provider == "edge-tts":
        return EdgeTTSProvider(voice=voice_cfg.get("voice_id", "zh-CN-XiaoyiNeural"))
    return None
