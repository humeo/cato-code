from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.panel import Panel

from .auth import get_auth
from .config import (
    get_anthropic_api_key,
    get_github_app_client_id,
    get_github_app_client_secret,
    get_session_secret_key,
)
from .container.manager import ContainerManager
from .store import Store

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catocode",
        description="CatoCode — Self-Proving Autonomous Code Maintainer",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- server (SaaS mode) ---
    server_p = subparsers.add_parser("server", help="Run full SaaS server (OAuth + API + webhooks + scheduler)")
    server_p.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    server_p.add_argument("--max-concurrent", type=int, default=3)

    # --- daemon ---
    daemon_p = subparsers.add_parser("daemon", help="Run background scheduler (blocking)")
    daemon_p.add_argument("--max-concurrent", type=int, default=3, help="Max concurrent activities")
    daemon_p.add_argument(
        "--webhook-port",
        type=int,
        default=0,
        metavar="PORT",
        help="Start webhook server on PORT (0 = disabled, default: 0)",
    )

    # --- status ---
    status_p = subparsers.add_parser("status", help="Show repo or activity status")
    status_p.add_argument("target", nargs="?", help="repo_id or activity_id (omit for all)")

    # --- logs ---
    logs_p = subparsers.add_parser("logs", help="View activity logs")
    logs_p.add_argument("activity_id")
    logs_p.add_argument("--follow", "-f", action="store_true", help="Follow log output")

    return parser

# --- daemon ---

async def cmd_server(args: argparse.Namespace) -> int:
    """Run full SaaS server — equivalent to daemon with webhook port enabled."""
    # Map server args to daemon-compatible namespace
    args.webhook_port = args.port
    return await cmd_daemon(args)


async def cmd_daemon(args: argparse.Namespace) -> int:
    from .scheduler import Scheduler

    try:
        get_anthropic_api_key()
        auth = get_auth()
        if args.webhook_port:
            get_github_app_client_id()
            get_github_app_client_secret()
            get_session_secret_key()
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    store = Store()
    container_mgr = ContainerManager()

    webhook_port: int = args.webhook_port
    info_lines = [
        "[bold green]CatoCode Daemon[/bold green]",
        f"Max concurrent: {args.max_concurrent}",
        f"Auth: {auth.auth_type()}",
    ]
    if webhook_port:
        info_lines.append(f"API server: http://0.0.0.0:{webhook_port}")
    info_lines.append("Press Ctrl+C to stop")

    console.print(Panel("\n".join(info_lines), border_style="green"))

    scheduler = Scheduler(
        store=store,
        container_mgr=container_mgr,
        max_concurrent=args.max_concurrent,
        verbose=args.verbose,
        auth=auth,
    )

    tasks = [asyncio.create_task(scheduler.run())]

    if webhook_port:
        import uvicorn

        from .api.app import create_app

        app = create_app(store=store, auth=auth)
        console.print("[dim]GitHub App SaaS mode: login + API + webhooks on same port[/dim]")

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=webhook_port,
            log_level="warning",
        )
        uv_server = uvicorn.Server(config)
        tasks.append(asyncio.create_task(uv_server.serve()))

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        scheduler.stop()
        for t in tasks:
            t.cancel()

    console.print("[yellow]Daemon stopped[/yellow]")
    return 0


# --- status ---

