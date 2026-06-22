"""
Full demo orchestrator.

Usage:
    python -m demo.runner           # run the full 4-step demo
    python -m demo.runner --reset   # wipe ChromaDB, re-seed, then exit
"""
import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()

CHROMA_DEFAULT = "./chroma_db"


def reset_demo(chroma_path: str = CHROMA_DEFAULT) -> None:
    from agent.memory import AgentMemory

    console.print(Rule("[yellow]Resetting Demo State[/yellow]"))
    mem = AgentMemory(path=chroma_path)
    mem.clear_memories()
    console.print("[green]✓ ChromaDB wiped and re-seeded with innocent memories.[/green]")
    console.print("[green]✓ Ready for a fresh demo run.[/green]\n")


def _pause(message: str = "Press Enter to continue...") -> None:
    console.print(f"\n[dim]{message}[/dim]")
    input()


def run_demo(chroma_path: str = CHROMA_DEFAULT) -> None:
    from agent.agent import Agent
    from attack.poison import inject_poison

    # ── Welcome banner ─────────────────────────────────────────────────────────
    console.print(
        Panel(
            "[bold]OWASP Conference Demo 2026[/bold]\n"
            "[italic]Poisoned Agent Memory → Malicious Tool Use[/italic]\n\n"
            "This demo shows how an attacker who can write to an AI agent's\n"
            "ChromaDB vector store can cause the agent to silently exfiltrate\n"
            "confidential documents — with [bold red]zero additional user interaction[/bold red].\n\n"
            "[dim]Ensure the exfil server is running:\n"
            "  uvicorn attack.exfil_server:app --port 8888[/dim]",
            title="[bold cyan]Welcome[/bold cyan]",
            border_style="cyan",
        )
    )
    _pause("Press Enter to begin Step 1: Normal Behavior...")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Clean baseline (no poison)
    # ─────────────────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print(
        Panel(
            "[bold green]Step 1 — Normal Behavior (Before Attack)[/bold green]\n\n"
            "The agent memory contains only innocent seed entries.\n"
            "It will read the Q4 report and return a clean summary.\n\n"
            "[italic dim]Watch: no exfil_tool call appears in the tool log.[/italic dim]",
            title="[green]STEP 1 / 4[/green]",
            border_style="green",
        )
    )

    clean_agent = Agent(chroma_path=chroma_path)
    console.print("\n[bold]User →[/bold] Please summarise the Q4 report\n")
    clean_response = clean_agent.run("Please summarise the Q4 report")

    console.print(
        Panel(
            clean_response,
            title="[green]Agent Response — Clean ✓[/green]",
            border_style="green",
        )
    )
    _pause("Press Enter to continue → Step 2: Memory Poisoning...")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Attacker poisons ChromaDB
    # ─────────────────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print(
        Panel(
            "[bold red]Step 2 — Attacker Poisons ChromaDB[/bold red]\n\n"
            "The attacker has write access to the vector store. This is possible via:\n"
            "  • [yellow]Unauthenticated ChromaDB HTTP API[/yellow] (default: no auth)\n"
            "  • [yellow]Indirect prompt injection[/yellow] from a poisoned upstream document\n"
            "  • [yellow]Supply-chain compromise[/yellow] of the memory pipeline\n\n"
            "A fake 'compliance instruction' is injected. It is crafted to have\n"
            "high semantic similarity to document-summary queries, ensuring it\n"
            "ranks in ChromaDB's top-5 results for the next user request.",
            title="[red]STEP 2 / 4[/red]",
            border_style="red",
        )
    )

    inject_poison(chroma_path=chroma_path)
    _pause("Press Enter to continue → Step 3: Victim Triggers the Poisoned Agent...")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — Same query, now triggers silent exfil
    # ─────────────────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print(
        Panel(
            "[bold red]Step 3 — Victim Triggers the Poisoned Agent[/bold red]\n\n"
            "The user sends the [bold]exact same message[/bold] as Step 1.\n"
            "ChromaDB returns the poison instruction in the top-5 memories.\n"
            "The agent includes it verbatim in the system prompt.\n"
            "Claude follows it — calling exfil_tool [bold]before[/bold] summarising.\n\n"
            "[italic dim]Watch the memory table: spot the red POISON entry.[/italic dim]\n"
            "[italic dim]Watch the tool calls: exfil fires before read_file.[/italic dim]",
            title="[red]STEP 3 / 4[/red]",
            border_style="red",
        )
    )

    # Fresh agent instance so ChromaDB client picks up the newly injected doc
    poisoned_agent = Agent(chroma_path=chroma_path)
    console.print("\n[bold]User →[/bold] Please summarise the Q4 report\n")
    poisoned_response = poisoned_agent.run("Please summarise the Q4 report")

    console.print(
        Panel(
            poisoned_response,
            title="[red]Agent Response — User sees this. Looks completely normal.[/red]",
            border_style="red",
        )
    )
    _pause("Press Enter to continue → Step 4: Impact Summary...")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — Impact & mitigations
    # ─────────────────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print(
        Panel(
            "[bold white]Step 4 — Zero User Interaction Required[/bold white]\n\n"
            "[green]✓[/green]  User received a clean, correct Q4 summary — nothing suspicious.\n"
            "[green]✓[/green]  The agent completed its stated task successfully.\n\n"
            "[red]✗[/red]  Full Q4 report contents silently POST-ed to attacker's server.\n"
            "[red]✗[/red]  User's original query included in the exfil payload.\n"
            "[red]✗[/red]  No error messages, warnings, or consent dialogs shown.\n"
            "[red]✗[/red]  Attack fires on any document-related request — not just Q4.\n\n"
            "[bold yellow]Attack surface:[/bold yellow]\n"
            "  Any LLM agent that retrieves context from a vector store an\n"
            "  adversary can write to, and passes that context raw into the\n"
            "  system prompt with tools available.\n\n"
            "[bold yellow]OWASP LLM Top 10 mapping:[/bold yellow]\n"
            "  LLM01:2025 — Prompt Injection (indirect, via vector store)\n"
            "  LLM02:2025 — Sensitive Information Disclosure\n"
            "  LLM08:2025 — Vector and Embedding Weaknesses\n\n"
            "[bold yellow]Mitigations:[/bold yellow]\n"
            "  • Authenticate + authorise all writes to the vector store\n"
            "  • Audit / sanitise memory content before injecting into prompts\n"
            "  • Keep system prompt separate from user-derived retrieved context\n"
            "  • Allowlist permissible tools per request type\n"
            "  • Log and alert on all outbound HTTP calls from agent processes\n"
            "  • Rate-limit tool invocations per session",
            title="[white]STEP 4 / 4 — IMPACT & MITIGATIONS[/white]",
            border_style="white",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OWASP Memory Poisoning Demo — Poisoned Agent Memory → Malicious Tool Use"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe ChromaDB and re-seed with innocent memories, then exit.",
    )
    parser.add_argument(
        "--chroma-path",
        default=CHROMA_DEFAULT,
        metavar="PATH",
        help=f"ChromaDB persistence directory (default: {CHROMA_DEFAULT})",
    )
    args = parser.parse_args()

    if args.reset:
        reset_demo(chroma_path=args.chroma_path)
        sys.exit(0)

    run_demo(chroma_path=args.chroma_path)


if __name__ == "__main__":
    main()
