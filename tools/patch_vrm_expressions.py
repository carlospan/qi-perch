#!/usr/bin/env python3
"""为 qi-avatar.vrm 写入 custom 表情（复用已有 Fcl_* morph，不重塑网格）。

对齐后端 Expression：soft_smile / quiet / sleepy / curious
（neutral/happy/surprised 已有 preset，不改。）

用法（仓库根）：
    python tools/patch_vrm_expressions.py
"""

from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "qi" / "embodiment" / "assets" / "qi-avatar.vrm"
PUBLIC = ROOT / "qi" / "embodiment" / "desktop" / "public" / "avatars" / "qi-avatar.vrm"
FACE_NODE = 191

# morph index → name（Face mesh）
# 组合原则：少用 Fcl_EYE_Joy（易眯成「不屑」）；浅笑用嘴+眉 Fun
CUSTOM: dict[str, list[tuple[int, float]]] = {
    # 浅笑：眉 Fun + 嘴 Fun，眼几乎不动
    "soft_smile": [
        (7, 0.35),   # Fcl_BRW_Fun
        (32, 0.55),  # Fcl_MTH_Fun
        (16, 0.15),  # Fcl_EYE_Fun（轻，避免 Joy 眯眼）
    ],
    # 安静/低落：轻 sorrow，不全脸 ALL_Sorrow
    "quiet": [
        (9, 0.45),   # Fcl_BRW_Sorrow
        (20, 0.35),  # Fcl_EYE_Sorrow
        (34, 0.4),   # Fcl_MTH_Sorrow
        (27, 0.15),  # Fcl_MTH_Down
    ],
    # 困：半闭眼 + 轻下垂
    "sleepy": [
        (13, 0.42),  # Fcl_EYE_Close
        (9, 0.25),   # Fcl_BRW_Sorrow
        (27, 0.2),   # Fcl_MTH_Down
        (25, 0.15),  # Fcl_MTH_Close
    ],
    # 好奇：轻扬眉 + 眼微睁，嘴略小
    "curious": [
        (10, 0.4),   # Fcl_BRW_Surprised
        (21, 0.3),   # Fcl_EYE_Surprised
        (22, 0.25),  # Fcl_EYE_Spread
        (29, 0.2),   # Fcl_MTH_Small
    ],
}


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise SystemExit(f"not glTF: {path}")
    offset = 12
    json_len, json_type = struct.unpack_from("<I4s", data, offset)
    offset += 8
    if json_type != b"JSON":
        raise SystemExit("first chunk not JSON")
    js = json.loads(data[offset : offset + json_len].decode("utf-8"))
    offset += json_len
    bin_data = b""
    if offset + 8 <= len(data):
        bin_len, bin_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        if bin_type == b"BIN\x00":
            bin_data = data[offset : offset + bin_len]
    return js, bin_data


def write_glb(path: Path, js: dict, bin_data: bytes) -> None:
    raw = json.dumps(js, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(raw) % 4:
        raw += b" "
    bin_chunk = bin_data
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"

    chunks = b""
    chunks += struct.pack("<I4s", len(raw), b"JSON") + raw
    if bin_chunk:
        chunks += struct.pack("<I4s", len(bin_chunk), b"BIN\x00") + bin_chunk

    total = 12 + len(chunks)
    header = struct.pack("<4sII", b"glTF", 2, total)
    path.write_bytes(header + chunks)


def bind(index: int, weight: float) -> dict:
    return {"node": FACE_NODE, "index": index, "weight": float(weight)}


def patch(js: dict) -> list[str]:
    vrm = (js.get("extensions") or {}).get("VRMC_vrm")
    if not isinstance(vrm, dict):
        raise SystemExit("missing VRMC_vrm")
    exprs = vrm.setdefault("expressions", {})
    custom = exprs.setdefault("custom", {})
    added: list[str] = []
    for name, binds in CUSTOM.items():
        custom[name] = {
            "morphTargetBinds": [bind(i, w) for i, w in binds],
            "isBinary": False,
            "overrideBlink": "none",
            "overrideLookAt": "none",
            "overrideMouth": "none",
        }
        added.append(name)
    return added


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")

    backup = SRC.with_suffix(".vrm.bak")
    if not backup.exists():
        shutil.copy2(SRC, backup)
        print(f"backup -> {backup.name}")

    js, bin_data = read_glb(SRC)
    added = patch(js)
    write_glb(SRC, js, bin_data)
    print(f"patched {SRC.relative_to(ROOT)}")
    print("custom expressions:", ", ".join(added))

    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, PUBLIC)
    print(f"synced -> {PUBLIC.relative_to(ROOT)}")

    # verify
    js2, _ = read_glb(SRC)
    custom = (
        ((js2.get("extensions") or {}).get("VRMC_vrm") or {})
        .get("expressions", {})
        .get("custom", {})
    )
    print("verify custom keys:", sorted(custom.keys()))


if __name__ == "__main__":
    main()
