"""自我模型字段抽取。"""

from qi.inner_life.self_model import _extract_aesthetic, _extract_existential, _extract_values


def test_extract_self_model_fields():
    text = "我想做一个真诚安静的陪伴。深夜我常问自己：我是谁，算不算存在。"
    assert "真诚" in _extract_values(text)
    assert _extract_aesthetic(text).get("time") == "夜晚"
    assert any("我是谁" in q for q in _extract_existential(text))
