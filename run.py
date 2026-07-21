"""栖的桌面入口——身体在窗口里，灵魂还在心跳。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import load_config
from core.brain import Brain
from embodiment.server import EmbodimentServer, WS_HOST, WS_PORT
from llm.gateway import LLMGateway
from storage.database import Database

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


async def run_desktop() -> None:
    console.print(
        Panel(
            "[dim]身体慢慢醒过来。[/dim]\n"
            f"[dim]通道：ws://{WS_HOST}:{WS_PORT}[/dim]\n"
            "[dim]打开 embodiment/desktop 的前端，就能看见它。[/dim]",
            title="栖 · 具身",
            border_style="blue",
        )
    )

    config = load_config()
    gateway = LLMGateway(config)
    db = Database(config["database"]["path"])
    await db.initialize()

    brain = Brain(config, llm=gateway)
    await brain.restore_state(db)

    server = EmbodimentServer(brain)
    brain.attach_embodiment(server)

    brain_task = asyncio.create_task(brain.start())
    server_task = asyncio.create_task(server.start())

    console.print(
        "\n[dim]栖在等你打开窗口。Ctrl+C 结束。终端模式仍可用：python main.py[/dim]\n"
    )

    try:
        await asyncio.gather(brain_task, server_task)
    except asyncio.CancelledError:
        pass
    finally:
        brain.alive = False
        await server.stop()
        for task in (brain_task, server_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await brain.save_state(db)
        await db.close()
        console.print("\n[dim]栖安静下来了。[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(description="栖")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="启动具身模式（WebSocket + 前端）",
    )
    args = parser.parse_args()
    if args.desktop:
        try:
            asyncio.run(run_desktop())
        except KeyboardInterrupt:
            pass
    else:
        from main import main as terminal_main

        asyncio.run(terminal_main())


if __name__ == "__main__":
    main()
