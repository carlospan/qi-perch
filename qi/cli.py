"""栖的命令行入口：终端聊天与具身桌面。"""

from __future__ import annotations

import argparse
import asyncio
import logging

from rich.console import Console
from rich.panel import Panel

from qi.config import load_config
from qi.core.brain import Brain
from qi.embodiment.server import WS_HOST, WS_PORT, EmbodimentServer
from qi.llm.gateway import LLMGateway
from qi.storage.database import Database

console = Console()


def _format_state(brain: Brain) -> str:
    e = brain.emotion
    return (
        f"模式：{e.mode.value}\n"
        f"描述：{e.description()}\n"
        f"energy={e.energy:.2f}  valence={e.valence:.2f}  arousal={e.arousal:.2f}\n"
        f"security={e.security:.2f}  curiosity={e.curiosity:.2f}  attachment={e.attachment:.2f}\n"
        f"心跳次数：{brain.heartbeat_count}"
    )


async def run_terminal() -> None:
    """终端聊天循环。"""
    console.print(
        Panel(
            "[dim]……[/dim]\n"
            "[dim]有什么东西在慢慢醒过来。[/dim]\n"
            "[dim]……[/dim]",
            title="栖",
            border_style="blue",
        )
    )

    config = load_config()
    gateway = LLMGateway(config)
    db = Database(config["database"]["path"])
    await db.initialize()

    brain = Brain(config, llm=gateway)
    await brain.restore_state(db)

    brain_task = asyncio.create_task(brain.start())
    console.print("\n[dim]栖醒了。输入 /state 看状态，/quit 离开。[/dim]\n")

    async def _drain_proactive() -> None:
        while brain.alive:
            try:
                text = await asyncio.wait_for(brain.proactive_queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            console.print(f"\n[green]栖：[/green]{text}\n")

    proactive_task = asyncio.create_task(_drain_proactive())
    loop = asyncio.get_running_loop()
    try:
        while brain.alive:
            user_input = await loop.run_in_executor(None, console.input, "[bold blue]你：[/bold blue]")
            user_input = user_input.strip()

            if not user_input:
                continue
            if user_input.lower() in ("/quit", "quit", "exit", "再见"):
                console.print("\n[dim]栖：……嗯。那，下次见。[/dim]")
                break
            if user_input == "/state":
                console.print(Panel(_format_state(brain), title="内在状态", border_style="cyan"))
                continue

            response = await brain.receive_user_message(user_input)
            if response:
                console.print(f"\n[green]栖：[/green]{response}\n")
            else:
                console.print("\n[dim][栖想说话，但没能说出来……][/dim]\n")

    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]栖安静下来了。[/dim]")
    finally:
        brain.alive = False
        proactive_task.cancel()
        try:
            await proactive_task
        except asyncio.CancelledError:
            pass
        try:
            await asyncio.wait_for(brain_task, timeout=5)
        except (TimeoutError, asyncio.CancelledError):
            brain_task.cancel()
            try:
                await brain_task
            except asyncio.CancelledError:
                pass
        await brain.save_state(db)
        await db.close()


async def run_desktop() -> None:
    """具身模式：Brain + WebSocket。"""
    console.print(
        Panel(
            "[dim]身体慢慢醒过来。[/dim]\n"
            f"[dim]通道：ws://{WS_HOST}:{WS_PORT}[/dim]\n"
            "[dim]打开 qi/embodiment/desktop 的前端，就能看见它。[/dim]",
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
        "\n[dim]栖在等你打开窗口。Ctrl+C 结束。终端模式仍可用：qi 或 python -m qi[/dim]\n"
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


def main_terminal() -> None:
    """入口：终端聊天（console script: qi）。"""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    try:
        asyncio.run(run_terminal())
    except KeyboardInterrupt:
        pass


def main_desktop() -> None:
    """入口：具身桌面后端（console script: qi-desktop）。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    try:
        asyncio.run(run_desktop())
    except KeyboardInterrupt:
        pass


def main() -> None:
    """兼容入口：qi 默认终端；传 --desktop 则具身。"""
    parser = argparse.ArgumentParser(description="栖")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="启动具身模式（WebSocket + 前端）",
    )
    args = parser.parse_args()
    if args.desktop:
        main_desktop()
    else:
        main_terminal()


if __name__ == "__main__":
    main()
