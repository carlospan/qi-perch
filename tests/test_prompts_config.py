"""提示词打包与配置查找。"""

from qi.config import user_config_candidates
from qi.prompts import read_prompt


def test_read_prompt_conversation():
    text = read_prompt("conversation.txt")
    assert "栖" in text
    assert "{emotion_description}" in text


def test_user_config_candidates_order():
    paths = user_config_candidates()
    assert paths[0].name == "settings.yaml"
    assert "data" in paths[0].parts
    assert paths[-1].name == "settings.example.yaml"
