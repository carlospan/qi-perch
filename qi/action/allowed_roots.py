"""世界触达允许根（disk/write 共用；落盘数据根 allowed_roots.json）。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from qi.paths import ensure_data_root, resolve_data_root

logger = logging.getLogger("qi.action.allowed_roots")

FILENAME = "allowed_roots.json"
LEGACY_DEFAULT = Path("D:/")

# 测试可替换；正式路径走 load/save
_override_roots: list[Path] | None = None


def allowed_roots_path(root: Path | None = None) -> Path:
    base = root if root is not None else resolve_data_root()
    return Path(base) / FILENAME


def _d_drive_exists() -> bool:
    try:
        return LEGACY_DEFAULT.exists()
    except OSError:
        return False


def default_roots() -> list[Path]:
    if _d_drive_exists():
        return [LEGACY_DEFAULT.resolve()]
    return []


def _normalize_root_entry(raw: str | Path) -> Path | None:
    text = str(raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    try:
        p = Path(text).expanduser().resolve()
    except OSError:
        return None
    return p


def load_allowed_roots(*, data_root: Path | None = None) -> list[Path]:
    """读取允许根；无文件时用默认（有 D: 则含 D:）。"""
    if _override_roots is not None:
        return list(_override_roots)
    path = allowed_roots_path(data_root)
    if not path.is_file():
        return default_roots()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取 %s 失败，回退默认：%s", path, e)
        return default_roots()
    items = raw.get("roots") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return default_roots()
    out: list[Path] = []
    seen: set[str] = set()
    for item in items:
        p = _normalize_root_entry(item)
        if p is None:
            continue
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def save_allowed_roots(
    roots: list[str | Path],
    *,
    data_root: Path | None = None,
) -> list[Path]:
    """写入允许根；返回规范化后的列表。空列表合法（须去设置再加）。"""
    global _override_roots
    base = data_root if data_root is not None else ensure_data_root()
    path = allowed_roots_path(base)
    cleaned: list[Path] = []
    seen: set[str] = set()
    for item in roots:
        p = _normalize_root_entry(item)
        if p is None:
            continue
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p)
    payload = {"roots": [str(p) for p in cleaned]}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _override_roots = None  # 落盘后清内存覆盖，下次读文件
    return cleaned


def set_roots_override(roots: list[Path] | None) -> None:
    """测试用：强制内存中的允许根；None 取消。"""
    global _override_roots
    _override_roots = list(roots) if roots is not None else None


def allowed_roots() -> list[Path]:
    return load_allowed_roots()


def allowed_root() -> Path | None:
    """兼容旧单根：取列表第一项；空则 None。"""
    roots = allowed_roots()
    return roots[0] if roots else None


def roots_empty() -> bool:
    return not allowed_roots()


def normalize_under_roots(
    raw: str,
    *,
    roots: list[Path] | None = None,
) -> Path | None:
    """路径须落在某一允许根下（含根自身）。"""
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    root_list = roots if roots is not None else allowed_roots()
    if not root_list:
        return None
    if re.fullmatch(r"[Dd]\s*盘", text):
        for r in root_list:
            if str(r).upper().startswith("D:"):
                return r.resolve()
        return None
    try:
        p = Path(text).expanduser()
        if not p.is_absolute():
            # 相对路径：试挂到每个根
            for r in root_list:
                candidate = (r / p).resolve()
                try:
                    candidate.relative_to(r.resolve())
                    return candidate
                except ValueError:
                    continue
            return None
        resolved = p.resolve()
    except OSError:
        return None
    for r in root_list:
        root = r.resolve()
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            if resolved == root:
                return resolved
    return None


def pick_directory_dialog() -> str | None:
    """本机系统文件夹选择器（tkinter）；失败返回 None。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        logger.debug("tkinter 不可用", exc_info=True)
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        chosen = filedialog.askdirectory(mustexist=True)
        root.destroy()
        if not chosen:
            return None
        return str(Path(chosen).resolve())
    except Exception:
        logger.exception("系统选目录失败")
        return None


def snapshot_for_settings() -> dict:
    roots = [str(p) for p in load_allowed_roots()]
    return {
        "roots": roots,
        "empty": len(roots) == 0,
        "default_had_d": _d_drive_exists(),
    }
