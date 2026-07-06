from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from alscan import __version__
from alscan.parser import parse_als
from alscan.project import find_als_file
from alscan.report.terminal import print_terminal_report, print_batch_summary
from alscan.report.html import generate_html_report
from alscan.report.json import generate_json_report
from alscan.models import ScanResult


@click.group()
@click.version_option(version=__version__, prog_name="alscan")
def cli() -> None:
    """Ableton Live Project Health Scanner"""


@cli.command()
@click.argument("path", type=str, required=True)
@click.option("--format", "-f", type=click.Choice(["terminal", "json", "html"]), default="terminal",
              help="Output format (default: terminal)")
@click.option("--browser", "-o", is_flag=True, default=False, help="Open HTML report in browser")
@click.option("--output", "-O", type=str, default="", help="Write output to file")
@click.option("--recursive", "-r", is_flag=True, default=False, help="Scan all projects in a directory")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show detailed output")
@click.option("--exit-code", "-e", is_flag=True, default=False, help="Exit with code 1 if any errors found")
@click.option("--pretty", "-p", is_flag=True, default=True, help="Pretty-print JSON output")
def scan(path: str, format: str, browser: bool, output: str, recursive: bool,
         verbose: bool, exit_code: bool, pretty: bool) -> None:
    """Scan an Ableton Live project for health issues."""
    scan_path = Path(path).resolve()
    any_errors = False

    if recursive and scan_path.is_dir():
        from alscan.project import find_projects
        projects = find_projects(scan_path)
        if not projects:
            click.echo(f"No Ableton projects found under {scan_path}", err=True)
            sys.exit(1)

        results = []
        total = len(projects)
        for i, proj_dir in enumerate(projects, 1):
            name = proj_dir.name
            click.echo(f"[{i}/{total}] {name}...", err=True)
            try:
                r = _scan_single(str(proj_dir), format, browser, output, verbose, pretty)
                if r and len(r.errors) > 0:
                    any_errors = True
                results.append(r)
            except Exception as e:
                click.echo(f"  Failed: {e}", err=True)

        if format == "terminal" and results:
            print_batch_summary(results)
    else:
        result = _scan_single(path, format, browser, output, verbose, pretty)
        if result and len(result.errors) > 0:
            any_errors = True

    if exit_code and any_errors:
        sys.exit(1)


def _scan_single(path: str, fmt: str, open_browser: bool, output_path: str,
                 verbose: bool, pretty: bool = True) -> ScanResult | None:
    als_file = find_als_file(path)
    if als_file is None:
        click.echo(f"Could not find a .als file at: {path}", err=True)
        return None

    start = time.time()

    try:
        project = parse_als(als_file)
    except Exception as e:
        click.echo(f"Error parsing {als_file}: {e}", err=True)
        return None

    from alscan.checks import list_checks
    findings = []
    for check in list_checks():
        try:
            result = check.func(project)
            findings.extend(result)
        except Exception as e:
            if verbose:
                click.echo(f"  Check '{check.name}' failed: {e}", err=True)

    elapsed = (time.time() - start) * 1000
    result = ScanResult(project=project, findings=findings, scan_time_ms=round(elapsed, 1))

    if fmt == "json":
        text = generate_json_report(result, pretty=pretty)
        if output_path:
            Path(output_path).write_text(text)
        else:
            click.echo(text)
    elif fmt == "html":
        html = generate_html_report(result)
        out_file = Path(output_path) if output_path else als_file.parent / "alscan-report.html"
        out_file.write_text(html)
        click.echo(f"HTML report written to: {out_file}", err=True)
        if open_browser:
            import webbrowser
            webbrowser.open(f"file://{out_file.resolve()}")
    else:
        text = print_terminal_report(result, verbose=verbose)
        if output_path:
            Path(output_path).write_text(text)
        else:
            click.echo(text)

    return result


@cli.command(name="list-checks")
def list_checks_command() -> None:
    """List all available health checks"""
    from alscan.checks import list_checks
    checks = list_checks()
    if not checks:
        click.echo("No checks registered.")
        return
    click.echo(f"{len(checks)} checks available:\n")
    for c in sorted(checks, key=lambda x: x.name):
        severity_tag = f"[{c.severity.upper()}]" if c.severity else ""
        click.echo(f"  {c.name:35s} {severity_tag:10s} {c.description}")
