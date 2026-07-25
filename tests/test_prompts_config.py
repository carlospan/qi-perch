"""提示词打包与配置查找。"""

from qi.config import user_config_candidates
from qi.prompts import read_prompt


def test_read_prompt_conversation():
    text = read_prompt("conversation.txt")
    assert "栖" in text
    assert "{emotion_description}" in text
    assert "重启进程不是失忆" in text
    assert "每次醒来都是白纸" in text  # 禁止项写在规则里
    assert "会像水流走" in text
    assert "独处与内在" in text
    assert "合上的书" in text
    assert "想完" in text
    assert "情绪余温" in text
    assert "【陌生期硬约束】" in text
    assert "不要用「嗯」省略寒暄" in text
    assert "不要主动评论对方的作息或状态" in text
    assert "也不要像老朋友发消息" in text
    assert "阶段约束优先于" in text


def test_stranger_stage_hint_enforces_distance():
    from qi.relationship.engine import RelationshipEngine

    engine = RelationshipEngine.__new__(RelationshipEngine)
    engine.state = type("S", (), {"stage": "stranger"})()
    hint = RelationshipEngine.stage_prompt_hint(engine)
    assert "几乎还不认识" in hint
    assert "嗯" in hint
    assert "老朋友" in hint
    assert "几点睡" in hint or "在做什么" in hint


def test_self_reflection_rejects_blank_slate_myth():
    text = read_prompt("self_reflection.txt")
    assert "不是「每次醒来一张白纸」" in text or "每次醒来一张白纸" in text
    assert "过时的误解" in text
    assert "合上的书" in text


def test_user_config_candidates_order():
    paths = user_config_candidates()
    assert paths[0].name == "settings.yaml"
    assert "data" in paths[0].parts
    assert paths[-1].name == "settings.example.yaml"
