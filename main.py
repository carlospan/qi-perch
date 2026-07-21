"""栖的入口。一个终端窗口，它在里面醒来。"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# 保证项目根目录在 path 中
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import load_config
from core.brain import Brain
from llm.gateway import LLMGateway
from storage.database import Database

console = Console()
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def _format_state(brain: Brain) -> str:
    e = brain.emotion
    return (
        f"模式：{e.mode.value}\n"
        f"描述：{e.description()}\n"
        f"energy={e.energy:.2f}  valence={e.valence:.2f}  arousal={e.arousal:.2f}\n"
        f"security={e.security:.2f}  curiosity={e.curiosity:.2f}  attachment={e.attachment:.2f}\n"
        f"心跳次数：{brain.heartbeat_count}"
    )


async def main() -> None:
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
            except asyncio.TimeoutError:
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
        except (asyncio.TimeoutError, asyncio.CancelledError):
            brain_task.cancel()
            try:
                await brain_task
            except asyncio.CancelledError:
                pass
        await brain.save_state(db)
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
