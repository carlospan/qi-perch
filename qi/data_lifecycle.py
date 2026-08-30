"""记忆备份 / 清空（设置页 · 不含钥匙与模型）。"""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from qi.paths import ensure_data_root, open_data_folder, resolve_data_root

# 与导出/删除同集；不含 user_secrets.env、models、settings.yaml、backups/
MEMORY_DIR_NAMES: tuple[str, ...] = ("chroma", "checkpoint", "corpus")
MEMORY_FILE_NAMES: tuple[str, ...] = ("qi.db",)
SQLITE_SIDECARS: tuple[str, ...] = ("qi.db-wal", "qi.db-shm", "qi.db-journal")


def list_memory_artifacts(root: Path | None = None) -> list[Path]:
    """当前数据根下存在的记忆产物（文件或目录）。"""
    base = (root or resolve_data_root()).resolve()
    found: list[Path] = []
    for name in MEMORY_FILE_NAMES:
        p = base / name
        if p.is_file():
            found.append(p)
    for name in SQLITE_SIDECARS:
        p = base / name
        if p.is_file():
            found.append(p)
    for name in MEMORY_DIR_NAMES:
        p = base / name
        if p.exists():
            found.append(p)
    return found


def backups_dir(root: Path | None = None) -> Path:
    return (root or resolve_data_root()) / "backups"


def export_memory_backup(
    root: Path | None = None,
    *,
    open_folder: bool = True,
) -> tuple[bool, str, Path | None]:
    """
    打包记忆本体到 data_root/backups/qi-memory-时间戳.zip，并可选打开 backups/。
    返回 (ok, message, zip_path|None)。
    """
    base = ensure_data_root() if root is None else Path(root)
    if root is not None:
        base.mkdir(parents=True, exist_ok=True)
    artifacts = list_memory_artifacts(base)
    # 至少要有实质记忆文件；仅 sidecar 不算
    core = [
        p
        for p in artifacts
        if p.name in MEMORY_FILE_NAMES or p.name in MEMORY_DIR_NAMES
    ]
    if not core:
        return False, "还没有可导出的记忆", None

    out_dir = backups_dir(base)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = out_dir / f"qi-memory-{stamp}.zip"

    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in artifacts:
                if path.is_file():
                    zf.write(path, arcname=path.name)
                elif path.is_dir():
                    for child in path.rglob("*"):
                        if child.is_file():
                            arc = path.name + "/" + child.relative_to(path).as_posix()
                            zf.write(child, arcname=arc)
    except OSError as e:
        return False, f"导出失败：{e}", None

    if open_folder:
        ok, detail = open_data_folder(out_dir)
        if not ok:
            return True, f"已导出到 {zip_path}，但打不开文件夹：{detail}", zip_path

    return True, str(zip_path), zip_path


def wipe_memory_artifacts(root: Path | None = None) -> tuple[bool, str]:
    """删除与导出同集的记忆文件；保留 secrets / models / backups / settings。"""
    base = (root or resolve_data_root()).resolve()
    errors: list[str] = []
    for path in list_memory_artifacts(base):
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        except OSError as e:
            errors.append(f"{path.name}: {e}")
    if errors:
        return False, "部分未能删除：" + "；".join(errors)
    return True, "ok"
