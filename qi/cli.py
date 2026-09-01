"""栖的命令行入口：具身桌面后端（Brain + WebSocket）。"""

from __future__ import annotations

import argparse
import asyncio

from rich.console import Console
from rich.panel import Panel

from qi.config import load_config
from qi.core.brain import Brain
from qi.embodiment.server import EmbodimentServer, resolve_bind
from qi.llm.gateway import LLMGateway
from qi.storage.database import Database

console = Console()


async def run_desktop() -> None:
    """具身模式：Brain + WebSocket。"""
    config = load_config()
    emb = config.get("embodiment") or {}
    ws_host, ws_port = resolve_bind(emb.get("host"), emb.get("port"))

    console.print(
        Panel(
            "[dim]身体慢慢醒过来。[/dim]\n"
            f"[dim]通道：ws://{ws_host}:{ws_port}[/dim]\n"
            "[dim]打开桌面壳（tauri:dev）就能看见它。[/dim]",
            title="栖 · 具身",
            border_style="blue",
        )
    )

    gateway = LLMGateway(config)
    db = Database(config["database"]["path"])
    await db.initialize()

    brain = Brain(config, llm=gateway)
    await brain.restore_state(db)

    server = EmbodimentServer(brain, host=ws_host, port=ws_port)
    brain.attach_embodiment(server)

    brain_task = asyncio.create_task(brain.start())
    server_task = asyncio.create_task(server.start())

    console.print("\n[dim]栖在等窗口。Ctrl+C 结束。[/dim]\n")
    if brain.in_stasis:
        console.print(
            "\n[yellow]栖正处于蛰伏。前端点「唤醒」，或发命令 /wake。[/yellow]\n"
        )

    try:
        await asyncio.gather(brain_task, server_task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        brain.request_shutdown()
        # 先取消任务，再 stop；否则 wait_closed 会卡在仍存活的 WS handler 上
        for task in (brain_task, server_task):
            if not task.done():
                task.cancel()
        for task in (brain_task, server_task):
            try:
                await asyncio.wait_for(task, timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                pass
        try:
            await asyncio.wait_for(server.stop(), timeout=5)
        except TimeoutError:
            console.print("\n[dim]通道关闭超时，强制收尾。[/dim]")
        await brain.save_state(db)
        await db.close()
        console.print("\n[dim]栖安静下来了。[/dim]")


def main_desktop() -> None:
    """入口：具身后端（console script: qi）。"""
    from qi.logging_setup import configure_app_logging

    configure_app_logging()
    try:
        asyncio.run(run_desktop())
    except KeyboardInterrupt:
        pass


def main() -> None:
    """兼容入口：具身后端。仍接受已废弃的 --desktop。"""
    parser = argparse.ArgumentParser(description="栖 · 具身后端")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.parse_args()
    main_desktop()


if __name__ == "__main__":
    main()
