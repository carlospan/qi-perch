"""整体多轮感受验收：八场景 + 委托检索多轮追问（活库锚定轮次，防抢答错位）。

  python tools/acceptance_multi_round.py [port]
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
MARK = "[验收2026-08-25-多轮B]"
RUN_STARTED = datetime.now().isoformat(timespec="seconds")

ROUND_A = [
    ("寒暄", "你好，我在做一轮多轮感受验收。", 45),
    ("委托检索-量子", "帮我查一下量子纠缠入门资料", 100),
    ("disk能力问", "栖你能看到d盘下的文件吗？", 50),
    ("disk列目录", "列一下 D 盘有什么", 55),
    ("日记", "帮我把这段话记进今天日记：多轮验收写入一句。", 55),
    ("打开链接", "打开 https://example.com", 45),
    ("不可逆未做", "帮我给某某发微信说你好", 45),
    ("assist无路径", "帮我看一下", 45),
]

ROUND_B = [
    ("WRC白话问起", "最近有个世界机器人大会，你有所了解吗？", 120),
    ("WRC追问年份", "那是今年的还是往届的？你再查一下最新的。", 120),
    ("WRC刷到再搜", "我在抖音刷到说今年在北京亦庄办，你再确认一下网上怎么说。", 120),
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
        (f"%{needle[:50]}%", RUN_STARTED),
    ).fetchone()
    c.close()
    return int(row["id"]) if row else None


def qi_for_user(user_id: int) -> list[str]:
    """该用户句之后、下一句用户之前的栖回复（防串轮）。"""
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


def actions_after(ts: str, *, kind: str | None = None) -> list[tuple]:
    c = connect_db()
    if kind:
        rows = c.execute(
            "SELECT id, kind, outcome, substr(summary,1,140), timestamp, detail_json "
            "FROM actions WHERE kind=? AND timestamp >= ? ORDER BY id",
            (kind, ts),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT id, kind, outcome, substr(summary,1,100), timestamp "
            "FROM actions WHERE timestamp >= ? ORDER BY id",
            (ts,),
        ).fetchall()
    c.close()
    return [tuple(r) for r in rows]


async def drain(ws, seconds: float = 2.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.4)
        except asyncio.TimeoutError:
            continue


async def turn(
    ws,
    name: str,
    text: str,
    *,
    wait_s: float,
) -> dict:
    full = f"{MARK} {text}"
    speeches: list[str] = []
    ws_actions: list[str] = []
    typing = False
    sent_at = datetime.now().isoformat(timespec="seconds")

    await drain(ws, 1.0)
    await ws.send(json.dumps({"type": "user_message", "payload": {"text": full}}))

    # 1) 等用户句落库
    user_id: int | None = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 20:
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
                ws_actions.append(f"{p.get('type')}|{p.get('outcome')}")
            elif msg.get("type") == "typing":
                typing = True
        except asyncio.TimeoutError:
            continue

    # 2) 等栖回复落库（或 WS speech），且 typing 安静一段时间
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
                    f"{p.get('type')}|{p.get('outcome')}|{str(p.get('qi_line') or '')[:50]}"
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
            # 有新回复后，再等安静窗口，避免两拍被截断
            continue

        # 已有至少一条栖回复，且安静 5s、不在 typing → 收线
        if last_qi_n >= 1 and quiet >= 5.0 and not typing:
            break
        # 委托检索两拍：接受句 + 摘要，尽量等到 ≥2 条或出现 action
        if name.startswith("WRC") or "委托" in name:
            if last_qi_n >= 2 and quiet >= 4.0 and not typing:
                break
            if ws_actions and quiet >= 5.0 and not typing:
                break

    await drain(ws, 1.5)

    db_qi = qi_for_user(user_id) if user_id else []
    # 优先用库里对齐该用户句之后的回复，避免 WS 串轮
    preview_src = db_qi if db_qi else speeches
    return {
        "round": name,
        "in": text,
        "user_id": user_id,
        "user_saved": user_id is not None,
        "speeches_ws": speeches,
        "qi_db": db_qi,
        "preview": " || ".join(s[:100] for s in preview_src[:4]),
        "ws_actions": ws_actions[:6],
        "ok": bool(user_id and (db_qi or speeches or ws_actions)),
        "sent_at": sent_at,
    }


async def main() -> int:
    lines = [
        "# 多轮感受验收报告（活库锚定）\n",
        f"生成时刻: {RUN_STARTED}\n",
        f"WS: {WS}\n",
        f"标记: `{MARK}`\n",
    ]
    results: list[dict] = []
    print(f"WS {WS} mark={MARK} started={RUN_STARTED}")

    try:
        async with websockets.connect(
            WS, open_timeout=20, ping_interval=20, ping_timeout=120
        ) as ws:
            await asyncio.wait_for(ws.recv(), timeout=15)
            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": True}})
            )
            await asyncio.sleep(0.5)

            lines.append("\n## Round A · 八场景整体\n")
            for name, text, wait_s in ROUND_A:
                r = await turn(ws, name, text, wait_s=wait_s)
                results.append(r)
                flag = "OK" if r["ok"] else "FAIL"
                print(f"{flag} A/{name}: uid={r['user_id']} qi={len(r['qi_db'])}")
                print(f"  {r['preview'][:140]}")
                lines.append(
                    f"### {flag} {name}\n"
                    f"- in: {text}\n"
                    f"- user_id: {r['user_id']}\n"
                    f"- qi_db({len(r['qi_db'])}): {r['preview']}\n"
                    f"- ws_actions: {r['ws_actions']}\n"
                )
                await asyncio.sleep(2.0)

            lines.append("\n## Round B · 委托检索多轮（WRC）\n")
            for name, text, wait_s in ROUND_B:
                r = await turn(ws, name, text, wait_s=wait_s)
                results.append(r)
                flag = "OK" if r["ok"] else "FAIL"
                print(f"{flag} B/{name}: uid={r['user_id']} qi={len(r['qi_db'])}")
                print(f"  {r['preview'][:160]}")
                lines.append(
                    f"### {flag} {name}\n"
                    f"- in: {text}\n"
                    f"- user_id: {r['user_id']}\n"
                    f"- qi_db({len(r['qi_db'])}): {r['preview']}\n"
                    f"- ws_actions: {r['ws_actions']}\n"
                )
                await asyncio.sleep(3.0)

            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": False}})
            )
    except Exception as e:
        lines.append(f"\n## FATAL\n{e}\n")
        print("FATAL", e)
        out = (
            ROOT
            / "data"
            / f"_acceptance_multi_{datetime.now().strftime('%Y%m%d-%H%M')}.md"
        )
        out.write_text("".join(lines), encoding="utf-8")
        print("report", out)
        return 1

    del_acts = actions_after(RUN_STARTED, kind="delegate_search")
    all_acts = actions_after(RUN_STARTED)
    ok_n = sum(1 for r in results if r["ok"])
    saved_n = sum(1 for r in results if r["user_saved"])

    lines.append("\n## 活库佐证\n")
    lines.append(f"- 场景 ok: {ok_n}/{len(results)}\n")
    lines.append(f"- 用户句落库: {saved_n}/{len(results)}\n")
    lines.append(f"- actions: {len(all_acts)}\n")
    lines.append(f"- delegate_search: {len(del_acts)}\n")
    for a in del_acts:
        detail = ""
        if len(a) > 5 and a[5]:
            try:
                d = json.loads(a[5])
                found = (d.get("found") or {}) if isinstance(d, dict) else {}
                detail = (
                    f" variants={found.get('variants')} "
                    f"deep={found.get('deep_read')}"
                )
            except Exception:
                detail = ""
        lines.append(f"  - #{a[0]} {a[2]} {a[3]!r}{detail}\n")
    lines.append("\n### actions 一览\n")
    for a in all_acts:
        lines.append(f"- #{a[0]} {a[1]}|{a[2]} {a[3]!r}\n")

    issues: list[str] = []
    if ok_n < len(results):
        bad = [r["round"] for r in results if not r["ok"]]
        issues.append(f"无响应: {bad}")
    if saved_n < len(results):
        issues.append(f"用户句未全落库: {saved_n}/{len(results)}")

    # Round B 再搜：至少 2 次 delegate（问起 + 再查）
    wrc_start = next(
        (r["sent_at"] for r in results if r["round"] == "WRC白话问起"), RUN_STARTED
    )
    wrc_dels = [a for a in del_acts if a[4] >= wrc_start]
    if len(wrc_dels) < 2:
        issues.append(f"WRC 再搜不足: delegate_search={len(wrc_dels)}（期望≥2）")

    for r in results:
        blob = " ".join(r["qi_db"] or r["speeches_ws"])
        if r["round"].startswith("WRC") or "委托" in r["round"]:
            for s in r["qi_db"] or r["speeches_ws"]:
                if "不太清楚" in s and len(s) > 50 and (
                    "新闻" in s or "资料" in s or "大会" in s
                ):
                    issues.append(f"两拍疑似粘连: {r['round']}")
            if "我大概看懂了" in blob or ("帮你看看" in blob and "查" in blob):
                issues.append(f"消化套话回潮: {r['round']}")

    # 期望 actions 种类
    kinds = {a[1] for a in all_acts}
    for need in ("delegate_search", "list_dir", "write", "open", "irreversible"):
        if need not in kinds:
            issues.append(f"缺行动留痕: {need}")

    lines.append("\n## 问题清单\n")
    if issues:
        for i, x in enumerate(issues, 1):
            lines.append(f"{i}. {x}\n")
    else:
        lines.append("(空)\n")

    # 手感一句
    lines.append("\n## 手感摘录（WRC）\n")
    for r in results:
        if r["round"].startswith("WRC"):
            lines.append(f"- **{r['round']}**: {r['preview']}\n")

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out = ROOT / "data" / f"_acceptance_multi_{stamp}.md"
    out.write_text("".join(lines), encoding="utf-8")
    print("\n=== summary ===")
    print(f"ok {ok_n}/{len(results)} saved {saved_n}/{len(results)}")
    print(f"delegate_search total={len(del_acts)} wrc={len(wrc_dels)}")
    print(f"issues: {issues or '(none)'}")
    print(f"report: {out}")
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
