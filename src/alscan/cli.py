from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import click

from alscan import __version__
from alscan.parser import parse_als
from alscan.project import find_als_file, _validate_parent
from alscan.report.terminal import print_terminal_report, print_batch_summary
from alscan.report.html import generate_html_report
from alscan.report.json import generate_json_report
from alscan.models import ScanResult
from alscan.versioner import (
    build_snapshot,
    save_snapshot,
    load_snapshot,
    find_snapshots,
    diff_snapshots,
    Snapshot,
    SNAPSHOT_FORMAT_VERSION,
)

ABLETON_CONTENT_EXTENSIONS = {".als", ".wav", ".aiff", ".aif", ".asd", ".adg", ".amxd", ".alp"}


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _atomic_publish_report(temp_path: Path, dest: Path) -> None:
    """Publish *temp_path* to *dest* with atomic no-clobber semantics.

    Uses os.link() which creates a hard link at *dest* pointing to the
    same data as *temp_path* only if *dest* does not already exist.
    This is a single filesystem call — no TOCTOU race between checking
    and writing.

    On success  → *dest* contains the data, *temp_path* is unlinked.
    On failure  → *dest* is untouched, *temp_path* is unlinked.
    On conflict → FileExistsError is raised (another writer already
                  published to *dest*), *temp_path* is unlinked.

    os.link() requires both paths on the same volume, which holds here
    because *temp_path* is created in *dest.parent*.
    """
    try:
        os.link(str(temp_path), str(dest))
    except FileExistsError:
        raise
    finally:
        _safe_unlink(temp_path)


def _atomic_write_report(dest: Path, content: str) -> None:
    """Write *content* to *dest* with atomic no-clobber publication.

    Creates parent directories if needed, writes to a temporary file in
    the same directory, flushes and fsyncs, then publishes atomically.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(dest.parent),
        prefix=f".{dest.name}.tmp.",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        _atomic_publish_report(tmp_path, dest)
    except BaseException:
        _safe_unlink(tmp_path)
        raise


def _safe_report_output(output_path: str, source_als: Path) -> Path:
    """Validate *output_path* for use as a report destination.

    Returns the resolved Path if safe, or prints an error and exits.
    """
    p = Path(output_path)
    _validate_parent(p)
    p = p.resolve()
    source = source_als.resolve()

    if p == source:
        click.echo("Error: refusing to overwrite the source .als file with report output", err=True)
        sys.exit(1)

    if p.suffix.lower() in ABLETON_CONTENT_EXTENSIONS:
        click.echo(
            f"Error: refusing to write report with a '{p.suffix}' extension "
            f"(reserved for Ableton content)",
            err=True,
        )
        sys.exit(1)

    for parent in p.parents:
        base = parent.name
        if base == "Backup" or base == ".alscan":
            click.echo(
                f"Error: refusing to write report inside the '{base}' directory",
                err=True,
            )
            sys.exit(1)

    if p.exists():
        click.echo(
            f"Error: output file already exists: {p}\n"
            f"  Delete it manually or use --output to write to a different location.",
            err=True,
        )
        sys.exit(1)

    return p


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

    if recursive and output:
        click.echo("Error: --output is not supported with --recursive", err=True)
        sys.exit(1)

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
    als_file = _resolve_als_path(path)
    if als_file is None:
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

    def _write(dest: Path, content: str) -> None:
        try:
            _atomic_write_report(dest, content)
        except OSError as e:
            click.echo(
                f"Error: could not write report to {dest} — {e}",
                err=True,
            )
            click.echo("  Report was not written. No fallback was attempted.", err=True)

    if fmt == "json":
        text = generate_json_report(result, pretty=pretty)
        if output_path:
            dest = _safe_report_output(output_path, als_file)
            _write(dest, text)
        else:
            click.echo(text)
    elif fmt == "html":
        html = generate_html_report(result)
        if output_path:
            dest = _safe_report_output(output_path, als_file)
        else:
            dest = _safe_report_output(
                str(als_file.parent / "alscan-report.html"), als_file,
            )
        _write(dest, html)
        if dest.exists():
            click.echo(f"HTML report written to: {dest}", err=True)
        if open_browser and dest.exists():
            import webbrowser
            webbrowser.open(dest.as_uri())
    else:
        text = print_terminal_report(result, verbose=verbose)
        if output_path:
            dest = _safe_report_output(output_path, als_file)
            _write(dest, text)
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


# ---------------------------------------------------------------------------
# Versioning commands (v0.3)
# ---------------------------------------------------------------------------

def _resolve_als_path(path: str) -> Path | None:
    """Resolve *path* to a single .als file.

    Returns the Path if found.  Prints an error and returns None on
    failure (callers should return / sys.exit accordingly).
    """
    als = find_als_file(path)
    if als is not None:
        return als

    p = Path(path).resolve()
    if p.is_dir():
        als_files = list(p.glob("*.als"))
        if len(als_files) > 1:
            click.echo(
                f"Multiple .als files found at: {path}\n"
                f"  Specify one: alscan <command> \"{path}/<filename>.als\"",
                err=True,
            )
            return None
    click.echo(f"Could not find a .als file at: {path}", err=True)
    return None


def _resolve_als(path: str) -> Path:
    """Resolve *path* to a single .als file or exit."""
    als = _resolve_als_path(path)
    if als is None:
        sys.exit(1)
    return als


def _load_any(path: str) -> Snapshot:
    p = Path(path).resolve()
    if p.is_dir():
        click.echo(
            "Expected an .als project file or alscan snapshot .json file, "
            f"but received a directory: {p}",
            err=True,
        )
        sys.exit(1)
    if p.suffix == ".json":
        try:
            snap = load_snapshot(p)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            click.echo(f"Error reading snapshot {p}: {e}", err=True)
            sys.exit(1)
        if snap.format_version != SNAPSHOT_FORMAT_VERSION:
            click.echo(
                f"Unsupported snapshot format version '{snap.format_version}' "
                f"(expected '{SNAPSHOT_FORMAT_VERSION}')",
                err=True,
            )
            sys.exit(1)
        return snap
    try:
        return build_snapshot(parse_als(p))
    except Exception as e:
        click.echo(f"Error parsing {p}: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=str, required=True)
def snapshot(path: str) -> None:
    """Capture a snapshot of a project's structure."""
    als_file = _resolve_als(path)
    try:
        proj = parse_als(als_file)
    except Exception as e:
        click.echo(f"Error parsing {als_file}: {e}", err=True)
        sys.exit(1)
    try:
        dest = save_snapshot(proj, als_file.parent)
    except Exception as e:
        click.echo(f"Error saving snapshot: {e}", err=True)
        sys.exit(1)
    click.echo(f"Snapshot saved: {dest}")


