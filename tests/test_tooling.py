"""包 18：CI/工具健壮性防回归；Stage3：verify_package / repair_* CLI 契约。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run_tool(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def test_check_spec_traceability_survives_gbk_stdio():
    """PYTHONIOENCODING=gbk 时仍应 exit 0，不因 emoji 抛 UnicodeEncodeError。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "gbk"
    proc = _run_tool(str(REPO / "tools" / "check_spec_traceability.py"), env=env)
    assert proc.returncode == 0, (
        f"rc={proc.returncode}\nstdout={proc.stdout[-800:]}\nstderr={proc.stderr[-800:]}"
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert "UnicodeEncodeError" not in blob


def test_verify_package_cli_requires_test_or_full_and_help():
    """无 --test/--full → exit 2；--help → 0 且列出关键开关。"""
    tool = str(REPO / "tools" / "verify_package.py")
    missing = _run_tool(tool)
    assert missing.returncode == 2
    assert "--test" in (missing.stderr + missing.stdout) or "须指定" in (
        missing.stderr + missing.stdout
    )

    help_proc = _run_tool(tool, "--help")
    assert help_proc.returncode == 0
    assert "--full" in help_proc.stdout
    assert "--test" in help_proc.stdout


def _empty_user_facts_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE user_facts (
                id INTEGER PRIMARY KEY,
                fact_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL,
                stability TEXT,
                source TEXT,
                first_learned TEXT,
                last_confirmed TEXT,
                superseded_by INTEGER,
                emotional_weight REAL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_repair_scripts_dry_run_on_temp_db(tmp_path: Path):
    """repair_* 默认预演：空库 exit 0，且不要求 --apply。

    额外用 PYTHONIOENCODING=cp1252 模拟 GitHub Windows runner，防中文 print 炸编码。
    """
    db = tmp_path / "qi.db"
    _empty_user_facts_db(db)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"

    scripts = [
        "repair_dirty_facts.py",
        "repair_user_facts.py",
        "repair_teaching_fact.py",
    ]
    for name in scripts:
        proc = _run_tool(str(REPO / "tools" / name), "--db", str(db), env=env)
        assert proc.returncode == 0, (
            f"{name} rc={proc.returncode}\n"
            f"stdout={proc.stdout[-600:]}\nstderr={proc.stderr[-600:]}"
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        assert "UnicodeEncodeError" not in blob
        # 预演不得声称已写入；空库常见「未发现」/「OK」
        assert "已 retire" not in blob
        assert "已具体化" not in blob
        assert "未发现" in blob or "[OK]" in blob or "预演" in blob
