import sys
from pathlib import Path
import asyncio

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure 'src' is in sys.path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt

from radar.orchestrator.engine import RadarEngine
from radar.mcp_server.storage.db import (
    init_db,
    get_all_tracked_entities,
    get_latest_briefing
)
from radar.orchestrator.mcp_client import RadarMCPClient
from radar.orchestrator.external_mcp import ExternalMCPBridge
from radar.mcp_server.server import run_server as run_mcp_server
from radar.orchestrator.notifier import send_test_email, is_smtp_configured
from radar.orchestrator.morning import run_morning_cycle
from radar.orchestrator.scheduler import (
    install_daily_schedule,
    remove_daily_schedule,
    query_daily_schedule,
    get_schedule_details,
    schedule_needs_repair,
)

console = Console()

def display_banner():
    console.print(Panel(
        "[bold cyan]📡 Autonomous Market & Tech Intelligence Radar[/bold cyan]\n"
        "[dim]Model Context Protocol (MCP) + Zero-Hallucination Multi-Agent Swarm[/dim]",
        border_style="cyan"
    ))

async def view_history():
    await init_db()
    entities = await get_all_tracked_entities()
    if not entities:
        console.print("[yellow]No entities tracked yet. Run an intelligence scan first![/yellow]")
        return

    table = Table(title="Tracked Technologies & Frameworks in Radar DB", border_style="blue")
    table.add_column("ID", justify="center", style="dim")
    table.add_column("Entity / Project", style="bold cyan")
    table.add_column("Category", style="green")
    table.add_column("Novelty", justify="center")
    table.add_column("Velocity", justify="center")
    table.add_column("Last Verified", style="dim")

    for e in entities[:20]:
        table.add_row(
            str(e["id"]),
            e["entity_name"],
            e["category"],
            str(e["novelty_score"]),
            str(e["velocity_score"]),
            e["last_verified_at"][:19] if e["last_verified_at"] else "N/A"
        )
    console.print(table)

async def view_latest():
    await init_db()
    latest = await get_latest_briefing()
    if not latest:
        console.print("[yellow]No briefings found in database. Run a scan first![/yellow]")
        return
    console.print(Markdown(latest["briefing_markdown"]))

def prompt_human_selection(candidates):
    console.print("\n[bold yellow]🧑‍💻 Human-in-the-Loop Selection Gate[/bold yellow]")
    console.print("The Signal Analyst shortlisted the following candidates. Choose which ones to audit:")
    
    cand_table = Table(title="Candidate Signals for Verification", border_style="yellow")
    cand_table.add_column("#", justify="center", style="bold")
    cand_table.add_column("Entity / Title", style="cyan")
    cand_table.add_column("Category", style="magenta")
    cand_table.add_column("Novelty", justify="center")
    cand_table.add_column("Velocity", justify="center")
    
    for idx, c in enumerate(candidates, start=1):
        cand_table.add_row(
            str(idx),
            c.signal.title[:65],
            c.category,
            f"{c.novelty_score}/10",
            f"{c.velocity_score}/10"
        )
    console.print(cand_table)
    
    user_input = Prompt.ask(
        "\nEnter numbers to approve (comma-separated, e.g. 1,2,3 or 'all' to approve all)",
        default="all"
    )
    if user_input.strip().lower() == "all":
        return candidates
    
    selected = []
    try:
        indices = [int(x.strip()) for x in user_input.split(",") if x.strip().isdigit()]
        for idx in indices:
            if 1 <= idx <= len(candidates):
                selected.append(candidates[idx - 1])
    except Exception:
        return candidates
    return selected if selected else candidates

async def run_pipeline(topic: str, verbose: bool = False, interactive: bool = False):
    display_banner()
    console.print(f"\n[bold green]Initiating Autonomous Intelligence Cycle on:[/bold green] [bold yellow]{topic}[/bold yellow]\n")

    await init_db()
    engine = RadarEngine()

    def on_step_notification(step_name: str, state):
        console.print(f"  [cyan]›[/cyan] {step_name}")

    selection_callback = prompt_human_selection if interactive else None

    state = await engine.run(
        topic=topic,
        on_step=on_step_notification,
        interactive=interactive,
        on_human_selection=selection_callback
    )

    console.print("\n[bold green]Cycle Finished Successfully![/bold green]\n")
    console.print(Markdown(state.briefing_markdown))

    from radar.ui.generator import generate_radar_html_from_state
    latest_html_path = generate_radar_html_from_state(state)
    console.print(f"\n[bold cyan]🎯 Interactive Visual Tech Radar Generated:[/bold cyan]")
    console.print(f"👉 File: [bold underline]{latest_html_path}[/bold underline]")
    console.print(f"👉 Or view live dashboard by running: [bold green]radar[/bold green]\n")

    if verbose:
        console.print("\n[dim]Detailed Verification Audit Trail:[/dim]")
        for item in state.verified_items:
            console.print(f"  [green]✓[/green] [bold]{item.candidate.signal.title[:50]}[/bold]")
            console.print(f"    URL: {item.candidate.signal.url}")
            console.print(f"    Notes: {item.fact_check_notes}")
            console.print(f"    Metrics: {item.verified_metrics}\n")

