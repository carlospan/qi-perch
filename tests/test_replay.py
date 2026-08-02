"""阶段三·包 11：经验回放语料 + 异时骨架。"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.learning.corpus import CorpusStore
from qi.learning.drift_check import diff_versions, summarize_corpus
from qi.learning.replay import ReplayBuffer
from qi.storage.database import Database


async def _seed_traces(db: Database) -> None:
    now = datetime(2026, 8, 2, 20, 0, 0)
    specs = [
        (1, "idle", 0.1, {"curiosity": 0.2}, "idle"),
        (2, "respond", 1.0, {"curiosity": 0.5}, "responded"),
        (3, "curiosity", 0.85, {"curiosity": 0.9, "world_surprise": 0.2}, "idle"),
        (4, "close_loop", 0.7, {"curiosity": 0.4}, "idle"),
        (5, "proactive:check_in", 0.55, {"curiosity": 0.3}, "proactive"),
        (6, "idle", 0.2, {"curiosity": 0.8, "world_surprise": 0.0}, "idle"),  # curiosity 旁路
        (7, "idle", 0.15, {"curiosity": 0.1, "world_surprise": 1.5}, "idle"),  # surprise 旁路
    ]
    for beat, kind, sal, motive, outcome in specs:
        await db.insert_broadcast_trace(
            beat=beat,
            timestamp=now,
            winner_kind=kind,
            winner_salience=sal,
            candidates=[{"kind": kind, "salience": sal}],
            motive=motive,
            outcome=outcome,
        )


@pytest.mark.asyncio
async def test_collect_candidates_salience_floor_and_order():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await _seed_traces(db)
        buf = ReplayBuffer(db, salience_floor=0.6, limit=50)
        cands = await buf.collect_candidates()
        kinds = [c["winner_kind"] for c in cands]
        # floor 0.6 → respond/curiosity/close_loop；旁路 → beat6 curiosity、beat7 surprise
        # proactive 0.55 < floor 且 motive 不高 → 不入选
        assert "proactive:check_in" not in kinds
        assert "respond" in kinds
        assert "curiosity" in kinds
        assert "close_loop" in kinds
        assert kinds[0] == "respond"  # salience 1.0 最高
        sals = [float(c["winner_salience"]) for c in cands]
        assert sals == sorted(sals, reverse=True)
        await db.close()


@pytest.mark.asyncio
async def test_to_samples_structure():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await _seed_traces(db)
        buf = ReplayBuffer(db, salience_floor=0.6)
        samples = buf.to_samples(await buf.collect_candidates())
        assert samples
        for s in samples:
            assert "winner_kind" in s
            assert "winner_salience" in s
            assert isinstance(s["motive"], dict)
            assert isinstance(s["candidates"], list)
            assert "prompt_hint" in s
            assert s["prompt_hint"].startswith("[winner=")
        await db.close()


@pytest.mark.asyncio
async def test_corpus_versioning_and_diff():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = CorpusStore(root=tmp)
        a = [
            {
                "beat": 1,
                "winner_kind": "curiosity",
                "winner_salience": 0.8,
                "motive": {"curiosity": 0.7},
                "candidates": [],
                "prompt_hint": "a",
            }
        ]
        b = [
            {
                "beat": 1,
                "winner_kind": "curiosity",
                "winner_salience": 0.8,
                "motive": {"curiosity": 0.7},
                "candidates": [],
                "prompt_hint": "a",
            },
            {
                "beat": 2,
                "winner_kind": "close_loop",
                "winner_salience": 0.7,
                "motive": {"curiosity": 0.4},
                "candidates": [],
                "prompt_hint": "b",
            },
        ]
        path_a = store.save_version(a, tag="v1")
        path_b = store.save_version(b, tag="v2")
        versions = store.list_versions()
        assert path_a in versions and path_b in versions
        loaded = store.load_version(path_b)
        assert len(loaded) == 2
        # 内容可 diff
        lines_a = Path(path_a).read_text(encoding="utf-8").strip().splitlines()
        lines_b = Path(path_b).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines_b) > len(lines_a)
        report = diff_versions(path_a, path_b)
        assert report["n_delta"] == 1
        assert "close_loop" in report["kinds_only_in_b"]
        assert "地基" in report["note"] or "语料" in report["note"]


@pytest.mark.asyncio
async def test_run_training_dry_run_no_train(capsys):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await _seed_traces(db)
        buf = ReplayBuffer(db, salience_floor=0.6)
        result = await buf.run_training(dry_run=True)
        assert result["dry_run"] is True
        assert result.get("training") is None
        out = capsys.readouterr().out
        assert "dry_run=True" in out
        assert "不触发训练" in out
        # 非 dry_run 仅占位
        result2 = await buf.run_training(dry_run=False)
        assert result2.get("training") == "not_implemented"
        await db.close()


@pytest.mark.asyncio
async def test_fake_provider_collect_no_llm():
    """拔管：无 LLM，仅 db traces 即可 collect/to_samples。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.insert_broadcast_trace(
            beat=1,
            timestamp=datetime.now(),
            winner_kind="curiosity",
            winner_salience=0.9,
            candidates=[{"kind": "curiosity", "salience": 0.9}],
            motive={"curiosity": 0.85, "world_surprise": 0.3},
            outcome="idle",
        )
        buf = ReplayBuffer(db, salience_floor=0.5)
        cands = await buf.collect_candidates()
        samples = buf.to_samples(cands)
        assert len(samples) == 1
        assert samples[0]["winner_kind"] == "curiosity"
        await db.close()


def test_summarize_corpus_empty():
    assert summarize_corpus([])["n"] == 0


def test_gitignore_has_corpus():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "data/corpus/" in text


def test_run_training_not_in_heartbeat():
    """心跳路径不调用 run_training。"""
    import qi.core.brain as brain_mod

    src = Path(brain_mod.__file__).read_text(encoding="utf-8")
    assert "run_training" not in src
    assert "ReplayBuffer" not in src


def test_drift_check_cli_exists():
    assert (Path("tools") / "replay_drift_check.py").is_file()


def test_drift_check_module_api():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = CorpusStore(root=tmp)
        p1 = store.save_version(
            [{"beat": 1, "winner_kind": "idle", "motive": {}, "candidates": []}],
            tag="a",
        )
        p2 = store.save_version(
            [
                {
                    "beat": 1,
                    "winner_kind": "curiosity",
                    "motive": {"curiosity": 0.9},
                    "candidates": [],
                }
            ],
            tag="b",
        )
        d = diff_versions(p1, p2)
        assert d["summary_a"]["n"] == 1
        assert json.loads(json.dumps(d))  # 可序列化
