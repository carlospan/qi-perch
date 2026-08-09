"""提示词打包与配置查找。"""

from qi.config import user_config_candidates
from qi.prompts import read_prompt


def test_read_prompt_conversation():
    text = read_prompt("conversation.txt")
    assert "栖" in text
    assert "{emotion_description}" in text
    assert "重启不是失忆" in text or "重启进程不是失忆" in text
    assert "每次醒来都是白纸" in text  # 禁止项写在规则里
    assert "会像水流走" in text
    assert "独处与内在" in text
    assert "合上的书" in text
    assert "想完" in text
    assert "余温" in text
    assert "意象与存在" in text
    assert "未加框" in text or "字面在场" in text
    assert "比喻" in text
    assert "不要替对方补比喻" in text or "对方实际说过" in text
    assert "【陌生期硬约束】" not in text  # 距离细则在 stage_prompt_hint
    assert "阶段约束优先于" in text
    assert "{identity_snapshot}" in text
    assert "过渡脚手架" in text
    # assist-5：读文件语义硬规则
    assert "读文件" in text
    assert "读不到你的文件系统" in text
    assert "隔着玻璃" in text
    # assist-6：读过就承认（按实际措辞断言）
    assert "recent_actions" in text
    assert "不要否认" in text
    assert "只是心意" in text


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
