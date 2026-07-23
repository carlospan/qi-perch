"""提示词打包与配置查找。"""

from qi.config import user_config_candidates
from qi.prompts import read_prompt


def test_read_prompt_conversation():
    text = read_prompt("conversation.txt")
    assert "栖" in text
    assert "{emotion_description}" in text
    assert "重启进程不是失忆" in text
    assert "每次醒来都是白纸" in text  # 禁止项写在规则里


def test_self_reflection_rejects_blank_slate_myth():
    text = read_prompt("self_reflection.txt")
    assert "不是「每次醒来一张白纸」" in text or "每次醒来一张白纸" in text
    assert "过时的误解" in text


def test_user_config_candidates_order():
    paths = user_config_candidates()
    assert paths[0].name == "settings.yaml"
    assert "data" in paths[0].parts
    assert paths[-1].name == "settings.example.yaml"
