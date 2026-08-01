"""Prompt 模板占位符契约测试。

防两类静默故障：
1. 债A：模板新增 {placeholder}，format() 忘给值 → 运行时 KeyError，该拍表达失败。
2. 债B：emotion/now 传 None → AttributeError（API 空值防护）。

conversation.txt 走真实 PromptBuilder 端到端验证（最可靠）；
其余模板锁定占位符集合——改模板占位符时这里会红，提醒同步改填充代码。
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest
from qi.core.emotion import EmotionState
from qi.llm.prompt_builder import PromptBuilder
from qi.prompts import read_prompt

_PLACEHOLDER = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")  # 排除 {{}} 转义

# 各模板占位符必须与对应填充代码一致（见评估文档 §三清单）。
EXPECTED: dict[str, set[str]] = {
    "conversation": {
        "intention_act",
        "intention_topic",
        "intention_materials",
        "intention_stance",
        "intention_length",
        "intention_must",
        "emotion_description",
        "energy_level",
        "time_feeling",
        "tone_hint",
        "relationship_stage",
        "relationship_hint",
        "season_hint",
        "scar_hint",
        "user_facts",
        "recent_actions",
        "shared_culture",
        "emotion_residue",
        "self_narrative",
        "inner_notes",
        "body_hint",
    },
    "consciousness_stream": {
        "time",
        "silence_duration",
        "emotion_summary",
        "season_hint",
        "recent_memories",
        "open_loop",
        "pending_thoughts",
        "last_dream",
        "chat_embers",
        "trigger_hint",
    },
    "dream": {
        "episode_fragments",
        "role_map_hint",
        "emotion_color",
        "season_hint",
        "unfinished_thoughts",
    },
    "creation": {"emotion_state", "trigger_thought", "target"},
    "fact_noticing": {"message", "stage", "emotion"},
    "self_reflection": {
        "current_state",
        "recent_experiences",
        "relationship_summary",
        "previous_self_narrative",
        "growth_events",
    },
    "story_weaving": {
        "raw_events_recent",
        "emotions_during_events",
        "relationship_stage",
    },
}


def test_conversation_builds_end_to_end():
    """债A：用最小参数真实 build 一次，任何缺键会当场炸。"""
    builder = PromptBuilder()
    messages = builder.build_conversation_prompt(
        user_message="你好",
        emotion=EmotionState(),
        now=datetime.now(),
    )
    assert messages and messages[0]["role"] == "system"


def test_conversation_requires_emotion_and_now():
    """债B：emotion/now 必填，传 None 应当显式失败。"""
    builder = PromptBuilder()
    with pytest.raises((TypeError, ValueError, AttributeError)):
        builder.build_conversation_prompt(user_message="x", emotion=None, now=None)


@pytest.mark.parametrize("name", list(EXPECTED))
def test_template_placeholder_set_matches(name):
    """债A：模板占位符集合 == EXPECTED；改模板时同步改填充代码并更新此表。"""
    template = read_prompt(f"{name}.txt")
    actual = set(_PLACEHOLDER.findall(template))
    assert actual == EXPECTED[name], (
        f"{name}.txt 占位符漂移：多了 {actual - EXPECTED[name]}，"
        f"少了 {EXPECTED[name] - actual}"
    )
