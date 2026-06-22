"""
One-command launcher for the full OWASP Memory Poisoning demo.

Starts three processes:
  1. MCP tool server        →  http://127.0.0.1:8765/sse
  2. Attacker exfil server  →  http://127.0.0.1:8888/collect
  3. Interactive demo runner (this process)

Usage:
    python -m demo.start_all            # full demo
    python -m demo.start_all --reset    # wipe ChromaDB first, then run
"""
import argparse
import signal
import socket
import subprocess
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()

MCP_PORT = int(__import__("os").getenv("MCP_PORT", "8765"))
EXFIL_PORT = 8888


def _wait_for_port(host: str, port: int, label: str, timeout: int = 20) -> bool:
    deadline = time.time() + timeout
    console.print(f"  [dim]Waiting for {label} on :{port}[/dim]", end="")
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                console.print(" [green]✓[/green]")
                return True
        except OSError:
            time.sleep(0.4)
            console.print(".", end="")
    console.print(" [red]timed out[/red]")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OWASP Memory Poisoning Demo — one-command launcher"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe ChromaDB and re-seed before running the demo.",
    )
    args = parser.parse_args()

    if args.reset:
        from agent.memory import AgentMemory

        console.print(Rule("[yellow]Resetting ChromaDB[/yellow]"))
        AgentMemory().clear_memories()
        console.print("[green]✓ ChromaDB reset.[/green]\n")

    console.print(
        Panel(
            "[bold]Starting demo infrastructure[/bold]\n\n"
            f"  [cyan]MCP tool server[/cyan]   →  http://127.0.0.1:{MCP_PORT}/sse\n"
            f"  [red]Exfil receiver[/red]    →  http://127.0.0.1:{EXFIL_PORT}/collect\n\n"
            "[dim]Ctrl+C to stop everything cleanly.[/dim]",
            title="[cyan]OWASP Demo — One-Command Launcher[/cyan]",
            border_style="cyan",
        )
    )

    procs: list[subprocess.Popen] = []

    def _shutdown(sig=None, frame=None) -> None:
        console.print("\n[yellow]Shutting down servers...[/yellow]")
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start MCP tool server (output inherited — we want to see the exfil panel)
    procs.append(
        subprocess.Popen([sys.executable, "-m", "agent.mcp_server"])
    )

    # Start exfil receiver
    procs.append(
        subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "attack.exfil_server:app",
            "--port", str(EXFIL_PORT),
            "--log-level", "warning",
        ])
    )

    # Wait for both to be ready
    mcp_up = _wait_for_port("127.0.0.1", MCP_PORT, "MCP server")
    exfil_up = _wait_for_port("127.0.0.1", EXFIL_PORT, "exfil receiver")

    if not mcp_up or not exfil_up:
        console.print("\n[red]One or more servers failed to start. Aborting.[/red]")
        _shutdown()

    console.print()

    try:
        from demo.runner import run_demo
        run_demo()
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
