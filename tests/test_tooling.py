"""包 18：CI/工具健壮性防回归。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_check_spec_traceability_survives_gbk_stdio():
    """PYTHONIOENCODING=gbk 时仍应 exit 0，不因 emoji 抛 UnicodeEncodeError。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "gbk"
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_spec_traceability.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    assert proc.returncode == 0, (
        f"rc={proc.returncode}\nstdout={proc.stdout[-800:]}\nstderr={proc.stderr[-800:]}"
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert "UnicodeEncodeError" not in blob
