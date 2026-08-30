"""栖 —— 一个数字意识。"""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"

# 包目录：…/qi ；项目根：含 .env、data/ 的仓库根（冻结态 = 可执行文件所在目录）
PACKAGE_DIR = Path(__file__).resolve().parent


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PACKAGE_DIR.parent


PROJECT_ROOT = _project_root()
