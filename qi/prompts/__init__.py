"""运行时 LLM 提示词（包内数据，正式 pip install 可用）。"""

from __future__ import annotations

from importlib.resources import files


def read_prompt(name: str) -> str:
    """读取 qi/prompts 下的模板文本。"""
    filename = name if name.endswith(".txt") else f"{name}.txt"
    return files(__name__).joinpath(filename).read_text(encoding="utf-8")