async def view_mcp_servers():
    display_banner()
    console.print("\n[bold cyan]Model Context Protocol (MCP) Ecosystem[/bold cyan]\n")

    mcp_client = RadarMCPClient()

    # Internal MCP Tools
    table = Table(title="Internal Radar MCP Tools (radar-mcp)", border_style="green")
    table.add_column("Tool Name", style="bold green")
    table.add_column("Description", style="dim")

    internal_tools = [
        ("github_search_trending", "Search for recently created or active repositories matching topic on GitHub."),
        ("github_verify_repo", "Verify live status, stars, forks, and last commit date of a GitHub repository."),
        ("hn_search_discussions", "Search Hacker News for community discussions, launches, and comments."),
        ("web_extract_markdown", "Fetch external web page, clean HTML, and return safe markdown with untrusted content wrapper."),
        ("arxiv_search_papers", "Search arXiv for recent scientific and architectural research preprints."),
        ("reddit_search_discussions", "Search developer communities on Reddit for discussions, benchmarks, and community sentiment."),
        ("db_persist_intel", "Persist a verified intelligence item to the local SQLite database."),
        ("db_query_history", "Query past intelligence items to prevent duplicates and check for historical coverage."),
        ("db_save_briefing", "Save the final generated markdown briefing to database."),
        ("db_get_velocity_delta", "Calculate the velocity delta (growth change) between the two most recent metric snapshots.")
    ]

    for name, desc in internal_tools:
        table.add_row(name, desc)
    console.print(table)

    # Configured External MCP Servers
    bridge = ExternalMCPBridge()
    servers = bridge.list_configured_servers()

    ext_table = Table(title="Configured External MCP Servers (mcp_servers.json)", border_style="yellow")
    ext_table.add_column("Server Name", style="bold yellow")
    ext_table.add_column("Command / Package", style="cyan")
    ext_table.add_column("Status", justify="center")
    ext_table.add_column("Description", style="dim")

    for s in servers:
        status_style = "bold green" if s["status"] == "Active" else "bold red"
        ext_table.add_row(
            s["name"],
            f"{s['command']} {' '.join(s['args'])}",
            f"[{status_style}]{s['status']}[/{status_style}]",
            s["description"]
        )
    console.print(ext_table)

    # Discovered External Tools
    ext_tools = await bridge.list_all_external_tools()
    if ext_tools:
        ext_tools_table = Table(title="Tools Imported from Active External MCP Servers", border_style="magenta")
        ext_tools_table.add_column("External Server", style="bold yellow")
        ext_tools_table.add_column("Tool Name", style="bold magenta")
        ext_tools_table.add_column("Description", style="dim")
        for tool in ext_tools:
            ext_tools_table.add_row(tool["server"], tool["name"], tool["description"][:80])
        console.print(ext_tools_table)

    console.print("[dim]Add third-party servers to 'mcp_servers.json' to extend the radar with external MCP capabilities.[/dim]\n")

def print_quick_help():
    display_banner()
    console.print("\n[bold cyan]🚀 Simple Commands Reference:[/bold cyan]\n")
    console.print("  [bold green]radar[/bold green]               🚀 Launch Interactive Web Radar in browser [dim](Default)[/dim]")
    console.print("  [bold green]radar \"<topic>\"[/bold green]     🔍 Run multi-agent intelligence scan on topic in terminal")
    console.print("  [bold green]radar morning[/bold green]       🌅 Run the daily combined AI briefing & send email")
    console.print("  [bold green]radar test-email[/bold green]    ✉️ Send sample test briefing email to your Gmail")
    console.print("  [bold green]radar schedule[/bold green]      ⏰ Manage 8:00 AM IST daily Windows schedule (--install/--remove)")
    console.print("  [bold green]radar menu[/bold green]          🧑‍💻 Open interactive terminal menu")
    console.print("  [bold green]radar history[/bold green]       📋 View tracked technologies from SQLite database")
    console.print("  [bold green]radar servers[/bold green]       🔌 List registered internal & external MCP tools")
    console.print("  [bold green]radar latest[/bold green]        📑 View the latest briefing report")
    console.print("\n[dim]Run 'radar --help' for full advanced flags.[/dim]\n")

