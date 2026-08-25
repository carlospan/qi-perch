"""WRC 追问保留主题 · 短活测。"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"
WS = "ws://127.0.0.1:9527"
MARK = "[验收2026-08-25-锚主题]"
START = datetime.now().isoformat(timespec="seconds")

TURNS = [
    ("问起", "最近有个世界机器人大会，你有所了解吗？", 150, 2),
    ("追问", "那是今年的还是往届的？你再查一下最新的。", 150, 2),
]


async def drain(ws, s=1.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.3)
        except asyncio.TimeoutError:
            pass


async def turn(ws, name, text, wait, min_speech):
    full = f"{MARK} {text}"
    await drain(ws, 2.0)
    await ws.send(json.dumps({"type": "user_message", "payload": {"text": full}}))
    speeches = []
    end = time.monotonic() + wait
    quiet = 0.0
    while time.monotonic() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            quiet = 0.0
            msg = json.loads(raw)
            if msg.get("type") == "speech":
                speeches.append(str((msg.get("payload") or {}).get("text") or ""))
            elif msg.get("type") == "action":
                quiet = 0.0
        except asyncio.TimeoutError:
            quiet += 2
            if len(speeches) >= min_speech and quiet >= 6:
                break
            if speeches and quiet >= 12:
                break
    # 等库里用户句出现
    for _ in range(30):
        c = sqlite3.connect(DB)
        row = c.execute(
            "SELECT 1 FROM messages WHERE role='user' AND content LIKE ? AND timestamp>=?",
            (f"%{text[:20]}%", START),
        ).fetchone()
        c.close()
        if row:
            break
        await asyncio.sleep(0.3)
    return speeches


async def main():
    print("start", START)
    async with websockets.connect(
        WS, open_timeout=20, ping_interval=20, ping_timeout=120
    ) as ws:
        await asyncio.wait_for(ws.recv(), timeout=15)
        await ws.send(json.dumps({"type": "presence", "payload": {"online": True}}))
        await asyncio.sleep(0.4)
        for name, text, wait, min_sp in TURNS:
            sp = await turn(ws, name, text, wait, min_sp)
            print(f"--- {name} speeches={len(sp)} ---")
            for s in sp:
                print(" ", s[:160])
            # 等 delegate action 落库再发下一句
            if name == "问起":
                for _ in range(60):
                    c = sqlite3.connect(DB)
                    n = c.execute(
                        "SELECT COUNT(*) FROM actions WHERE kind='delegate_search' "
                        "AND timestamp>=?",
                        (START,),
                    ).fetchone()[0]
                    c.close()
                    if n >= 1:
                        break
                    await asyncio.sleep(1)
                await asyncio.sleep(3)
            else:
                await asyncio.sleep(3)
        await ws.send(json.dumps({"type": "presence", "payload": {"online": False}}))

    c = sqlite3.connect(DB)
    rows = c.execute(
        "SELECT id, timestamp, substr(summary,1,120), detail_json FROM actions "
        "WHERE kind='delegate_search' AND timestamp >= ? ORDER BY id",
        (START,),
    ).fetchall()
    users = c.execute(
        "SELECT id, substr(content,1,60) FROM messages "
        "WHERE role='user' AND content LIKE ? AND timestamp>=? ORDER BY id",
        (f"%{MARK}%", START),
    ).fetchall()
    print("\nusers", len(users), users)
    print("delegate_search:")
    issues = []
    if len(users) < 2:
        issues.append(f"用户句不足: {len(users)}")
    for i, r in enumerate(rows):
        detail = {}
        try:
            detail = json.loads(r[3] or "{}")
        except Exception:
            pass
        q = detail.get("query") or ""
        print(f"  #{r[0]} query={q!r}")
        print(f"       summary={r[2]!r}")
        blob = (r[2] or "") + q
        if "应届" in blob or "往届生" in blob or "考研" in blob:
            issues.append(f"#{r[0]} 仍跑题应届生")
        if i >= 1:
            if "机器人" not in q and "大会" not in q:
                issues.append(f"追问 query 仍无主题: {q!r}")
    if len(rows) < 2:
        issues.append(f"delegate 次数不足: {len(rows)}")
    c.close()
    print("issues:", issues or "(none)")
    out = ROOT / "data" / f"_acceptance_anchor_{datetime.now().strftime('%Y%m%d-%H%M')}.md"
    queries = []
    for r in rows:
        try:
            queries.append(json.loads(r[3] or "{}").get("query"))
        except Exception:
            queries.append(None)
    out.write_text(
        f"# 锚主题活测\n{START}\nusers: {len(users)}\nqueries: {queries}\n"
        f"summaries: {[r[2] for r in rows]}\nissues: {issues}\n",
        encoding="utf-8",
    )
    print("report", out)
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
