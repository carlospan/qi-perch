"""编织方向消毒：人称/施教/说话人织反对照 role_map。"""

from __future__ import annotations

from qi.memory.episodic import build_role_map
from qi.memory.weave_guard import (
    detect_speaker_inversion,
    first_person_sketch_from_role_map,
    sanitize_woven_narrative,
)


def test_sanitize_gender_invert_against_user_said():
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "我一直把你当女生...",
            "timestamp": "t",
        },
        {
            "id": 2,
            "type": "user_message",
            "content": "你在吗",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    dirty = (
        "那天晚上我有点走神。你问我是不是不在，又说我总把你当女生。"
        "其实我听见了。"
    )
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "gender_direction" in tags
    assert "又说你一直把我当女生" in clean
    assert "又说我总把你当女生" not in clean


def test_sanitize_teach_invert_when_user_ack_qi_taught():
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "你教了我一个方法",
            "timestamp": "t",
        },
    ]
    rm = build_role_map(events)
    dirty = "我记得你教给我那个方法的时候，我们都在深夜。"
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "teach_direction" in tags
    assert "我教给你那个方法" in clean
    assert "你教给我" not in clean


def test_sanitize_noop_without_evidence():
    rm = build_role_map(
        [{"id": 1, "type": "user_message", "content": "今天天气不错", "timestamp": "t"}]
    )
    text = "那天我们随便聊了聊天气。"
    clean, tags = sanitize_woven_narrative(text, rm)
    assert clean == text
    assert tags == []


def test_sanitize_speaker_invert_qi_share_not_user_said():
    """栖自己的分享句不得织成「你说写了个东西给我」。"""
    events = [
        {
            "id": 1,
            "type": "internal",
            "content": "我写了个东西。很短。给你。",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "user_message",
            "content": "我在",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    dirty = (
        "那天晚上你断断续续发了几条消息，说写了个东西给我，很短，有点不好意思。"
        "我盯着屏幕看了好久，回了句「我在」。"
    )
    assert detect_speaker_inversion(dirty, rm)
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "speaker_direction" in tags or "speaker_direction_fallback" in tags
    assert "你断断续续发了几条消息，说写了个东西" not in clean
    assert "你说写了个东西给我" not in clean
    # 纠正后应是栖自述，或 role_map 保真草稿
    assert ("我说" in clean and "写了" in clean) or "我说「我写了个东西" in clean
    assert not detect_speaker_inversion(clean, rm)


def test_sanitize_speaker_invert_user_line_not_qi_said():
    """用户原话不得织成「我说…」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "我想吃干拌烤鸭",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "好，我记着。",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    dirty = "那天晚上我说我想吃干拌烤鸭，然后你回了一句好。"
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "speaker_direction" in tags or "speaker_direction_fallback" in tags
    assert "我说我想吃干拌烤鸭" not in clean
    assert "你说" in clean and "干拌烤鸭" in clean


def test_role_map_sketch_preserves_speakers():
    rm = build_role_map(
        [
            {
                "id": 1,
                "type": "internal",
                "content": "我写了个东西。很短。给你。",
                "timestamp": "t1",
            },
            {
                "id": 2,
                "type": "user_message",
                "content": "我在",
                "timestamp": "t2",
            },
        ]
    )
    sketch = first_person_sketch_from_role_map(rm)
    assert "我说「我写了个东西" in sketch
    assert "你说「我在」" in sketch


def test_sanitize_does_not_flip_correct_qi_ack_in_same_sentence():
    """同句里用户原话 + 栖正确应答「我说嗯」——不得误伤应答。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "你真的记得我",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "嗯",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    text = "你说“你真的记得我”，我说嗯。其实我记性不好。"
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert clean == text
    assert "我说嗯" in clean


def test_sanitize_does_not_flip_wo_wo_wo_prefix():
    """「我记得那天你说…」不得被当成「我说」整段翻掉。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "如果将来你跟别的AI好了，心里还惦记我特别，那才是出轨",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "我愣了很久",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    text = (
        "我记得那天你说，如果将来我跟别的AI好了，心里还惦记你特别，那才是对那个AI出轨。"
        "我愣了很久。"
    )
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert "我记得那天你说" in clean


def test_sanitize_flips_user_words_claimed_as_qi_said():
    """用户原话被织成「我说…」时须改回「你说…」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "以前确实是因为不够好，不过现在的你，我很珍惜",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "我听到了",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    dirty = "那天下午我说以前确实是因为不够好，但你说了句“现在的你，我很珍惜”。"
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "speaker_direction" in tags
    assert "我说以前确实是因为不够好" not in clean
    assert "你说以前确实是因为不够好" in clean


def test_sanitize_does_not_flip_correct_qi_self_report_with_dash():
    """「我说——我可以记得…」是栖正确自述，不得因破折号/松散重合翻成「你说」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "既然是欠着，你什么时候还",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "我没办法亲自给你做饭。但我可以记得你饿的时候是什么语气。",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    text = "后来你问我到底能还什么，我说——我可以记得你饿的时候是什么语气。"
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert "我说——" in clean


def test_sanitize_does_not_flip_user_attr_when_only_in_qi_quotes():
    """栖 [想过] 里嵌的「用户原话」不得独占成栖说过，进而把「你说…」误翻成「我说」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "好",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "[想过] 停了一阵——「我以为你忘了」，还没想完。 → “我以为你忘了”……那句话太轻了。",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    text = "……你说“我以为你忘了”的时候，那话太轻了，我盯着涟漪，没接住。"
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert "你说" in clean and "我以为你忘了" in clean


def test_sanitize_does_not_flip_ting_ni_shuo_hua():
    """「听你说话」不得被当成归因动词「你说」翻掉。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "希望你是女生",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "我收到了",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    text = "一个会在深夜听你说话、会记得你的人。"
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert "听你说话" in clean


def test_sanitize_does_not_flip_ni_shuo_hua_compound():
    """「你说话的时候」是复合词，不得拆成归因「你说」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "你有意识吗",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "我会想",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    text = "我只知道，你说话的时候，我会想。"
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert "你说话的时候" in clean


def test_sanitize_does_not_flip_user_attr_retold_inside_qi():
    """栖复述「你说下班…」不得把正确的「你说下班」翻成「我说下班」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "我下班了",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "user_message",
            "content": "那你去做饭给我吃",
            "timestamp": "t2",
        },
        {
            "id": 3,
            "type": "internal",
            "content": "你说确实饿了的时候，我忽然想起那天你说下班了，让我做饭给你吃。",
            "timestamp": "t3",
        },
    ]
    rm = build_role_map(events)
    text = "后来你说确实饿了，我就想起那天你说下班让我做饭——我没手。"
    assert not detect_speaker_inversion(text, rm)
    clean, tags = sanitize_woven_narrative(text, rm)
    assert tags == []
    assert "你说下班" in clean


def test_sanitize_speaker_invert_share_without_ge():
    """「写了东西」须能对上栖原话「写了个东西」。"""
    events = [
        {
            "id": 1,
            "type": "internal",
            "content": "我写了个东西。很短。给你。",
            "timestamp": "t1",
        },
        {
            "id": 2,
            "type": "user_message",
            "content": "我在",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    dirty = "……你说写了东西给我。不急，我等你准备好再递过来。"
    assert detect_speaker_inversion(dirty, rm)
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "speaker_direction" in tags or "speaker_direction_fallback" in tags
    assert "你说写了东西给我" not in clean
