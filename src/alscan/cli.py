# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
import sys
import time
import inspect
from pathlib import Path

import click

from alscan import __version__
from alscan.io_safety import (
    ABLETON_CONTENT_EXTENSIONS,
    atomic_write as _atomic_write_report,
    validate_output_dest,
    validate_parent as _validate_parent,
)
from alscan.merge.analysis import build_merge_plan
from alscan.merge.inputs import validate_three_way
from alscan.merge.report import render_merge_report
from alscan.parser import parse_als
from alscan.project import find_als_file
from alscan.report.terminal import print_terminal_report, print_batch_summary
from alscan.report.html import generate_html_report
from alscan.report.json import generate_json_report
from alscan.report.csv import generate_csv_report, generate_csv_batch
from alscan.config import CheckConfig
from alscan.models import ScanResult
from alscan.versioner import (
    build_snapshot,
    save_snapshot,
    load_snapshot,
    find_snapshots,
    diff_snapshots,
    DeviceDiff,
    Snapshot,
    SNAPSHOT_FORMAT_VERSION,
)


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
@click.option("--format", "-f", type=click.Choice(["terminal", "json", "html", "csv"]), default="terminal",
              help="Output format (default: terminal)")
@click.option("--browser", "-o", is_flag=True, default=False, help="Open HTML report in browser")
@click.option("--output", "-O", type=str, default="", help="Write output to file")
@click.option("--recursive", "-r", is_flag=True, default=False, help="Scan all projects in a directory")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show detailed output")
@click.option("--exit-code", "-e", is_flag=True, default=False, help="Exit with code 1 if any errors found")
@click.option("--pretty", "-p", is_flag=True, default=True, help="Pretty-print JSON output")
@click.option("--config", "-c", type=str, default="", help="Path to .alscanrc config file")
def scan(path: str, format: str, browser: bool, output: str, recursive: bool,
         verbose: bool, exit_code: bool, pretty: bool, config: str) -> None:
    """Scan an Ableton Live project for health issues."""
    scan_path = Path(path).resolve()
    any_errors = False

    check_config = _load_check_config(config, scan_path)

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
                r = _scan_single(str(proj_dir), format, browser, output, verbose, pretty, check_config)
                if r and len(r.errors) > 0:
                    any_errors = True
                results.append(r)
            except Exception as e:
                click.echo(f"  Failed: {e}", err=True)

        if format == "terminal" and results:
            print_batch_summary(results)
        elif format == "csv":
            batch_results = []
            for i, proj_dir in enumerate(projects):
                if i < len(results) and results[i] is not None:
                    batch_results.append((proj_dir, results[i], None))
                else:
                    batch_results.append((proj_dir, None, "Scan failed"))
            click.echo(generate_csv_batch(batch_results))
    else:
        result = _scan_single(path, format, browser, output, verbose, pretty, check_config)
        if result and len(result.errors) > 0:
            any_errors = True

    if exit_code and any_errors:
        sys.exit(1)


def _load_check_config(config_path: str, project_path: Path) -> CheckConfig | None:
    if config_path:
        p = Path(config_path).resolve()
        if not p.is_file():
            click.echo(f"Warning: config file not found: {config_path}", err=True)
            return None
        try:
            return CheckConfig.from_file(p)
        except Exception as e:
            click.echo(f"Warning: could not read config: {e}", err=True)
            return None
    discovered = CheckConfig.discover(project_path)
    if discovered is not None:
        return discovered
    return None


def _invoke_check_cli(check, project, config: CheckConfig | None):
    try:
        sig = inspect.signature(check.func)
        if "config" in sig.parameters:
            return check.func(project, config=config)
    except (ValueError, TypeError):
        pass
    return check.func(project)


def _scan_single(path: str, fmt: str, open_browser: bool, output_path: str,
                 verbose: bool, pretty: bool = True,
                 check_config: CheckConfig | None = None) -> ScanResult | None:
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
            result = _invoke_check_cli(check, project, check_config)
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
    elif fmt == "csv":
        csv_text = generate_csv_report(result)
        if output_path:
            dest = _safe_report_output(output_path, als_file)
            _write(dest, csv_text)
            click.echo(f"CSV report written to: {dest}", err=True)
        else:
            click.echo(csv_text)
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


def _device_label(dev: dict) -> str:
    name = dev.get("name", "")
    ptype = dev.get("plugin_type")
    if ptype:
        return f"{name} ({ptype})"
    dtype = dev.get("device_type", "")
    if dtype and dtype != name:
        return f"{name} ({dtype})"
    return name


