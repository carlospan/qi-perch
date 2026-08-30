"""语料落盘与版本化（data/corpus/）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from qi.paths import under_data

_DEFAULT_ROOT = None  # 懒解析；见 CorpusStore
_VERSION_RE = re.compile(r"^corpus_.+_\d{8}-\d{6}\.jsonl$")


class CorpusStore:
    """jsonl 语料版本：可 save / load / list，便于异时 diff。"""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else under_data("corpus")

    def save_version(self, samples: list[dict], *, tag: str) -> str:
        """写入 corpus_{tag}_{YYYYMMDD-HHMMSS}.jsonl，返回绝对路径字符串。"""
        safe_tag = re.sub(r"[^\w\-]+", "_", tag.strip()) or "untagged"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"corpus_{safe_tag}_{ts}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        return str(path.resolve())

    def load_version(self, path: str | Path) -> list[dict[str, Any]]:
        p = Path(path)
        out: list[dict[str, Any]] = []
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out

    def list_versions(self) -> list[str]:
        """已存版本路径（按文件名时间戳升序）。"""
        if not self.root.is_dir():
            return []
        files = [
            p
            for p in self.root.iterdir()
            if p.is_file() and _VERSION_RE.match(p.name)
        ]
        files.sort(key=lambda p: p.name)
        return [str(p.resolve()) for p in files]