def interactive_menu():
    display_banner()
    console.print("\n[bold cyan]📡 Tech Intelligence Radar - Main Menu[/bold cyan]")
    console.print("─────────────────────────────────────────────")
    console.print("  [bold green][1][/bold green] 🚀 [bold]Launch Web Radar UI[/bold] (Opens in Browser) [dim][Default][/dim]")
    console.print("  [bold yellow][2][/bold yellow] 🔍 [bold]Run Intelligence Scan on a New Topic[/bold]")
    console.print("  [bold blue][3][/bold blue] 📋 [bold]View Tracked Intelligence & Database History[/bold]")
    console.print("  [bold magenta][4][/bold magenta] 🔌 [bold]Inspect Connected MCP Servers & Tools[/bold]")
    console.print("  [bold cyan][5][/bold cyan] 📑 [bold]View Latest Briefing Report[/bold]")
    console.print("  [bold white][6][/bold white] 🛰️ [bold]Run Standalone MCP Server over stdio[/bold]")
    console.print("  [bold green][7][/bold green] ✉️  [bold]Send Test Morning Briefing Email to Gmail[/bold]")
    console.print("  [bold yellow][8][/bold yellow] 🌅 [bold]Run Combined Morning AI Intelligence Cycle Now[/bold]")
    console.print("  [bold cyan][9][/bold cyan] ⏰ [bold]Install / Manage 8:00 AM Daily Windows Schedule[/bold]")
    console.print("  [bold red][0][/bold red] ❌ [bold]Exit[/bold]\n")

    choice = Prompt.ask("[bold green]Select an option[/bold green]", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", ""], default="1")
    if choice in ("1", ""):
        launch_ui()
    elif choice == "2":
        topic = Prompt.ask("\n[bold yellow]Enter domain or topic to research[/bold yellow]", default="Model Context Protocol")
        asyncio.run(run_pipeline(topic))
    elif choice == "3":
        asyncio.run(view_history())
    elif choice == "4":
        asyncio.run(view_mcp_servers())
    elif choice == "5":
        asyncio.run(view_latest())
    elif choice == "6":
        run_mcp_server()
    elif choice == "7":
        handle_test_email()
    elif choice == "8":
        asyncio.run(run_morning_cycle(send_email=True))
    elif choice == "9":
        handle_schedule_cli([])
    elif choice == "0":
        console.print("[dim]Goodbye![/dim]")

def handle_test_email():
    display_banner()
    console.print("\n[bold yellow]✉️ Testing Gmail SMTP Connection...[/bold yellow]")
    if not is_smtp_configured():
        console.print("[bold red]✗ Gmail credentials not configured in .env[/bold red]")
        console.print("Please edit the [cyan].env[/cyan] file in the project folder with:")
        console.print("  GMAIL_USER=your_email@gmail.com")
        console.print("  GMAIL_APP_PASSWORD=your_16_char_password\n")
        return

    res = send_test_email()
    if res.get("success"):
        console.print(f"[bold green]✓ SUCCESS![/bold green] Sample briefing email delivered to: [bold cyan]{res.get('recipient')}[/bold cyan]")
        console.print("Check your Gmail inbox (or Promotions/Updates tab) to see the design!\n")
    else:
        console.print(f"[bold red]✗ ERROR:[/bold red] {res.get('error')}\n")

def handle_schedule_cli(args_list: list):
    display_banner()
    if "--install" in args_list or "install" in args_list:
        install_daily_schedule()
    elif "--remove" in args_list or "remove" in args_list:
        remove_daily_schedule()
    else:
        # Default: check status, audit health flags, and offer install/repair
        is_active = query_daily_schedule()
        if not is_active:
            sub = Prompt.ask("\nWould you like to register the 8:00 AM IST daily schedule in Windows Task Scheduler?", choices=["y", "n"], default="y")
            if sub.lower() == "y":
                install_daily_schedule()
        elif schedule_needs_repair(get_schedule_details()):
            sub = Prompt.ask("\nUpgrade scheduled task with battery-safe + sleep catch-up settings now?", choices=["y", "n"], default="y")
            if sub.lower() == "y":
                install_daily_schedule()

def launch_ui(port: int = 8844):
    from radar.ui.generator import generate_radar_html_from_entities
    from radar.ui.server import start_radar_server
    from radar.config import BRIEFINGS_DIR

    display_banner()
    # Refresh radar_latest.html from latest DB entities and current template
    async def prep_html():
        await init_db()
        entities = await get_all_tracked_entities()
        latest_b = await get_latest_briefing()
        topic = latest_b.get("topic_query", "Model Context Protocol") if latest_b else "Model Context Protocol"
        if entities:
            generate_radar_html_from_entities(topic, entities)
    asyncio.run(prep_html())

    console.print(f"[bold green]🚀 Launching Interactive Visual Tech Radar...[/bold green]")
    start_radar_server(port=port, auto_open=True)

def main():
    # If no arguments provided: default directly to launching the Web UI!
    if len(sys.argv) == 1:
        launch_ui()
        return

    first_arg = sys.argv[1].strip().lower()
    
    if first_arg in ("ui", "dashboard", "web"):
        launch_ui()
        return
    elif first_arg in ("menu", "interactive"):
        interactive_menu()
        return
    elif first_arg in ("morning", "daily"):
        res = asyncio.run(run_morning_cycle(send_email=True))
        if is_smtp_configured() and not res.get("email_status", {}).get("sent"):
            sys.exit(1)
        return
    elif first_arg in ("test-email", "test_email", "testemail"):
        handle_test_email()
        return
    elif first_arg in ("schedule", "cron"):
        handle_schedule_cli(sys.argv[2:])
        return
    elif first_arg in ("history", "db"):
        asyncio.run(view_history())
        return
    elif first_arg in ("servers", "mcp"):
        asyncio.run(view_mcp_servers())
        return
    elif first_arg in ("latest", "report"):
        asyncio.run(view_latest())
        return
    elif first_arg in ("help", "commands"):
        print_quick_help()
        return
    elif first_arg == "scan" and len(sys.argv) > 2:
        topic = " ".join(sys.argv[2:])
        asyncio.run(run_pipeline(topic))
        return

    # Standard argparse for options, flags, and direct topics
    parser = argparse.ArgumentParser(
        description="Autonomous Market & Tech Intelligence Radar",
        epilog="Examples:\n  radar                   # Launch Web UI\n  radar \"AI Agents\"       # Run terminal scan\n  radar morning           # Run 8:00 AM briefing cycle\n  radar test-email        # Test Gmail delivery\n  radar schedule          # Manage Windows 8 AM schedule\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("topic", nargs="?", default=None, help="Topic to research (optional)")
    parser.add_argument("--ui", "--dashboard", dest="ui", action="store_true", help="Launch interactive browser-based Tech Radar visualization")
    parser.add_argument("--history", action="store_true", help="View tracked entities from database")
    parser.add_argument("--latest", action="store_true", help="View the latest generated briefing")
    parser.add_argument("--servers", action="store_true", help="List registered internal and external MCP servers/tools")
    parser.add_argument("--serve-mcp", action="store_true", help="Run as standalone MCP server over stdio")
    parser.add_argument("--morning", action="store_true", help="Run morning combined intelligence cycle")
    parser.add_argument("--test-email", action="store_true", help="Send a test briefing email via Gmail SMTP")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logs")
    parser.add_argument("-i", "--interactive", action="store_true", help="Enable Human-in-the-Loop candidate selection")

    args = parser.parse_args()

    if args.serve_mcp:
        run_mcp_server()
    elif args.morning:
        res = asyncio.run(run_morning_cycle(send_email=True))
        if is_smtp_configured() and not res.get("email_status", {}).get("sent"):
            sys.exit(1)
    elif args.test_email:
        handle_test_email()
    elif args.ui:
        launch_ui()
    elif args.servers:
        asyncio.run(view_mcp_servers())
    elif args.history:
        asyncio.run(view_history())
    elif args.latest:
        asyncio.run(view_latest())
    elif args.topic:
        asyncio.run(run_pipeline(args.topic, verbose=args.verbose, interactive=args.interactive))
    else:
        launch_ui()

if __name__ == "__main__":
    main()
