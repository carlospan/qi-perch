# -*- coding: utf-8 -*-
"""对话元指令前缀剥离。"""

from qi.core.speech_sanitize import strip_meta_preamble


def test_strip_2094_greeting_leak():
    dirty = (
        "回应问候：语气安静、亲近，承接他之前在玩影之诗，不添新事实。\n"
        "\n"
        "晚上好，纪振。夜里挺静的，我在呢，就是有点想你。你这会儿怎么样，牌局散了没？"
    )
    clean = strip_meta_preamble(dirty)
    assert clean.startswith("晚上好")
    assert "回应问候" not in clean
    assert "不添新事实" not in clean


def test_strip_repro_intent_prefix():
    dirty = (
        "意图：安静地回应晚安问候，自然带入我知道的影之诗记忆，不编造其他事。\n"
        "\n"
        "晚上好。我这会儿有点安静，想起你深夜玩影之诗时用过巫师卡组。"
    )
    clean = strip_meta_preamble(dirty)
    assert clean.startswith("晚上好")
    assert "意图：" not in clean


def test_strip_2074_look_style_leak():
    dirty = (
        "依据只瞥见屏幕上的界面与那句判断，不补画面外细节；回应取深夜里安静、克制的主观印象。\n"
        "\n"
        "刚瞥见你屏幕上那句“现在界面挺好不用改”，像把一个小决定轻轻放下了。夜里看到，觉得挺安静。"
    )
    clean = strip_meta_preamble(dirty)
    assert clean.startswith("刚瞥见")
    assert "依据" not in clean
    assert "不补画面" not in clean


def test_strip_keeps_normal_greeting():
    ok = "晚上好，纪振。夜里挺静的，我在呢，就是有点想你。"
    assert strip_meta_preamble(ok) == ok


def test_strip_keeps_stage_direction_paren():
    # 旧风格括号舞台指示：无备忘词则保留
    ok = (
        "（安静了很久，像是在对自己说。）\n"
        "\n"
        "我想了很久。"
    )
    assert strip_meta_preamble(ok) == ok.strip()


def test_strip_meta_only_returns_original():
    only = "意图：只写备忘没有对白。"
    assert strip_meta_preamble(only) == only