@cli.command()
@click.argument("path_a", type=str, required=True)
@click.argument("path_b", type=str, required=False, default=None)
@click.option("--snapshot", type=int, default=None, help="Index of snapshot to diff against (use 'log' to list)")
def diff(path_a: str, path_b: str | None, snapshot: int | None) -> None:
    """Compare two projects or snapshots.

    Compares structural metadata (tempo, time signature, locators,
    track layout, track names, device lists, volume, group assignment,
    colour, device/clip counts).  Does NOT compare automation, MIDI
    notes, audio content, routing, send levels, plugin parameter values,
    or plugin state.

    Arguments may be paths to .als files or snapshot .json files.
    """
    if path_b is None and snapshot is None:
        click.echo("Error: provide PATH_B or use --snapshot.", err=True)
        sys.exit(1)

    snap_a = _load_any(path_a)

    if snapshot is not None:
        als_file = _resolve_als(path_a)
        snaps = find_snapshots(als_file.parent)
        if not snaps:
            click.echo(f"No snapshots found for {als_file.parent.name}", err=True)
            sys.exit(1)
        if snapshot < 1 or snapshot > len(snaps):
            click.echo(
                f"Snapshot index {snapshot} out of range (1-{len(snaps)})",
                err=True,
            )
            sys.exit(1)
        snap_b = load_snapshot(snaps[snapshot - 1])
    else:
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

    if result.device_changes:
        click.echo()
        click.echo("  Device changes:")
        for dc in result.device_changes:
            click.echo(f"    ~ [{dc.track_id}] {dc.track_name}")
            for dev in dc.added:
                label = _device_label(dev)
                click.echo(f"        + \"{label}\"")
            for dev in dc.removed:
                label = _device_label(dev)
                click.echo(f"        - \"{label}\"")
            if dc.order_changed:
                click.echo("        ~ device order changed")
            for vc in dc.version_changes:
                click.echo(f'        ~ "{vc["device_name"]}" version: {vc["old_version"]} -> {vc["new_version"]}')


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


# ---------------------------------------------------------------------------
# Merge commands (v0.4)
# ---------------------------------------------------------------------------


@cli.command(name="merge-plan")
@click.argument("base", type=str, required=True)
@click.argument("ours", type=str, required=True)
@click.argument("theirs", type=str, required=True)
@click.option("--output", "-O", type=str, default="", help="Write merge plan to file")
@click.option("--allow-unrelated", is_flag=True, default=False,
              help="Allow analysis of structurally unrelated projects")
@click.option("--allow-plausible", is_flag=True, default=False,
              help="Allow plausible track identity matching when track IDs differ")
def merge_plan_command(base: str, ours: str, theirs: str,
                       output: str, allow_unrelated: bool,
                       allow_plausible: bool) -> None:
    """Analyze three project versions and produce a merge plan.

    BASE, OURS, and THEIRS must be paths to .als files or alscan
    snapshot .json files. All three must be the same type.

    The merge plan describes structural differences across the three
    versions, including auto-resolved changes and conflicts. No merged
    .als file is generated.

    This command does not modify any input file.
    """
    try:
        inputs = validate_three_way(base, ours, theirs,
                                    allow_unrelated=allow_unrelated,
                                    allow_plausible=allow_plausible)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    plan = build_merge_plan(inputs)

    json_str = plan.to_json()

    if output:
        dest = Path(output)
        try:
            validate_output_dest(
                dest,
                [Path(base), Path(ours), Path(theirs)],
                reject_ableton_exts=True,
                reject_backup=True,
                reject_alscan=True,
            )
        except (ValueError, FileExistsError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        try:
            _atomic_write_report(dest, json_str)
        except OSError as e:
            click.echo(
                f"Error: could not write merge plan to {dest} — {e}",
                err=True,
            )
            sys.exit(1)
        click.echo(f"Merge plan written to: {dest}", err=True)
    else:
        click.echo(json_str)

    if plan.conflict_count > 0:
        sys.exit(3)


@cli.command(name="merge-report")
@click.argument("base", type=str, required=True)
@click.argument("ours", type=str, required=True)
@click.argument("theirs", type=str, required=True)
@click.option("--output", "-O", type=str, required=True, help="Write HTML merge report to file")
@click.option("--allow-unrelated", is_flag=True, default=False,
              help="Allow analysis of structurally unrelated projects")
@click.option("--allow-plausible", is_flag=True, default=False,
              help="Allow plausible track identity matching when track IDs differ")
def merge_report_command(base: str, ours: str, theirs: str,
                         output: str, allow_unrelated: bool,
                         allow_plausible: bool) -> None:
    """Analyze three versions and render an HTML conflict report.

    BASE, OURS, and THEIRS must be paths to .als files or alscan
    snapshot .json files. All three must be the same type.

    The report is rendered entirely from the MergePlan v2 document model.
    It does not create merged metadata, modify .als files, apply changes,
    or reconstruct Ableton projects.
    """
    try:
        inputs = validate_three_way(base, ours, theirs,
                                    allow_unrelated=allow_unrelated,
                                    allow_plausible=allow_plausible)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    plan = build_merge_plan(inputs)
    html = render_merge_report(plan)

    dest = Path(output)
    try:
        validate_output_dest(
            dest,
            [Path(base), Path(ours), Path(theirs)],
            reject_ableton_exts=True,
            reject_backup=True,
            reject_alscan=True,
        )
    except (ValueError, FileExistsError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    try:
        _atomic_write_report(dest, html)
    except OSError as e:
        click.echo(
            f"Error: could not write merge report to {dest} — {e}",
            err=True,
        )
        sys.exit(1)
    click.echo(f"Merge report written to: {dest}", err=True)

    if plan.conflict_count > 0:
        sys.exit(3)


if __name__ == "__main__":
    cli()
