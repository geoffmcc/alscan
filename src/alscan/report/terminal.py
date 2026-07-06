from __future__ import annotations

import io

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich import box

from alscan.models import ScanResult

SEVERITY_STYLES = {
    "error": "bold red",
    "warning": "bold yellow",
    "info": "cyan",
    "suggestion": "dim white",
}

SEVERITY_LABELS = {
    "error": "ERROR",
    "warning": "WARN",
    "info": "INFO",
    "suggestion": "SUGGEST",
}


def print_terminal_report(result: ScanResult, verbose: bool = False) -> str:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)

    proj = result.project

    console.print()
    console.print(Panel(
        f"[bold]alscan[/bold] - Project Health Scan  "
        f"[dim]{proj.file_path.name if proj.file_path else ''}[/dim]",
        border_style="blue",
    ))

    stats = Table.grid(padding=(0, 2))
    stats.add_column(style="bold")
    stats.add_column()
    stats.add_row("File:", proj.file_path.name if proj.file_path else "N/A")
    stats.add_row("Creator:", proj.creator or "Unknown")
    stats.add_row("Tempo:", f"{proj.tempo:.1f} BPM")
    stats.add_row("Time Sig:", f"{proj.time_signature[0]}/{proj.time_signature[1]}")
    stats.add_row("Tracks:", str(len(proj.tracks)))
    stats.add_row("Locators:", str(len(proj.locators)))
    console.print(stats)
    console.print()

    if result.findings:
        e, w, i = len(result.errors), len(result.warnings), len(result.info)
        parts = []
        if e:
            parts.append(f"[bold red]{e} error(s)[/bold red]")
        if w:
            parts.append(f"[bold yellow]{w} warning(s)[/bold yellow]")
        if i:
            parts.append(f"[cyan]{i} info[/cyan]")
        console.print("Found " + ", ".join(parts))
        console.print()
    else:
        console.print("[green]No issues found![/green]")
        console.print()

    if result.findings:
        table = Table(box=box.SIMPLE, header_style="bold")
        table.add_column("Severity", width=10)
        table.add_column("Check", width=22)
        table.add_column("Message", width=70)

        for finding in sorted(
            result.findings,
            key=lambda f: ("error", "warning", "info", "suggestion").index(f.severity),
        ):
            style = SEVERITY_STYLES.get(finding.severity, "")
            label = SEVERITY_LABELS.get(finding.severity, "INFO")
            table.add_row(
                Text(label, style=style),
                Text(finding.check_name, style=style),
                Text(finding.message, style=style),
            )

        console.print(table)
        console.print()

    if verbose and result.findings:
        console.print("[bold]Details[/bold]")
        for finding in result.findings:
            console.print()
            label = SEVERITY_LABELS.get(finding.severity, "INFO")
            style = SEVERITY_STYLES.get(finding.severity, "")
            console.print(f"  [{style}]{label}[/] {finding.check_name}: {finding.title}")
            console.print(f"    Message:   {finding.message}")
            if finding.location:
                console.print(f"    Location:  {finding.location}")
            if finding.suggestion:
                console.print(f"    Suggestion: {finding.suggestion}")
            if finding.file_path:
                console.print(f"    File:      {finding.file_path}")
        console.print()

    console.print(f"[dim]Scan completed in {result.scan_time_ms}ms[/dim]")
    console.print()

    return buf.getvalue()
