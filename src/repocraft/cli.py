from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .config import get_anthropic_api_key, get_github_token, parse_issue_url, repo_id_from_url
from .container.manager import ContainerManager
from .dispatcher import dispatch
from .store import Store

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repocraft",
        description="RepoCraft v2 - Autonomous codebase maintenance agent",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # fix: blocking execution
    fix_parser = subparsers.add_parser(
        "fix",
        help="Fix a GitHub issue (blocking)",
    )
    fix_parser.add_argument(
        "issue_url",
        help="GitHub issue URL (e.g. https://github.com/owner/repo/issues/42)",
    )
    fix_parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Claude model to use (default: claude-sonnet-4-6)",
    )
    fix_parser.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help="Maximum agent turns (default: 200)",
    )

    # submit: async execution (stub)
    submit_parser = subparsers.add_parser(
        "submit",
        help="Submit an issue for async processing (stub)",
    )
    submit_parser.add_argument("issue_url")

    # ask: free-form instruction (stub)
    ask_parser = subparsers.add_parser(
        "ask",
        help="Give the agent a free-form instruction (stub)",
    )
    ask_parser.add_argument("repo")
    ask_parser.add_argument("instruction")

    # daemon: background scheduler (stub)
    subparsers.add_parser(
        "daemon",
        help="Run background scheduler (stub)",
    )

    # status: check progress (stub)
    status_parser = subparsers.add_parser(
        "status",
        help="Check activity status (stub)",
    )
    status_parser.add_argument("target", nargs="?", help="repo_id or activity_id")

    # logs: view activity logs (stub)
    logs_parser = subparsers.add_parser(
        "logs",
        help="View activity logs (stub)",
    )
    logs_parser.add_argument("activity_id")
    logs_parser.add_argument("--follow", "-f", action="store_true")

    return parser


async def cmd_fix(args: argparse.Namespace) -> int:
    """Fix a GitHub issue (blocking execution with live log streaming)."""
    try:
        owner, repo, issue_number = parse_issue_url(args.issue_url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    repo_url = f"https://github.com/{owner}/{repo}"
    repo_id = repo_id_from_url(repo_url)

    console.print(
        Panel(
            Text.from_markup(
                f"[bold]RepoCraft v2[/bold]\n"
                f"Repo: [cyan]{owner}/{repo}[/cyan]\n"
                f"Issue: [yellow]#{issue_number}[/yellow]\n"
                f"Model: [green]{args.model}[/green]\n"
                f"Max turns: [magenta]{args.max_turns}[/magenta]"
            ),
            title="Starting",
            border_style="blue",
        )
    )

    try:
        anthropic_api_key = get_anthropic_api_key()
        github_token = get_github_token()
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    store = Store()
    container_mgr = ContainerManager()

    # Add repo if not exists
    if store.get_repo(repo_id) is None:
        store.add_repo(repo_id, repo_url)
        console.print(f"[dim]Registered repo: {repo_id}[/dim]")

    # Create activity
    activity_id = store.add_activity(repo_id, "fix_issue", f"issue:{issue_number}")
    console.print(f"[dim]Created activity: {activity_id}[/dim]\n")

    # Dispatch with live log streaming
    console.print("[bold blue]▶ Dispatching activity...[/bold blue]")

    try:
        # Run dispatch in background task
        dispatch_task = asyncio.create_task(
            dispatch(
                activity_id=activity_id,
                store=store,
                container_mgr=container_mgr,
                anthropic_api_key=anthropic_api_key,
                github_token=github_token,
                max_turns=args.max_turns,
                verbose=args.verbose,
            )
        )

        # Poll logs and display in real-time
        last_log_id = 0
        with Live(console=console, refresh_per_second=2) as live:
            while not dispatch_task.done():
                logs = store.get_logs(activity_id)
                new_logs = [log for log in logs if log["id"] > last_log_id]
                if new_logs:
                    for log in new_logs:
                        console.print(f"[dim]{log['line'].rstrip()}[/dim]")
                        last_log_id = log["id"]
                await asyncio.sleep(0.5)

        # Wait for dispatch to complete
        await dispatch_task

        # Print final logs
        logs = store.get_logs(activity_id)
        new_logs = [log for log in logs if log["id"] > last_log_id]
        for log in new_logs:
            console.print(f"[dim]{log['line'].rstrip()}[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        store.update_activity(activity_id, status="failed", summary="Interrupted by user")
        return 1
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Get final status
    activity = store.get_activity(activity_id)
    if activity is None:
        console.print("[red]Activity not found after dispatch[/red]")
        return 1

    status = activity["status"]
    summary = activity["summary"] or "No summary"

    if status == "done":
        console.print(
            Panel(
                Text.from_markup(
                    f"[bold green]SUCCESS[/bold green]\n\n"
                    f"{summary}"
                ),
                title="Activity Completed",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                Text.from_markup(
                    f"[bold red]FAILED[/bold red]\n\n"
                    f"{summary}"
                ),
                title="Activity Failed",
                border_style="red",
            )
        )
        return 1


def cmd_submit(args: argparse.Namespace) -> int:
    console.print("[yellow]submit command not yet implemented (M2)[/yellow]")
    return 1


def cmd_ask(args: argparse.Namespace) -> int:
    console.print("[yellow]ask command not yet implemented (M2)[/yellow]")
    return 1


def cmd_daemon(args: argparse.Namespace) -> int:
    console.print("[yellow]daemon command not yet implemented (M2)[/yellow]")
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    console.print("[yellow]status command not yet implemented (M2)[/yellow]")
    return 1


def cmd_logs(args: argparse.Namespace) -> int:
    console.print("[yellow]logs command not yet implemented (M2)[/yellow]")
    return 1


async def run_async(args: argparse.Namespace) -> int:
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "fix":
        return await cmd_fix(args)
    elif args.command == "submit":
        return cmd_submit(args)
    elif args.command == "ask":
        return cmd_ask(args)
    elif args.command == "daemon":
        return cmd_daemon(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "logs":
        return cmd_logs(args)
    else:
        console.print(f"[red]Unknown command: {args.command}[/red]")
        return 1


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(asyncio.run(run_async(args)))


if __name__ == "__main__":
    main()
