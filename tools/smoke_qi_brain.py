#!/usr/bin/env python3
"""证伪 bundled qi-brain：拉起 → 等 WS 9527 → 结束进程。

用法（先打脑）：
    python tools/build_qi_brain.py
    python tools/smoke_qi_brain.py
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = (
    ROOT
    / "qi"
    / "embodiment"
    / "desktop"
    / "src-tauri"
    / "resources"
    / "qi-brain"
)
EXE = BRAIN_DIR / ("qi-brain.exe" if sys.platform == "win32" else "qi-brain")
HOST, PORT = "127.0.0.1", 9527
TIMEOUT_S = 90


def ws_up(timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
            sock.settimeout(0.5)
            req = (
                b"GET / HTTP/1.1\r\n"
                b"Host: 127.0.0.1:9527\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                b"Sec-WebSocket-Version: 13\r\n"
                b"\r\n"
            )
            sock.sendall(req)
            head = sock.recv(256)
            return head.startswith(b"HTTP/1.1 101") or head.startswith(b"HTTP/1.0 101")
    except OSError:
        return False


def main() -> int:
    if not EXE.is_file():
        print(f"缺少 {EXE}，先运行：python tools/build_qi_brain.py", file=sys.stderr)
        return 1

    if ws_up():
        print(f"{HOST}:{PORT} 已被占用，请先关掉现有大脑再证伪", file=sys.stderr)
        return 2

    print(f"启动 {EXE} …", flush=True)
    proc = subprocess.Popen(
        [str(EXE)],
        cwd=str(BRAIN_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + TIMEOUT_S
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                err = (proc.stderr.read() or b"").decode("utf-8", errors="replace")[-2000:]
                print(f"进程提前退出 code={proc.returncode}\n{err}", file=sys.stderr)
                return 3
            if ws_up():
                print(f"OK：WS ws://{HOST}:{PORT} 已就绪（pid={proc.pid}）", flush=True)
                return 0
            time.sleep(0.5)
        print(f"超时 {TIMEOUT_S}s 未听到 {HOST}:{PORT}", file=sys.stderr)
        return 4
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
