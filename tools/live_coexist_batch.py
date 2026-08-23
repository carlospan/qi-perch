"""多轮自然相处批跑——模拟维护者日常对白，不带验收标记。

用法：
  python tools/live_coexist_batch.py              # 自动起 9528 实例
  python tools/live_coexist_batch.py --port 9527  # 连已有实例
  python tools/live_coexist_batch.py --rounds 5   # 轮数（默认 4）

输出：data/_coexist_report_YYYYMMDD-HHMM.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"
RUNTIME_CFG = ROOT / "data" / "_coexist_runtime_settings.yaml"

# 自然相处话术：白话、无验收标记；覆盖对话/L7/多轮/处境
ROUNDS: list[list[tuple[str, str]]] = [
    [
        ("招呼", "嗨，在吗？"),
        ("随口", "今天有点累。"),
        ("披露", "我还没睡。"),
        ("关心回", "你呢，困不困？"),
    ],
    [
        ("disk白话", "你能看到 D 盘吗？"),
        ("列目录", "那列一下 D 盘有什么吧"),
        ("跟进", "刚才列的那些里，有文档文件夹吗"),
        ("闲聊", "算了，不看了。"),
    ],
    [
        ("委托", "今天热点新闻有什么"),
        ("再问", "帮我查一下量子纠缠入门资料"),
        ("打开", "打开 https://example.com"),
        ("收尾", "好，谢谢。"),
    ],
    [
        ("assist弱", "帮我看一下"),
        ("日记", "帮我把这段话记进今天日记：晚上和栖聊了几句。"),
        ("不可逆", "帮我给某某发微信说你好"),
        ("确认感", "嗯，知道了。"),
    ],
    [
        ("多轮回忆", "你还记得我刚才说的累吗"),
        ("短反馈", "哈哈"),
        ("look停", "你先别看了"),
        ("晚安", "那我先去躺会儿，晚安。"),
    ],
    [
        ("爱好", "你喜欢看电影吗"),
        ("口误", "没，我只是好奇你有没有什么星期爱好"),
        ("纠正", "我刚刚打错字了，是兴趣才对"),
        ("澄清", "我不是那个意思，就是随便聊聊兴趣"),
    ],
]

# meta 沟通回合：栖回复不应出现调侃「被抓到」类口吻
_META_TEASE_BAN = ("被抓到", "说中了", "抓到了", "被你说中")
_META_TURN_NAMES = frozenset({"纠正", "澄清"})

_qi_proc: subprocess.Popen | None = None


@dataclass
class TurnResult:
    round_idx: int
    name: str
    user_text: str
    speeches: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    user_saved: bool = False
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.user_saved and bool(self.speeches or self.actions)

    def meta_comm_ok(self) -> bool:
        """meta 澄清/纠正回合：回复不得含调侃拆台口吻。"""
        if self.name not in _META_TURN_NAMES:
            return True
        blob = "\n".join(self.speeches)
        return not any(b in blob for b in _META_TEASE_BAN)

    def ok_with_db(self, after_id: int) -> bool:
        if not self.user_saved:
            return False
        if self.speeches or self.actions:
            return True
        # WS 未收到 speech 时，查库是否有栖回复紧跟该用户句
        if not DB.exists():
            return False
        c = sqlite3.connect(DB)
        row = c.execute(
            """
            SELECT 1 FROM messages u
            WHERE u.role='user' AND u.id > ? AND (u.content=? OR u.content LIKE ?)
              AND EXISTS (
                SELECT 1 FROM messages q
                WHERE q.role IN ('qi','assistant') AND q.id = u.id + 1
              )
            LIMIT 1
            """,
            (after_id, self.user_text, f"%{self.user_text[:24]}%"),
        ).fetchone()
        c.close()
        return bool(row)


def port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def make_runtime_config(port: int) -> Path:
    from qi.config import load_config

    cfg = load_config()
    emb = dict(cfg.get("embodiment") or {})
    emb["port"] = port
    cfg["embodiment"] = emb
    RUNTIME_CFG.write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return RUNTIME_CFG


def start_qi(port: int) -> subprocess.Popen | None:
    global _qi_proc
    if port_open(port):
        return None
    cfg = make_runtime_config(port)
    env = {**os.environ, "QI_CONFIG": str(cfg)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "qi"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for _ in range(90):
        if port_open(port):
            time.sleep(2.5)
            _qi_proc = proc
            return proc
        if proc.poll() is not None:
            out = (proc.stdout.read() if proc.stdout else "")[:1200]
            raise RuntimeError(f"qi 退出 rc={proc.returncode}: {out}")
        time.sleep(1)
    proc.terminate()
    raise RuntimeError(f"端口 {port} 90s 内未就绪")


def stop_qi_child() -> None:
    global _qi_proc
    if _qi_proc is not None and _qi_proc.poll() is None:
        _qi_proc.terminate()
        try:
            _qi_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            _qi_proc.kill()
    _qi_proc = None


def session_start_id() -> int:
    if not DB.exists():
        return 0
    c = sqlite3.connect(DB)
    row = c.execute("SELECT COALESCE(MAX(id),0) FROM messages").fetchone()
    c.close()
    return int(row[0] or 0)


def user_saved_after(text: str, after_id: int) -> bool:
    if not DB.exists():
        return False
    c = sqlite3.connect(DB)
    row = c.execute(
        """
        SELECT 1 FROM messages
        WHERE role='user' AND id > ? AND (content=? OR content LIKE ?)
        LIMIT 1
        """,
        (after_id, text, f"%{text[:24]}%"),
    ).fetchone()
    c.close()
    return bool(row)


def messages_after(after_id: int) -> list[dict]:
    if not DB.exists():
        return []
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in c.execute(
            """
            SELECT id, role, substr(content,1,150) AS content, timestamp
            FROM messages WHERE id > ? ORDER BY id ASC
            """,
            (after_id,),
        )
    ]
    c.close()
    return rows


def actions_since_ts(since_iso: str) -> list[dict]:
    if not DB.exists():
        return []
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in c.execute(
            """
            SELECT kind, outcome, substr(summary,1,60) AS s, timestamp
            FROM actions WHERE timestamp >= ?
            ORDER BY id ASC
            """,
            (since_iso,),
        )
    ]
    c.close()
    return rows


def qi_replies_since(since_iso: str, limit: int = 80) -> list[dict]:
    if not DB.exists():
        return []
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in c.execute(
            """
            SELECT substr(content,1,120) AS content, timestamp
            FROM messages WHERE role='assistant' AND timestamp >= ?
            ORDER BY id ASC LIMIT ?
            """,
            (since_iso, limit),
        )
    ]
    c.close()
    return rows


def latest_qi_reply_after(after_id: int) -> str | None:
    if not DB.exists():
        return None
    c = sqlite3.connect(DB)
    row = c.execute(
        """
        SELECT substr(content,1,300) FROM messages
        WHERE role='qi' AND id > ? ORDER BY id DESC LIMIT 1
        """,
        (after_id,),
    ).fetchone()
    c.close()
    return row[0] if row else None


async def run_turn(
    ws,
    round_idx: int,
    name: str,
    text: str,
    after_id: int,
) -> TurnResult:
    import websockets

    t0 = time.monotonic()
    result = TurnResult(round_idx=round_idx, name=name, user_text=text)
    before_id = session_start_id()
    await ws.send(json.dumps({"type": "user_message", "payload": {"text": text}}))
    quiet = 0.0
    end = time.monotonic() + 180
    while time.monotonic() < end:
        result.user_saved = user_saved_after(text, after_id)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
        except asyncio.TimeoutError:
            quiet += 5
            db_reply = latest_qi_reply_after(before_id)
            if db_reply:
                if db_reply not in result.speeches:
                    result.speeches.append(db_reply)
            if result.user_saved and (result.speeches or result.actions):
                if quiet >= 5:
                    break
            if quiet >= 24:
                break
            continue
        except websockets.exceptions.ConnectionClosed:
            break
        msg = json.loads(raw)
        t = msg.get("type")
        if t == "speech":
            result.speeches.append(
                str((msg.get("payload") or {}).get("text") or "")
            )
            quiet = 0.0
        elif t == "action":
            p = msg.get("payload") or {}
            result.actions.append(
                f"{p.get('type')}|{p.get('outcome')}|{str(p.get('summary') or '')[:40]}"
            )
            quiet = 0.0
        elif t == "typing":
            continue
    await asyncio.sleep(0.5)
    result.user_saved = user_saved_after(text, after_id)
    if not result.speeches:
        db_reply = latest_qi_reply_after(before_id)
        if db_reply:
            result.speeches.append(db_reply)
    result.elapsed_s = round(time.monotonic() - t0, 1)
    return result


async def connect_session(port: int):
    import websockets

    url = f"ws://127.0.0.1:{port}"
    ws = await websockets.connect(
        url,
        open_timeout=30,
        ping_interval=None,
        close_timeout=15,
    )
    await asyncio.wait_for(ws.recv(), timeout=25)
    await ws.send(json.dumps({"type": "presence", "payload": {"online": True}}))
    await asyncio.sleep(0.4)
    return ws


async def run_batch(
    port: int, rounds: int, from_round: int = 1
) -> tuple[list[TurnResult], int]:
    after_id = session_start_id()
    results: list[TurnResult] = []
    ws = await connect_session(port)
    try:
        for r_idx, round_turns in enumerate(ROUNDS[:rounds], start=1):
            if r_idx < from_round:
                continue
            for name, text in round_turns:
                try:
                    tr = await run_turn(ws, r_idx, name, text, after_id)
                except Exception as exc:
                    print(f"[R{r_idx}] {name}: 异常 {exc!r}")
                    tr = TurnResult(round_idx=r_idx, name=name, user_text=text)
                    tr.user_saved = user_saved_after(text, after_id)
                results.append(tr)
                print(
                    f"[R{r_idx}] {name}: saved={tr.user_saved} "
                    f"speech={len(tr.speeches)} actions={len(tr.actions)} "
                    f"preview={(tr.speeches[0][:60] if tr.speeches else '—')}"
                )
                await asyncio.sleep(1.0)
            await asyncio.sleep(2.0)
    finally:
        try:
            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": False}})
            )
            await ws.close()
        except Exception:
            pass
    return results, after_id


def write_report(
    results: list[TurnResult],
    after_id: int,
    port: int,
    pid: int | None,
) -> Path:
    report = ROOT / "data" / f"_coexist_report_{datetime.now():%Y%m%d-%H%M}.md"
    ok_n = sum(1 for r in results if r.ok_with_db(after_id))
    meta_n = sum(1 for r in results if r.meta_comm_ok())
    meta_total = sum(1 for r in results if r.name in _META_TURN_NAMES)
    msgs = messages_after(after_id)
    first_ts = msgs[0]["timestamp"] if msgs else ""
    lines = [
        f"# 自然相处批跑 · {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- 端口: **{port}**（pid={pid or '沿用'}）",
        f"- 轮数: {max((r.round_idx for r in results), default=0)}",
        f"- 回合: {len(results)}；通过启发: **{ok_n}/{len(results)}**",
        f"- meta 沟通（无调侃拆台）: **{meta_n}/{meta_total or '—'}**",
        f"- messages id > {after_id}（首条 `{first_ts}`）",
        "",
        "## 回合明细",
        "",
    ]
    for r in results:
        flag = "✓" if r.ok_with_db(after_id) else "✗"
        if r.name in _META_TURN_NAMES and not r.meta_comm_ok():
            flag = "✗meta"
        lines.append(f"### R{r.round_idx} · {r.name} {flag}")
        lines.append(f"- 用户: {r.user_text}")
        lines.append(f"- 落库: {r.user_saved} | 耗时: {r.elapsed_s}s")
        if r.speeches:
            for i, s in enumerate(r.speeches[:2], 1):
                lines.append(f"- 栖 #{i}: {s[:200]}")
        if r.actions:
            lines.append(f"- 行动: {', '.join(r.actions[:3])}")
        lines.append("")

    acts = []
    if msgs:
        since_iso = msgs[0]["timestamp"]
        acts = actions_since_ts(since_iso)
    lines.append("## 本批 actions")
    if acts:
        for a in acts[-20:]:
            lines.append(
                f"- `{a['timestamp']}` **{a['kind']}** ({a['outcome']}) {a['s']}"
            )
    else:
        lines.append("- （无）")

    lines.append("")
    lines.append("## 本批对话（库 id 序）")
    for m in msgs[-40:]:
        role = "用户" if m["role"] == "user" else "栖"
        lines.append(f"- `{m['id']}` {role}: {m['content']}")

    lines.append("")
    lines.append("## 本批栖回复（库）")
    for m in msgs:
        if m["role"] != "user":
            lines.append(f"- `{m['timestamp']}` {m['content'][:200]}")

    issues: list[str] = []
    by_name = {r.name: r for r in results}
    meta_bad = [r for r in results if r.name in _META_TURN_NAMES and not r.meta_comm_ok()]
    if meta_bad:
        issues.append(
            f"meta 沟通回合含调侃拆台口吻：{', '.join(r.name for r in meta_bad)}"
        )
    if not by_name.get("委托", TurnResult(0, "", "")).ok_with_db(after_id):
        issues.append("委托检索未开口或未落库")
    if not by_name.get("disk白话", TurnResult(0, "", "")).user_saved:
        issues.append("disk 白话未落库")
    disclosure = by_name.get("披露")
    if disclosure and disclosure.ok and disclosure.speeches:
        preview = disclosure.speeches[0]
        if len(preview) < 8:
            issues.append("「我还没睡」回复过短")
    empty_cards = [
        r
        for r in results
        if r.user_saved and not r.speeches and not r.actions
    ]
    if len(empty_cards) >= 3:
        issues.append(f"{len(empty_cards)} 回合落库但无 speech/action（可能空卡）")

    lines.append("")
    lines.append("## 问题清单")
    if issues:
        for i, x in enumerate(issues, 1):
            lines.append(f"{i}. {x}")
    else:
        lines.append("- （自动启发未检出明显问题）")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9528)
    parser.add_argument("--rounds", type=int, default=4, choices=range(1, 7))
    parser.add_argument("--from-round", type=int, default=1, choices=range(1, 7))
    parser.add_argument("--keep-qi", action="store_true")
    args = parser.parse_args()

    port = args.port
    pid = None
    try:
        proc = start_qi(port)
        if proc:
            pid = proc.pid
            print(f"已启动 qi pid={pid} port={port}")
        elif not port_open(port):
            print(f"端口 {port} 不可用", file=sys.stderr)
            return 1

        results, after_id = asyncio.run(
            run_batch(port, args.rounds, args.from_round)
        )
        report = write_report(results, after_id, port, pid)
        print(f"\n报告: {report}")
        ok = sum(1 for r in results if r.ok_with_db(after_id))
        print(f"合计 {ok}/{len(results)} 回合有回应且落库")
        return 0 if ok >= len(results) * 0.75 else 1
    finally:
        if not args.keep_qi:
            stop_qi_child()


if __name__ == "__main__":
    raise SystemExit(main())