@cli.command()
@click.argument("path_a", type=str, required=True)
@click.argument("path_b", type=str, required=True)
def diff(path_a: str, path_b: str) -> None:
    """Compare two projects or snapshots.

    Compares structural metadata (tempo, time signature, locators,
    track layout, track names, device/clip counts).  Does NOT compare
    automation, MIDI notes, audio content, routing, send levels, or
    plugin parameter values.

    Arguments may be paths to .als files or snapshot .json files.
    """
    snap_a = _load_any(path_a)
    snap_b = _load_any(path_b)
    result = diff_snapshots(snap_a, snap_b)

    if not result.has_changes:
        click.echo("No differences found in structural metadata.")
        return

    click.echo(f"Diff: {result.project_a} vs {result.project_b}")
    click.echo()

    if result.tempo_changed:
        click.echo(f"  Tempo: {result.tempo_before} BPM -> {result.tempo_after} BPM")

    if result.time_sig_changed:
        click.echo(f"  Time Sig: {result.ts_before[0]}/{result.ts_before[1]} -> {result.ts_after[0]}/{result.ts_after[1]}")

    if result.locators_changed:
        click.echo()
        click.echo("  Locator changes:")
        for loc in result.added_locators:
            click.echo(f'    + "{loc["name"]}" at {loc["time"]:.1f}')
        for loc in result.removed_locators:
            click.echo(f'    - "{loc["name"]}" at {loc["time"]:.1f}')

    if result.track_changes:
        click.echo()
        click.echo("  Track changes:")
        for tc in result.track_changes:
            sym = {"added": "+", "removed": "-", "modified": "~", "unchanged": " "}[tc.kind]
            click.echo(f"    {sym} [{tc.track_id}] {tc.name}")
            for d in tc.details:
                click.echo(f"        {d}")


@cli.command()
@click.argument("path", type=str, required=True)
def log(path: str) -> None:
    """Show snapshot history for a project."""
    als_file = _resolve_als(path)
    snaps = find_snapshots(als_file.parent)
    if not snaps:
        click.echo(f"No snapshots found for {als_file.parent.name}")
        return

    from datetime import datetime
    click.echo(f"Snapshot history for {als_file.parent.name}:")
    click.echo()
    count = 0
    for snap_path in snaps:
        try:
            snap = load_snapshot(snap_path)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            click.echo(f"  ! {snap_path.name}: {e}", err=True)
            continue
        count += 1
        ts = datetime.fromtimestamp(snap.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"  {count}. {ts}  ({snap.tempo} BPM, {snap.track_count} tracks, {snap.device_count} devices)")

    click.echo()
    click.echo(f"  {count} snapshot(s) total")
