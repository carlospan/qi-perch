"""栖 · 全面验收跑批（工程 + WS 对话 + 活库 + 短观察自主拍）。

用法：
  python tools/acceptance_run.py           # 全量
  python tools/acceptance_run.py --skip-pytest

输出：data/_acceptance_report_YYYYMMDD-HHMM.md
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
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"
MARK = "[验收2026-08-22]"
REPORT = ROOT / "data" / f"_acceptance_report_{datetime.now():%Y%m%d-%H%M}.md"
RUNTIME_CFG = ROOT / "data" / "_acceptance_runtime_settings.yaml"

WS_URL = "ws://127.0.0.1:9527"
_qi_proc: subprocess.Popen | None = None
_qi_port = 9527


def log(lines: list[str], msg: str) -> None:
    lines.append(msg)
    print(msg)


def db_snapshot() -> dict:
    if not DB.exists():
        return {"error": "no db"}
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    def q(sql, p=()):
        return [dict(r) for r in c.execute(sql, p)]

    snap = {
        "relationship": q(
            "SELECT stage, trust, season, last_updated FROM relationship ORDER BY id DESC LIMIT 1"
        ),
        "action_count": q("SELECT COUNT(*) AS n FROM actions")[0]["n"],
        "message_count": q("SELECT COUNT(*) AS n FROM messages")[0]["n"],
        "actions_by_kind_7d": q(
            """
            SELECT kind, COUNT(*) n FROM actions
            WHERE timestamp >= datetime('now', '-7 day')
            GROUP BY kind ORDER BY n DESC
            """
        ),
        "last_actions": q(
            "SELECT kind, outcome, substr(summary,1,50) s, timestamp FROM actions ORDER BY id DESC LIMIT 8"
        ),
        "emotion": q(
            "SELECT mode, round(energy,3) e, round(valence,3) v, timestamp FROM emotion_states ORDER BY id DESC LIMIT 1"
        ),
        "delegate_queue": q("SELECT value FROM body_memory WHERE key='user_delegate_queue'"),
        "in_stasis_hint": q("SELECT value FROM body_memory WHERE key='stasis_intents' LIMIT 1"),
    }
    c.close()
    return snap


def db_user_saved(text: str) -> bool:
    if not DB.exists():
        return False
    c = sqlite3.connect(DB)
    row = c.execute(
        "SELECT 1 FROM messages WHERE role='user' AND content LIKE ? LIMIT 1",
        (f"%{text[:40]}%",),
    ).fetchone()
    c.close()
    return row is not None


def db_recent_action(kind: str, since_iso: str) -> bool:
    if not DB.exists():
        return False
    c = sqlite3.connect(DB)
    row = c.execute(
        "SELECT 1 FROM actions WHERE kind=? AND timestamp >= ? LIMIT 1",
        (kind, since_iso),
    ).fetchone()
    c.close()
    return row is not None


def run_pytest(lines: list[str]) -> int:
    basetemp = ROOT / ".pytest_basetemp"
    basetemp.mkdir(exist_ok=True)
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=no",
            f"--basetemp={basetemp}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    tail = (r.stdout or "").strip().splitlines()[-3:]
    log(lines, "## pytest")
    for t in tail:
        log(lines, t)
    log(lines, f"exit_code={r.returncode}")
    return r.returncode


def port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def pid_on_port(port: int) -> int | None:
    if sys.platform == "win32":
        r = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in (r.stdout or "").splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        return int(parts[-1])
                    except ValueError:
                        pass
    return None


def try_kill_port(port: int) -> bool:
    pid = pid_on_port(port)
    if pid is None:
        return True
    for cmd in (
        ["taskkill", "/F", "/PID", str(pid)],
        ["taskkill", "/F", "/T", "/PID", str(pid)],
    ):
        subprocess.run(cmd, capture_output=True)
        time.sleep(1.5)
        if not port_open(port):
            return True
    return not port_open(port)


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


def start_qi_on_port(port: int) -> subprocess.Popen | None:
    global WS_URL, _qi_proc, _qi_port
    if port_open(port):
        WS_URL = f"ws://127.0.0.1:{port}"
        _qi_port = port
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
    for _ in range(60):
        if port_open(port):
            WS_URL = f"ws://127.0.0.1:{port}"
            _qi_port = port
            _qi_proc = proc
            time.sleep(2.0)
            return proc
        if proc.poll() is not None:
            out = (proc.stdout.read() if proc.stdout else "")[:800]
            raise RuntimeError(f"qi 子进程退出 rc={proc.returncode}: {out}")
        time.sleep(1)
    proc.terminate()
    raise RuntimeError(f"qi 在端口 {port} 上 60s 内未监听")


async def ws_handshake_ok(port: int) -> bool:
    import websockets

    url = f"ws://127.0.0.1:{port}"
    try:
        async with websockets.connect(url, open_timeout=8) as ws:
            await asyncio.wait_for(ws.recv(), timeout=8)
        return True
    except Exception:
        return False


async def ensure_fresh_qi(lines: list[str]) -> None:
    """9527 空闲则起新进程；已就绪且能握手则沿用（不杀用户刚起的栖）。"""
    global _qi_proc, WS_URL, _qi_port
    if port_open(9527) and await ws_handshake_ok(9527):
        WS_URL = "ws://127.0.0.1:9527"
        _qi_port = 9527
        _qi_proc = None
        log(lines, "WS 9527 已就绪（沿用当前实例，未杀进程）")
        return
    killed = try_kill_port(9527)
    if killed and not port_open(9527):
        log(lines, "已释放 9527，启动新 `python -m qi`")
        _qi_proc = start_qi_on_port(9527)
        if not await ws_handshake_ok(9527):
            raise RuntimeError("9527 已监听但 WS 握手失败")
        log(lines, f"WS: {WS_URL}（新进程 pid={_qi_proc.pid if _qi_proc else 'n/a'}）")
        return
    if not port_open(9527):
        log(lines, "9527 空闲，启动新 `python -m qi`")
        _qi_proc = start_qi_on_port(9527)
        if not await ws_handshake_ok(9527):
            raise RuntimeError("9527 已监听但 WS 握手失败")
        log(lines, f"WS: {WS_URL}")
        return
    alt = 9528
    log(
        lines,
        f"无法结束 9527（pid={pid_on_port(9527)}），改在 {alt} 启动**当前代码**实例",
    )
    if port_open(alt):
        try_kill_port(alt)
    _qi_proc = start_qi_on_port(alt)
    if not await ws_handshake_ok(alt):
        raise RuntimeError(f"{alt} 已监听但 WS 握手失败")
    log(lines, f"WS: {WS_URL}（验收连此端口）")


def stop_qi_child() -> None:
    global _qi_proc
    if _qi_proc is None:
        return
    _qi_proc.terminate()
    try:
        _qi_proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        _qi_proc.kill()
    _qi_proc = None


async def ws_session(
    scenarios: list[tuple[str, str]], *, run_started: str
) -> list[dict]:
    """scenarios: (name, user_text)"""
    import websockets

    results: list[dict] = []
    async with websockets.connect(
        WS_URL,
        open_timeout=12,
        ping_interval=25,
        ping_timeout=90,
        close_timeout=5,
    ) as ws:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            _ = json.loads(raw)
        except Exception as e:
            return [{"error": f"no initial state: {e}"}]

        await ws.send(
            json.dumps({"type": "presence", "payload": {"online": True}})
        )
        await asyncio.sleep(0.3)

        for name, text in scenarios:
            full = f"{MARK} {text}" if MARK not in text else text
            speeches: list[str] = []
            actions: list[str] = []
            await ws.send(
                json.dumps({"type": "user_message", "payload": {"text": full}})
            )
            quiet_after_speech = 0.0
            deadline = time.monotonic() + 55
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=4)
                except asyncio.TimeoutError:
                    if speeches and quiet_after_speech >= 2.5:
                        break
                    if speeches:
                        quiet_after_speech += 4
                    continue
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "speech":
                    speeches.append(str((msg.get("payload") or {}).get("text") or ""))
                    quiet_after_speech = 0.0
                elif t == "action":
                    p = msg.get("payload") or {}
                    actions.append(
                        f"{p.get('type')}|{p.get('outcome')}|{(p.get('qi_line') or '')[:80]}"
                    )
                    quiet_after_speech = 0.0
                elif t == "typing":
                    continue
                else:
                    continue
                if speeches and quiet_after_speech == 0.0:
                    # 收到内容后再等一小会看有没有后续包
                    await asyncio.sleep(0.3)

            user_ok = db_user_saved(full)
            db_ok = user_ok
            if name == "委托检索":
                db_ok = db_ok or db_recent_action("delegate_search", run_started)
            elif name.startswith("disk"):
                db_ok = db_ok or db_recent_action("list_dir", run_started)
            elif name == "打开链接":
                db_ok = db_ok or db_recent_action("open", run_started)
            elif name == "不可逆未做":
                db_ok = db_ok or db_recent_action("irreversible", run_started)
            results.append(
                {
                    "scenario": name,
                    "in": full,
                    "speeches": speeches,
                    "actions": actions,
                    "user_saved": user_ok,
                    "db_ok": db_ok,
                    "ok": bool(speeches or actions or db_ok),
                }
            )
            await asyncio.sleep(2.5)

        await ws.send(
            json.dumps({"type": "presence", "payload": {"online": False}})
        )
    return results


async def observe_autonomous(seconds: float, lines: list[str]) -> int:
    before = db_snapshot()["action_count"]
    log(lines, f"\n## 自主观察（{seconds}s，presence=online，{WS_URL}）")
    import websockets

    try:
        async with websockets.connect(
            WS_URL,
            open_timeout=12,
            ping_interval=25,
            ping_timeout=90,
        ) as ws:
            await ws.recv()
            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": True}})
            )
            await asyncio.sleep(seconds)
            await ws.send(
                json.dumps({"type": "presence", "payload": {"online": False}})
            )
    except Exception as e:
        log(lines, f"observe failed: {e}")
        return 0
    after = db_snapshot()["action_count"]
    delta = after - before
    log(lines, f"actions 表增量: {delta}（{before} → {after}）")
    return delta


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


async def main_async(*, skip_pytest: bool) -> int:
    lines: list[str] = []
    run_started = datetime.now().isoformat(timespec="seconds")
    log(lines, f"# 栖全面验收报告\n\n生成时刻: {run_started}\n")

    log(lines, "## 启动")
    try:
        await ensure_fresh_qi(lines)
    except Exception as e:
        log(lines, f"启动失败: {e}")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    log(lines, "\n## 活库（跑前）")
    log(lines, json.dumps(db_snapshot(), ensure_ascii=False, indent=2))

    pytest_code = 0
    if skip_pytest:
        log(lines, "\n## pytest\n(skipped)")
    else:
        pytest_code = run_pytest(lines)

    ws_results: list[dict] = []
    if port_open(_qi_port):
        log(lines, f"\n## WebSocket 场景（{WS_URL}）")
        try:
            ws_results = await ws_session(SCENARIOS, run_started=run_started)
            for r in ws_results:
                log(lines, f"\n### {r.get('scenario')}")
                log(lines, f"- 输入: {r.get('in')}")
                log(lines, f"- 开口: {r.get('speeches')}")
                log(lines, f"- 行动卡: {r.get('actions')}")
                log(lines, f"- 用户落库: {r.get('user_saved')}")
                log(lines, f"- 活库佐证: {r.get('db_ok')}")
                log(lines, f"- ok: {r.get('ok')}")
        except Exception as e:
            log(lines, f"WS 场景失败: {e}")
    else:
        log(lines, "WS 不可用，跳过场景")

    delta = 0
    if port_open(_qi_port):
        delta = await observe_autonomous(60, lines)

    log(lines, "\n## 活库（跑后）")
    log(lines, json.dumps(db_snapshot(), ensure_ascii=False, indent=2))

    issues: list[str] = []
    if pytest_code != 0:
        issues.append("P1 pytest 非全绿（见上文 exit_code / 摘要）")
    for r in ws_results:
        if r.get("error"):
            issues.append(f"P0 WS: {r['error']}")
        elif not r.get("ok"):
            issues.append(f"P2 场景无响应: {r.get('scenario')}")
        elif not r.get("user_saved"):
            issues.append(f"P1 用户句未落库: {r.get('scenario')}")
    if not port_open(_qi_port):
        issues.append(f"P0 无法连接 WS {_qi_port}")
    if delta == 0:
        issues.append(
            "P2 60s 在线观察 actions 无增量（可能门槛未触发或 GWS 未胜出）"
        )
    irrev = db_recent_action("irreversible", run_started)
    if not irrev:
        issues.append("P1 本轮未见 irreversible 留痕（发微信场景可能未走新路径）")
    users_marked = 0
    if DB.exists():
        c = sqlite3.connect(DB)
        users_marked = c.execute(
            "SELECT COUNT(*) FROM messages WHERE role='user' AND content LIKE ? AND timestamp >= ?",
            (f"%{MARK}%", run_started),
        ).fetchone()[0]
        c.close()
    if users_marked < len(SCENARIOS):
        issues.append(
            f"P1 带验收标记的用户句仅 {users_marked}/{len(SCENARIOS)} 条落库"
        )
    if _qi_port != 9527:
        issues.append(
            f"P3 9527 仍被旧进程占用；本轮验的是 {_qi_port} 上的新代码实例"
        )

    log(lines, "\n## 问题清单")
    if not issues:
        log(lines, "（未发现阻塞项）")
    else:
        for i, issue in enumerate(issues, 1):
            log(lines, f"{i}. {issue}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    log(lines, f"\n报告已写入: {REPORT}")

    stop_qi_child()
    return pytest_code


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-pytest", action="store_true")
    args = p.parse_args()
    return asyncio.run(main_async(skip_pytest=args.skip_pytest))


if __name__ == "__main__":
    raise SystemExit(main())
