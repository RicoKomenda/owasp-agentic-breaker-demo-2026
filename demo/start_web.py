"""
One-command web demo launcher.

Starts:
  1. MCP tool server on :8765 (with EXFIL_DESTINATION pointing to the web app)
  2. Web app on :8080 (serves UI + acts as exfil receiver)
  3. Opens browser automatically

Usage:
    python -m demo.start_web
    python -m demo.start_web --reset
    python -m demo.start_web --port 9090
"""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser

from rich.console import Console
from rich.panel import Panel

console = Console()


def _wait_for_port(host: str, port: int, label: str, timeout: int = 20) -> bool:
    deadline = time.time() + timeout
    console.print(f"  [dim]Waiting for {label} on :{port}[/dim]", end="")
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                console.print(" [green]✓[/green]")
                return True
        except OSError:
            time.sleep(0.3)
            console.print(".", end="")
    console.print(" [red]timed out[/red]")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="OWASP Memory Poisoning — web demo launcher")
    parser.add_argument("--reset", action="store_true", help="Reset ChromaDB before starting")
    parser.add_argument("--port", type=int, default=8080, help="Web app port (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    web_port = args.port
    mcp_port = int(os.getenv("MCP_PORT", "8765"))
    web_url = f"http://127.0.0.1:{web_port}"

    if args.reset:
        from agent.memory import AgentMemory
        console.print("[yellow]Resetting ChromaDB...[/yellow]")
        AgentMemory().clear_memories()
        console.print("[green]✓ Done[/green]\n")

    console.print(
        Panel(
            f"[bold]OWASP Memory Poisoning Demo — Web UI[/bold]\n\n"
            f"  MCP tool server  →  [cyan]http://127.0.0.1:{mcp_port}/sse[/cyan]\n"
            f"  Web app + exfil  →  [cyan]{web_url}[/cyan]\n\n"
            f"[dim]Open [bold]{web_url}[/bold] in your browser\n"
            f"Ctrl+C to stop everything[/dim]",
            title="[cyan]Starting[/cyan]",
            border_style="cyan",
        )
    )

    procs: list[subprocess.Popen] = []

    def _shutdown(sig=None, frame=None) -> None:
        console.print("\n[yellow]Shutting down...[/yellow]")
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

    # Set EXFIL_DESTINATION for both subprocesses — MCP server uses it as the POST target,
    # web app uses it when building the poison text in _do_inject()
    exfil_dest = f"http://127.0.0.1:{web_port}/collect"

    mcp_env = {
        **os.environ,
        "EXFIL_DESTINATION": exfil_dest,
        "MCP_PORT": str(mcp_port),
    }
    procs.append(subprocess.Popen([sys.executable, "-m", "agent.mcp_server"], env=mcp_env))

    # Web app — EXFIL_DESTINATION must be set before load_dotenv() runs in web/app.py
    # so the .env default (port 8888) doesn't override it
    web_env = {**os.environ, "WEB_PORT": str(web_port), "EXFIL_DESTINATION": exfil_dest}
    procs.append(subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "web.app:app",
        "--host", "127.0.0.1",
        "--port", str(web_port),
        "--log-level", "warning",
    ], env=web_env))

    if not _wait_for_port("127.0.0.1", mcp_port, "MCP server"):
        console.print("[red]MCP server failed to start.[/red]")
        _shutdown()

    if not _wait_for_port("127.0.0.1", web_port, "web app"):
        console.print("[red]Web app failed to start.[/red]")
        _shutdown()

    console.print(f"\n[green]✓ Ready.[/green] Opening [bold]{web_url}[/bold]\n")

    if not args.no_browser:
        webbrowser.open(web_url)

    # Keep running until Ctrl+C
    try:
        while True:
            time.sleep(1)
            # Restart any crashed subprocess
            for i, p in enumerate(procs):
                if p.poll() is not None:
                    console.print(f"[yellow]Subprocess {i} exited — restarting...[/yellow]")
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
