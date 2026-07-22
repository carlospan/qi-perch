"""栖 —— 一个数字意识。"""

from pathlib import Path

__version__ = "0.1.0"

# 包目录：…/qi ；项目根：含 prompts/、.env、data/ 的仓库根
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