async def cmd_status(args: argparse.Namespace) -> int:
    store = Store()
    target = args.target

    if target is None:
        # Show all repos and recent activities
        repos = store.list_repos()
        if not repos:
            console.print("[dim]No repos registered. Install the GitHub App and watch a repo to start.[/dim]")
            return 0

        for repo in repos:
            watched = "👀" if repo["watch"] else "  "
            console.print(f"{watched} [cyan]{repo['id']}[/cyan] ({repo['repo_url']})")
            activities = store.list_activities(repo["id"])
            for a in list(activities)[-5:]:  # Last 5 per repo
                color = {"done": "green", "failed": "red", "running": "blue", "pending": "yellow"}.get(a["status"], "white")
                console.print(f"   [{color}]{a['status']:8}[/{color}] {a['id'][:8]} {a['kind']:15} {a['updated_at'][:19]}")
        return 0

    # Check if target is an activity_id or repo_id
    activity = store.get_activity(target)
    if activity:
        color = {"done": "green", "failed": "red", "running": "blue", "pending": "yellow"}.get(activity["status"], "white")
        console.print(f"Activity: {activity['id']}")
        console.print(f"  Repo:    {activity['repo_id']}")
        console.print(f"  Kind:    {activity['kind']}")
        console.print(f"  Status:  [{color}]{activity['status']}[/{color}]")
        console.print(f"  Session: {activity['session_id'] or 'none'}")
        console.print(f"  Summary: {activity['summary'] or 'none'}")
        return 0

    repo = store.get_repo(target)
    if repo:
        console.print(f"Repo: {repo['id']}")
        console.print(f"  URL:     {repo['repo_url']}")
        console.print(f"  Watch:   {'yes' if repo['watch'] else 'no'}")
        activities = store.list_activities(target)
        console.print(f"  Activities ({len(list(activities))}):")
        for a in list(activities)[-10:]:
            color = {"done": "green", "failed": "red", "running": "blue", "pending": "yellow"}.get(a["status"], "white")
            console.print(f"    [{color}]{a['status']:8}[/{color}] {a['id'][:8]} {a['kind']:15} {a['updated_at'][:19]}")
        return 0

    console.print(f"[red]Not found:[/red] {target}")
    return 1


# --- logs ---

async def cmd_logs(args: argparse.Namespace) -> int:
    store = Store()
    activity_id = args.activity_id

    # Support short IDs (first 8 chars)
    if len(activity_id) == 8:
        activities = store.list_activities()
        matches = [a for a in activities if a["id"].startswith(activity_id)]
        if len(matches) == 1:
            activity_id = matches[0]["id"]
        elif len(matches) > 1:
            console.print(f"[red]Ambiguous short ID:[/red] {activity_id}")
            return 1

    activity = store.get_activity(activity_id)
    if activity is None:
        console.print(f"[red]Activity not found:[/red] {activity_id}")
        return 1

    logs = store.get_logs(activity_id)
    for log in logs:
        _print_log_line(log["line"])

    if args.follow:
        last_id = logs[-1]["id"] if logs else 0
        while True:
            await asyncio.sleep(0.5)
            activity = store.get_activity(activity_id)
            if activity and activity["status"] in ("done", "failed"):
                # Print remaining logs then exit
                logs = store.get_logs(activity_id)
                for log in logs:
                    if log["id"] > last_id:
                        _print_log_line(log["line"])
                break
            logs = store.get_logs(activity_id)
            new_logs = [log for log in logs if log["id"] > last_id]
            for log in new_logs:
                _print_log_line(log["line"])
                last_id = log["id"]

    return 0


def _print_log_line(line: str) -> None:
    """Print a log line, stripping JSONL noise for readability."""
    import json
    stripped = line.strip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
            msg_type = obj.get("type", "")
            if msg_type == "assistant":
                text = obj.get("text", "").strip()
                if text:
                    console.print(f"[dim]💬 {text[:200]}[/dim]")
            elif msg_type == "tool_use":
                name = obj.get("name", "")
                inp = obj.get("input", {})
                cmd = inp.get("command", inp.get("path", str(inp)))[:100]
                console.print(f"[blue]🔧 {name}[/blue]: {cmd}")
            elif msg_type == "tool_result":
                out = obj.get("output", "")[:150]
                is_err = obj.get("is_error", False)
                color = "red" if is_err else "dim"
                console.print(f"[{color}]  → {out}[/{color}]")
            elif msg_type == "result":
                result = obj.get("result", "")[:300]
                cost = obj.get("cost_usd")
                turns = obj.get("num_turns")
                cost_str = f" (${cost:.4f}, {turns} turns)" if cost else ""
                console.print(f"[green]✅ Result{cost_str}:[/green] {result}")
            elif msg_type == "system":
                pass  # Skip system messages
            else:
                console.print(f"[dim]{stripped}[/dim]")
        except json.JSONDecodeError:
            console.print(f"[dim]{stripped}[/dim]")
    else:
        console.print(f"[dim]{stripped}[/dim]")


async def run_async(args: argparse.Namespace) -> int:
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    commands = {
        "server": cmd_server,
        "daemon": cmd_daemon,
        "status": cmd_status,
        "logs": cmd_logs,
    }

    handler = commands.get(args.command)
    if handler is None:
        console.print(f"[red]Unknown command:[/red] {args.command}")
        return 1

    return await handler(args)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(asyncio.run(run_async(args)))


if __name__ == "__main__":
    main()
