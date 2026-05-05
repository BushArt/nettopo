"""
main_static.py — Phase 1 entry point.

Runs nmap, parses output, writes JSON to data/sessions/latest.json.
This is NOT the long-term server entry point (that is main.py in Phase 2).

Usage:
    python main_static.py
    python main_static.py --subnet 192.168.1.0/24 --profile ports
    python main_static.py --output data/sessions/my_scan.json
"""

import argparse
import json
import logging
import pathlib
import time
import uuid
from datetime import datetime, timezone

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scanner import runner, parser

console = Console()
logging.basicConfig(level=logging.WARNING)


def load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        console.print(f"[yellow]Warning:[/yellow] {path} not found — using defaults.")
        return {}


def main() -> None:
    config = load_config()

    # ── CLI args ──────────────────────────────────────────────────────────────
    defaults = config.get("scanner", {})
    arg = argparse.ArgumentParser(description="NetTopo Phase 1 — Static Scanner")
    arg.add_argument("--subnet",  default=defaults.get("default_subnet",  "172.20.0.0/24"))
    arg.add_argument("--profile", default=defaults.get("default_profile", "quick"))
    arg.add_argument("--output",  default=str(pathlib.Path(
                         defaults.get("output_dir", "data/sessions/")) / "latest.json"))
    args = arg.parse_args()

    # ── Header ────────────────────────────────────────────────────────────────
    console.print(Panel.fit(
        f"[bold cyan]NetTopo[/bold cyan] — Phase 1 Static Scanner\n"
        f"Target: [green]{args.subnet}[/green]  ·  Profile: [yellow]{args.profile}[/yellow]",
        title="NetTopo",
    ))

    # ── Scan ──────────────────────────────────────────────────────────────────
    t0 = time.time()
    xml_string = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Scanning {args.subnet} …", total=None)
        try:
            xml_string = runner.run_scan(args.subnet, args.profile, config)
        except (
            runner.PermissionStatementMissingError,
            runner.SubnetNotAllowedError,
        ) as e:
            console.print(f"\n[bold red]Blocked:[/bold red] {e}")
            raise SystemExit(1)
        except runner.NmapExecutionError as e:
            console.print(f"\n[bold red]nmap error:[/bold red] {e}")
            raise SystemExit(1)
        finally:
            progress.remove_task(task)

    scan_duration = time.time() - t0

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        hosts = parser.parse_xml(xml_string)
    except parser.ParseError as e:
        console.print(f"[bold red]Parse error:[/bold red] {e}")
        raise SystemExit(1)

    console.print(f"[green]✓[/green] Discovered [bold]{len(hosts)}[/bold] hosts in {scan_duration:.1f}s")

    # ── Write JSON output ─────────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hosts, f, indent=2, ensure_ascii=False)

    # Also write a timestamped copy for Phase 4 history features
    ts_path = output_path.parent / f"{scan_id}.json"
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(hosts, f, indent=2, ensure_ascii=False)

    # ── Summary table ─────────────────────────────────────────────────────────
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("IP", style="cyan")
    table.add_column("Hostname")
    table.add_column("OS Family")
    table.add_column("Open Ports", justify="right")
    table.add_column("Status")

    for h in hosts:
        table.add_row(
            h["ip"],
            h["hostname"] or "—",
            h["os_family"] or "—",
            str(len(h["ports"])),
            h["status"],
        )

    console.print(table)
    console.print(f"\n[dim]Output:[/dim] {output_path.resolve()}")
    console.print(f"[dim]Run [bold]make serve[/bold] then open http://localhost:8080/frontend/index.html to view graph.[/dim]")


if __name__ == "__main__":
    main()
