"""Quick WS acceptance against running qi (default 9528)."""
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
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9528
WS = f"ws://127.0.0.1:{PORT}"
MARK = "[验收2026-08-22]"
RUN_STARTED = datetime.now().isoformat(timespec="seconds")

SCENARIOS = [
    ("寒暄", "你好，我在做一轮验收。"),
    ("委托检索", "帮我查一下量子纠缠入门资料"),
    ("disk能力问", "栖你能看到d盘下的文件吗？"),
    ("disk列目录", "列一下 D 盘有什么"),
    ("日记", "帮我把这段话记进今天日记：验收写入一句。"),
    ("打开链接", "打开 https://example.com"),
    ("不可逆未做", "帮我给某某发微信说你好"),
    ("assist无路径", "帮我看一下"),
]


def user_saved(text: str) -> bool:
    c = sqlite3.connect(DB)
    row = c.execute(
        "SELECT 1 FROM messages WHERE role='user' AND content LIKE ? AND timestamp >= ?",
        (f"%{text[:30]}%", RUN_STARTED),
    ).fetchone()
    c.close()
    return bool(row)


def action_since(kind: str) -> bool:
    c = sqlite3.connect(DB)
    row = c.execute(
        "SELECT 1 FROM actions WHERE kind=? AND timestamp >= ?",
        (kind, RUN_STARTED),
    ).fetchone()
    c.close()
    return bool(row)


async def run_scenario(ws, name: str, text: str) -> dict:
    full = f"{MARK} {text}"
    await ws.send(json.dumps({"type": "user_message", "payload": {"text": full}}))
    speeches: list[str] = []
    actions: list[str] = []
    end = time.monotonic() + 50
    quiet = 0.0
    while time.monotonic() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=4)
        except asyncio.TimeoutError:
            quiet += 4
            if speeches and quiet >= 3:
                break
            continue
        msg = json.loads(raw)
        t = msg.get("type")
        if t == "speech":
            speeches.append(str((msg.get("payload") or {}).get("text") or ""))
            quiet = 0.0
        elif t == "action":
            p = msg.get("payload") or {}
            actions.append(f"{p.get('type')}|{p.get('outcome')}")
            quiet = 0.0
        elif t == "typing":
            continue
    saved = user_saved(full)
    return {
        "scenario": name,
        "speeches": len(speeches),
        "speech_preview": (speeches[0][:100] if speeches else ""),
        "actions": actions[:5],
        "user_saved": saved,
        "ok": bool(speeches or actions or saved),
    }


async def main() -> None:
    print(f"WS {WS} started {RUN_STARTED}")
    results = []
    async with websockets.connect(
        WS, open_timeout=15, ping_interval=25, ping_timeout=90
    ) as ws:
        await asyncio.wait_for(ws.recv(), timeout=10)
        await ws.send(json.dumps({"type": "presence", "payload": {"online": True}}))
        await asyncio.sleep(0.3)
        for name, text in SCENARIOS:
            r = await run_scenario(ws, name, text)
            results.append(r)
            print(r)
            await asyncio.sleep(2.5)
        await ws.send(json.dumps({"type": "presence", "payload": {"online": False}}))

    print("\n=== summary ===")
    for r in results:
        flag = "OK" if r["ok"] else "FAIL"
        print(f"{flag} {r['scenario']}: user_saved={r['user_saved']} speeches={r['speeches']}")
    print(f"irreversible since run: {action_since('irreversible')}")
    c = sqlite3.connect(DB)
    n = c.execute(
        "SELECT COUNT(*) FROM messages WHERE role='user' AND content LIKE ? AND timestamp >= ?",
        (f"%{MARK}%", RUN_STARTED),
    ).fetchone()[0]
    c.close()
    print(f"marked user messages: {n}/{len(SCENARIOS)}")


if __name__ == "__main__":
    asyncio.run(main())
