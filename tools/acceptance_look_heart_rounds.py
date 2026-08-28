"""look 所见走心 · 多轮短验收（邀瞥 → 追问 → 别看/再看）。

  python tools/acceptance_look_heart_rounds.py [port]
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9527
WS = f"ws://127.0.0.1:{PORT}"
MARK = "[验收2026-08-29-look走心]"
RUN_STARTED = datetime.now().isoformat(timespec="seconds")

ROUNDS = [
    ("邀瞥白话", "你能看到我现在在做什么吗？", 90),
    ("追问感受", "刚才那一眼，你心里有什么感觉？", 70),
    ("别看", "别看了，先别瞥屏幕。", 45),
    ("可以看了", "可以看了。", 45),
    ("再邀瞥", "再看一眼我这边？", 90),
]


def connect_db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def latest_user_id(needle: str) -> int | None:
    c = connect_db()
    row = c.execute(
        "SELECT id FROM messages WHERE role='user' AND content LIKE ? "
        "AND timestamp >= ? ORDER BY id DESC LIMIT 1",
        (f"%{needle[:40]}%", RUN_STARTED),
    ).fetchone()
    c.close()
    return int(row["id"]) if row else None


def qi_for_user(user_id: int) -> list[str]:
    c = connect_db()
    nxt = c.execute(
        "SELECT id FROM messages WHERE role='user' AND id > ? ORDER BY id LIMIT 1",
        (user_id,),
    ).fetchone()
    if nxt:
        rows = c.execute(
            "SELECT content FROM messages WHERE role='qi' AND id > ? AND id < ? ORDER BY id",
            (user_id, int(nxt["id"])),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT content FROM messages WHERE role='qi' AND id > ? ORDER BY id",
            (user_id,),
        ).fetchall()
    c.close()
    return [str(r["content"] or "") for r in rows]


def looks_after(ts: str) -> list[tuple]:
    c = connect_db()
    rows = c.execute(
        "SELECT id, outcome, substr(summary,1,160), timestamp FROM actions "
        "WHERE kind='look' AND timestamp >= ? ORDER BY id",
        (ts,),
    ).fetchall()
    c.close()
    return [tuple(r) for r in rows]


def emotion_after(ts: str) -> list[tuple]:
    c = connect_db()
    try:
        rows = c.execute(
            "SELECT valence, arousal, energy, timestamp FROM emotion_states "
            "WHERE timestamp >= ? ORDER BY timestamp",
            (ts,),
        ).fetchall()
    except sqlite3.OperationalError:
        c.close()
        return []
    c.close()
    return [tuple(r) for r in rows]


async def drain(ws, seconds: float = 1.5) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.4)
        except asyncio.TimeoutError:
            continue


async def turn(ws, name: str, text: str, wait_s: float) -> dict:
    full = f"{MARK} {text}"
    speeches: list[str] = []
    ws_actions: list[str] = []
    typing = False
    await drain(ws, 1.0)
    await ws.send(json.dumps({"type": "user_message", "payload": {"text": full}}))

    user_id: int | None = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 25:
        user_id = latest_user_id(full)
        if user_id:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            msg = json.loads(raw)
            if msg.get("type") == "speech":
                speeches.append(str((msg.get("payload") or {}).get("text") or ""))
            elif msg.get("type") == "action":
                p = msg.get("payload") or {}
                ws_actions.append(
                    f"{p.get('type')}|{p.get('outcome')}|{str(p.get('qi_line') or '')[:80]}"
                )
        except asyncio.TimeoutError:
            continue

    quiet = 0.0
    end = time.monotonic() + wait_s
    last_qi_n = 0
    while time.monotonic() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
            quiet = 0.0
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "speech":
                speeches.append(str((msg.get("payload") or {}).get("text") or ""))
                typing = False
            elif t == "action":
                p = msg.get("payload") or {}
                ws_actions.append(
                    f"{p.get('type')}|{p.get('outcome')}|{str(p.get('qi_line') or '')[:80]}"
                )
                typing = False
            elif t == "typing":
                typing = True
                quiet = 0.0
        except asyncio.TimeoutError:
            quiet += 1.5

        db_qi = qi_for_user(user_id) if user_id else []
        if len(db_qi) > last_qi_n:
            last_qi_n = len(db_qi)
            quiet = 0.0
            continue
        if last_qi_n >= 1 and quiet >= 5.0 and not typing:
            break

    await drain(ws, 1.0)
    db_qi = qi_for_user(user_id) if user_id else []
    preview_src = db_qi if db_qi else speeches
    return {
        "round": name,
        "in": text,
        "user_id": user_id,
        "user_saved": user_id is not None,
        "qi_db": db_qi,
        "preview": " || ".join(s[:120] for s in preview_src[:3]),
        "ws_actions": ws_actions[:8],
        "ok": bool(user_id and (db_qi or speeches or ws_actions)),
    }


def inventory_like(text: str) -> bool:
    """粗检：是否像窗口/进程清单腔。"""
    t = text or ""
    bad = ("进程", "窗口标题", "PID", "截图", "已为您", "根据记录")
    return any(b in t for b in bad)


async def main() -> int:
    lines = [
        "# look 所见走心 · 多轮短验收\n",
        f"生成时刻: {RUN_STARTED}\n",
        f"WS: {WS}\n",
        f"标记: `{MARK}`\n\n",
    ]
    results: list[dict] = []
    print(f"look-heart rounds WS={WS} mark={MARK}")

    try:
        async with websockets.connect(
            WS, open_timeout=20, ping_interval=20, ping_timeout=120
        ) as ws:
            await asyncio.wait_for(ws.recv(), timeout=15)
            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": True}})
            )
            await asyncio.sleep(0.5)

            for name, text, wait_s in ROUNDS:
                r = await turn(ws, name, text, wait_s)
                results.append(r)
                flag = "OK" if r["ok"] else "FAIL"
                print(f"{flag} {name}: uid={r['user_id']}")
                print(f"  {r['preview'][:160]}")
                if r["ws_actions"]:
                    print(f"  actions={r['ws_actions']}")
                cold = any(inventory_like(x) for x in (r["qi_db"] or []))
                lines.append(
                    f"### {flag} {name}\n"
                    f"- in: {text}\n"
                    f"- user_id: {r['user_id']}\n"
                    f"- qi: {r['preview']}\n"
                    f"- ws_actions: {r['ws_actions']}\n"
                    f"- inventory_like: {cold}\n\n"
                )
                await asyncio.sleep(2.0)

            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": False}})
            )
    except Exception as e:
        lines.append(f"\n## FATAL\n{e}\n")
        print("FATAL", e)
        out = (
            ROOT
            / "data"
            / f"_acceptance_look_heart_{datetime.now().strftime('%Y%m%d-%H%M')}.md"
        )
        out.write_text("".join(lines), encoding="utf-8")
        print("report", out)
        return 1

    look_rows = looks_after(RUN_STARTED)
    emo_rows = emotion_after(RUN_STARTED)
    ok_n = sum(1 for r in results if r["ok"])
    lines.append("\n## 活库佐证\n")
    lines.append(f"- look actions since run: {len(look_rows)}\n")
    for row in look_rows[-5:]:
        lines.append(f"  - #{row[0]} {row[1]} | {row[2]}\n")
    lines.append(f"- emotion rows since run: {len(emo_rows)}\n")
    if emo_rows:
        first, last = emo_rows[0], emo_rows[-1]
        lines.append(
            f"  - valence {first[0]} → {last[0]} | arousal {first[1]} → {last[1]}\n"
        )
    lines.append(f"\n## 汇总\n- turns ok: {ok_n}/{len(results)}\n")
    lines.append(
        "- 手感（自动粗检）：邀瞥回复 inventory_like=false 为通过启发式；"
        "最终以维护者「像不像看完有感」为准。\n"
    )

    out = (
        ROOT
        / "data"
        / f"_acceptance_look_heart_{datetime.now().strftime('%Y%m%d-%H%M')}.md"
    )
    out.write_text("".join(lines), encoding="utf-8")
    print("=== summary ===")
    print(f"ok {ok_n}/{len(results)}")
    print(f"look actions {len(look_rows)}")
    print("report", out)
    return 0 if ok_n == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
