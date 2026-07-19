# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
import sys
import time
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
from alscan.merge.guided import create_merge_session, build_merge_operations
from alscan.merge.manifest import MergeManifest
from alscan.merge.verification import verify_destination
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
@click.option("--search-paths", "-s", type=str, default="", help="Additional sample search paths (comma-separated)")
@click.option("--no-default-paths", is_flag=True, default=False, help="Do not search default Ableton library paths")
@click.option("--candidate-limit", type=int, default=5, help="Max candidates per missing sample (default: 5)")
def scan(path: str, format: str, browser: bool, output: str, recursive: bool,
         verbose: bool, exit_code: bool, pretty: bool, config: str,
         search_paths: str, no_default_paths: bool, candidate_limit: int) -> None:
    """Scan an Ableton Live project for health issues."""
    scan_path = Path(path).resolve()
    any_errors = False

    if candidate_limit < 0:
        click.echo("Error: --candidate-limit must be >= 0", err=True)
        sys.exit(1)

    check_config = _load_check_config(config, scan_path)
    _sp = _build_search_paths(search_paths, no_default_paths)

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
                r = _scan_single(str(proj_dir), format, browser, output, verbose, pretty, check_config, _sp, candidate_limit)
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
        result = _scan_single(path, format, browser, output, verbose, pretty, check_config, _sp, candidate_limit)
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


def _build_search_paths(search_paths_str: str, no_default_paths: bool) -> list[str] | None:
    paths = []
    if not no_default_paths:
        from alscan.search import known_sample_dirs
        for d in known_sample_dirs():
            paths.append(str(d))
    if search_paths_str:
        for p in search_paths_str.split(","):
            p = p.strip()
            if p:
                paths.append(p)
    return paths if paths else None


def _scan_single(path: str, fmt: str, open_browser: bool, output_path: str,
                 verbose: bool, pretty: bool = True,
                 check_config: CheckConfig | None = None,
                 search_paths: list[str] | None = None,
                 candidate_limit: int = 5) -> ScanResult | None:
    """Scan a single project and handle output formatting.

    Uses services.scan_project() for the actual scanning, then handles
    output formatting and file writing in the CLI layer.
    """
    from alscan.services import scan_project, ScanOptions, ScanError

    als_file = _resolve_als_path(path)
    if als_file is None:
        return None

    options = ScanOptions(
        format=fmt,
        verbose=verbose,
        pretty=pretty,
        check_config=check_config,
        search_paths=search_paths,
        candidate_limit=candidate_limit,
    )

    try:
        result = scan_project(als_file, options)
    except ScanError as e:
        click.echo(f"Error: {e}", err=True)
        return None
    except Exception as e:
        click.echo(f"Error scanning {als_file}: {e}", err=True)
        return None

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
            for pc in dc.param_changes:
                click.echo(f'        ~ "{pc["device_name"]}" parameters:')
                for param, vals in pc["changes"].items():
                    click.echo(f'            {param}: {vals["old"]} -> {vals["new"]}')


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


@cli.command(name="merge", context_settings={"ignore_unknown_options": True})
@click.argument("subcommand", type=str, required=True)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def merge_group(subcommand: str, args: tuple[str, ...]) -> None:
    """Guided merge workflow commands.

    Subcommands:
      guide BASE OURS THEIRS      Start a guided merge workflow
      plan   BASE OURS THEIRS     Generate a merge manifest (non-interactive)
      verify PLAN DEST            Verify a destination against a manifest
      resume PLAN                 Resume a saved merge session
    """
    if subcommand == "guide":
        _merge_guide(args)
    elif subcommand == "plan":
        _merge_plan_manifest(args)
    elif subcommand == "verify":
        _merge_verify(args)
    elif subcommand == "resume":
        _merge_resume(args)
    else:
        click.echo(f"Unknown merge subcommand: {subcommand}", err=True)
        click.echo("Available: guide, plan, verify, resume", err=True)
        sys.exit(1)


def _parse_three_args(args: tuple[str, ...]) -> tuple[str, str, str]:
    if len(args) < 3:
        click.echo("Error: requires three arguments: BASE OURS THEIRS", err=True)
        sys.exit(1)
    return args[0], args[1], args[2]


def _merge_guide(args: tuple[str, ...]) -> None:
    """Interactive guided merge workflow."""
    non_interactive = False
    clean_args = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--non-interactive":
            non_interactive = True
        elif arg == "--allow-unrelated":
            allow_unrelated_val = True
        elif arg == "--output" and i + 1 < len(args):
            pass
        else:
            clean_args.append(arg)

    allow_unrelated = "--allow-unrelated" in args
    base, ours, theirs = _parse_three_args(tuple(clean_args))

    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if non_interactive or not is_tty:
        _merge_guide_noninteractive(base, ours, theirs, allow_unrelated)
        return

    _merge_guide_interactive(base, ours, theirs, allow_unrelated)


def _merge_guide_noninteractive(base: str, ours: str, theirs: str, allow_unrelated: bool) -> None:
    click.echo("=== ALScan Guided Merge (non-interactive) ===", err=True)
    click.echo(f"Base:   {base}", err=True)
    click.echo(f"Ours:   {ours}", err=True)
    click.echo(f"Theirs: {theirs}", err=True)
    click.echo("", err=True)

    try:
        session, plan = create_merge_session(base, ours, theirs, allow_unrelated=allow_unrelated)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    preflight = session.safety_preflight
    if preflight:
        click.echo("--- Safety Preflight ---", err=True)
        click.echo(f"Path collision check: {'PASS' if preflight.path_collision_check else 'FAIL'}", err=True)
        click.echo(f"Version check:        {'PASS' if preflight.version_check else 'FAIL'}", err=True)
        click.echo(f"Lineage confidence:   {preflight.lineage_confidence}", err=True)
        for w in preflight.warnings:
            click.echo(f"  Warning: {w}", err=True)

    foundation = session.foundation_recommendation
    if foundation:
        click.echo("", err=True)
        click.echo("--- Foundation Recommendation ---", err=True)
        click.echo(f"Recommended: {foundation.recommended} (confidence: {foundation.confidence})", err=True)
        click.echo(foundation.explanation, err=True)
        for key, comp in foundation.comparisons.items():
            star = " (*)" if key == foundation.recommended else ""
            click.echo(
                f"  {comp.get('label', key)}{star}: actions={comp.get('estimated_manual_actions', '?')}, "
                f"risk={comp.get('risk_level', '?')}",
                err=True,
            )

    ops = build_merge_operations(session, plan, foundation.recommended if foundation else "ours")
    click.echo("", err=True)
    click.echo(f"--- Merge Plan: {len(ops)} operations ---", err=True)
    for op in ops:
        state_val = _op_state_label(op)
        click.echo(f"  {state_val} {op.title}", err=True)
    sys.exit(0)


def _op_state_label(op) -> str:
    state = op.state.value if hasattr(op.state, 'value') else str(op.state)
    return {"accepted": "[ACCEPTED]", "awaiting_decision": "[REVIEW]", "completed_manual": "[DONE]"}.get(state, f"[{state.upper()}]")


def _merge_guide_interactive(base: str, ours: str, theirs: str, allow_unrelated: bool) -> None:
    click.echo("=== ALScan Guided Merge ===", err=True)
    click.echo("", err=True)

    try:
        session, plan = create_merge_session(base, ours, theirs, allow_unrelated=allow_unrelated)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    preflight = session.safety_preflight
    if preflight and not preflight.passed():
        click.echo("WARNING: Safety preflight detected issues:", err=True)
        if not preflight.path_collision_check:
            click.echo("  - Source file collision detected", err=True)
        for d in preflight.path_collision_details:
            click.echo(f"    {d}", err=True)

    click.echo(f"Lineage confidence: {plan.lineage_confidence}", err=True)
    click.echo(f"Conflicts: {plan.conflict_count}, Reconcilable: {len(plan.auto_resolved)}", err=True)
    click.echo("", err=True)

    # Foundation selection
    foundation = session.foundation_recommendation
    if not foundation:
        click.echo("No foundation recommendation available.", err=True)
        sys.exit(1)

    click.echo("--- Choose Foundation ---", err=True)
    click.echo(f"Recommended: {foundation.recommended} (confidence: {foundation.confidence})", err=True)
    click.echo(foundation.explanation, err=True)
    click.echo("", err=True)
    click.echo("Candidates:", err=True)
    keys = list(foundation.comparisons.keys())
    for idx, key in enumerate(keys, 1):
        comp = foundation.comparisons[key]
        star = " (recommended)" if key == foundation.recommended else ""
        click.echo(
            f"  [{idx}] {comp.get('label', key)}{star} — "
            f"risk: {comp.get('risk_level', '?')}, "
            f"penalty: {comp.get('penalty_score', '?')}",
            err=True,
        )
    click.echo("  [b] Back  [q] Quit", err=True)

    choice = _prompt("Select foundation [1]: ", ["1", "2", "3", "b", "q"], default="1")
    if choice == "q":
        sys.exit(0)
    if choice == "b":
        sys.exit(0)
    try:
        idx = int(choice) - 1
        selected_key = keys[idx]
    except (ValueError, IndexError):
        selected_key = foundation.recommended

    session.selected_foundation = selected_key
    click.echo(f"Selected: {foundation.comparisons[selected_key].get('label', selected_key)}", err=True)
    click.echo("", err=True)

    operations = build_merge_operations(session, plan, selected_key)

    # Decision review
    click.echo("--- Review Decisions ---", err=True)
    for idx, op in enumerate(operations):
        if not op.required_user_decision:
            continue
        _interactive_decide(idx, len(operations), op)

    # Destination
    click.echo("", err=True)
    click.echo("--- Destination Preparation ---", err=True)
    click.echo("Open the selected foundation in Ableton Live.", err=True)
    click.echo("Use File > Save Live Set As to create a NEW destination Set.", err=True)
    click.echo("The destination must NOT be Base, Ours, or Theirs.", err=True)
    dest = _prompt("Destination path (or enter to skip): ", default="")
    if dest and Path(dest).exists():
        dp = Path(dest)
        sources = {Path(base), Path(ours), Path(theirs)}
        if dp.resolve() in {s.resolve() for s in sources}:
            click.echo("ERROR: Destination cannot be the same as a source file.", err=True)
        else:
            session.destination_path = str(dp)
            click.echo(f"Destination set: {dest}", err=True)

    # Manual execution
    click.echo("", err=True)
    click.echo("--- Perform Merge ---", err=True)
    for idx, op in enumerate(operations):
        if op.state.value in ("rejected", "deferred") if hasattr(op.state, 'value') else op.state in ("rejected", "deferred"):
            continue
        click.echo(f"Step {idx + 1}/{len(operations)}: {op.title}", err=True)
        if op.instructions:
            click.echo(f"  {op.instructions.description}", err=True)
        choices = ["[m] Mark complete", "[s] Skip", "[d] Defer", "[q] Save and quit", "[b] Back"]
        click.echo("  " + " | ".join(choices), err=True)
        c = _prompt("Action [m]: ", ["m", "s", "d", "q", "b"], default="m")
        if c == "q":
            _interactive_save_and_exit(session, operations, base, ours, theirs)
        elif c == "s":
            try:
                op.transition_to(OperationState.REJECTED)
            except ValueError:
                pass
        elif c == "d":
            try:
                op.transition_to(OperationState.DEFERRED)
            except ValueError:
                pass
        elif c == "m":
            try:
                if op.state == OperationState.ACCEPTED:
                    op.transition_to(OperationState.READY)
                if op.state == OperationState.READY:
                    op.transition_to(OperationState.IN_PROGRESS)
                if op.state == OperationState.IN_PROGRESS:
                    op.transition_to(OperationState.COMPLETED_MANUAL)
            except ValueError:
                pass
            click.echo("  Marked complete.", err=True)

    # Manifest save prompt
    click.echo("", err=True)
    click.echo("--- Save Session ---", err=True)
    if _prompt("Save merge manifest? [y/N]: ", ["y", "n"], default="n") == "y":
        out = _prompt("Output path [merge-manifest.json]: ", default="merge-manifest.json")
        manifest = MergeManifest.create(session, operations)
        hashes = {r: session.sources[r].sha256 for r in ("base", "ours", "theirs") if r in session.sources and session.sources[r]}
        manifest.source_hashes_captured = hashes
        try:
            from alscan.io_safety import atomic_write
            atomic_write(Path(out), manifest.to_json())
            click.echo(f"Manifest saved: {out}", err=True)
        except OSError as e:
            click.echo(f"Error saving: {e}", err=True)

    click.echo("", err=True)
    click.echo("Guided merge session complete. Run 'alscan merge verify <manifest> <destination.als>' to verify.", err=True)


def _interactive_decide(idx: int, total: int, op) -> None:
    from alscan.merge.operation import OperationState
    click.echo(f"  [{idx + 1}/{total}] {op.title}", err=True)
    if op.description:
        click.echo(f"    {op.description}", err=True)
    if op.base_value is not None:
        click.echo(f"    Base:   {op.base_value}", err=True)
    if op.ours_value is not None:
        click.echo(f"    Ours:   {op.ours_value}", err=True)
    if op.theirs_value is not None:
        click.echo(f"    Theirs: {op.theirs_value}", err=True)
    if op.recommended_result is not None:
        click.echo(f"    Recommended: {op.recommended_result}", err=True)
    if op.recommendation_rationale:
        click.echo(f"    Rationale: {op.recommendation_rationale}", err=True)

    click.echo("    [a] Accept  [s] Skip  [d] Defer  [q] Save and quit", err=True)
    c = _prompt("    Choice [a]: ", ["a", "s", "d", "q"], default="a")
    if c == "q":
        from alscan.merge.manifest import MergeManifest
        ops_list = [op]
        click.echo("    Saving and exiting...", err=True)
        sys.exit(0)
    elif c == "s":
        try:
            op.transition_to(OperationState.REJECTED)
        except ValueError:
            pass
    elif c == "d":
        try:
            op.transition_to(OperationState.DEFERRED)
        except ValueError:
            pass
    else:
        try:
            op.transition_to(OperationState.ACCEPTED)
        except ValueError:
            pass


def _interactive_save_and_exit(session, operations, base, ours, theirs) -> None:
    from alscan.merge.manifest import MergeManifest
    out = _prompt("Manifest path [merge-manifest.json]: ", default="merge-manifest.json")
    manifest = MergeManifest.create(session, operations)
    hashes = {r: session.sources[r].sha256 for r in ("base", "ours", "theirs") if r in session.sources and session.sources[r]}
    manifest.source_hashes_captured = hashes
    try:
        from alscan.io_safety import atomic_write
        atomic_write(Path(out), manifest.to_json())
        click.echo(f"Saved: {out}", err=True)
    except OSError as e:
        click.echo(f"Error saving: {e}", err=True)
    sys.exit(0)


def _prompt(msg: str, valid: list[str] | None = None, default: str = "") -> str:
    import sys as _sys
    try:
        value = input(msg).strip().lower()
    except (EOFError, KeyboardInterrupt):
        click.echo("", err=True)
        _sys.exit(0)
    if not value and default:
        return default
    if valid and value not in valid:
        return default
    return value


def _merge_plan_manifest(args: tuple[str, ...]) -> None:
    """Generate a merge manifest (non-interactive JSON export)."""
    import json as _json

    allow_unrelated = False
    output_path = ""
    clean_args = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--allow-unrelated":
            allow_unrelated = True
        elif arg == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            skip_next = True
        else:
            clean_args.append(arg)

    base, ours, theirs = _parse_three_args(tuple(clean_args))

    try:
        session, plan = create_merge_session(base, ours, theirs, allow_unrelated=allow_unrelated)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    foundation = session.foundation_recommendation
    ops = build_merge_operations(
        session, plan, foundation.recommended if foundation else "ours"
    )
    manifest = MergeManifest.create(session, ops)

    source_hashes = {
        role: session.sources[role].sha256
        for role in ("base", "ours", "theirs")
        if role in session.sources
    }
    manifest.source_hashes_captured = source_hashes

    json_str = manifest.to_json()

    if output_path:
        dest_p = Path(output_path)
        try:
            validate_output_dest(
                dest_p,
                [Path(base), Path(ours), Path(theirs)],
                reject_ableton_exts=True,
                reject_backup=True,
                reject_alscan=True,
            )
            _atomic_write_report(dest_p, json_str)
            click.echo(f"Merge manifest written to: {dest_p}", err=True)
        except (ValueError, FileExistsError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except OSError as e:
            click.echo(f"Error writing manifest: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(json_str)

    if plan.conflict_count > 0:
        sys.exit(3)


def _merge_verify(args: tuple[str, ...]) -> None:
    """Verify a destination .als against a merge manifest."""
    if len(args) < 2:
        click.echo("Error: requires two arguments: MANIFEST.json DESTINATION.als", err=True)
        sys.exit(1)

    manifest_path = args[0]
    dest_path = args[1]

    mp = Path(manifest_path)
    if not mp.exists():
        click.echo(f"Error: manifest not found: {manifest_path}", err=True)
        sys.exit(1)

    try:
        manifest = MergeManifest.from_json(mp.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError) as e:
        click.echo(f"Error reading manifest: {e}", err=True)
        sys.exit(1)

    session = manifest.get_session()
    source_paths = {}
    for role in ("base", "ours", "theirs"):
        if role not in session.sources:
            continue
        src = session.sources[role]
        if hasattr(src, "path"):
            source_paths[role] = src.path
        elif isinstance(src, dict):
            source_paths[role] = src.get("path", src.get("resolved", ""))
        else:
            source_paths[role] = str(src)
    source_hashes = manifest.source_hashes_captured

    try:
        report = verify_destination(dest_path, manifest, source_paths, source_hashes)
    except Exception as e:
        click.echo(f"Error during verification: {e}", err=True)
        sys.exit(1)

    click.echo("=== Verification Report ===", err=True)
    click.echo(f"Destination: {dest_path}", err=True)
    click.echo(f"Total operations: {report.total_operations}", err=True)
    click.echo(f"Passed:  {report.passed}", err=True)
    click.echo(f"Failed:  {report.failed}", err=True)
    click.echo(f"Partial: {report.partial}", err=True)
    click.echo(f"Unverifiable: {report.unverifiable}", err=True)
    click.echo(f"Blocked: {report.blocked}", err=True)
    click.echo(f"Source hashes stable: {'YES' if report.source_hashes_stable else 'NO'}", err=True)

    for detail in report.source_hash_details:
        if detail.get("status") == "changed":
            click.echo(
                f"  {detail.get('role')}: CHANGED — "
                f"expected {detail.get('expected_sha256', '')[:12]}..., "
                f"got {detail.get('observed_sha256', '')[:12]}...",
                err=True,
            )

    for error in report.errors:
        click.echo(f"Error: {error}", err=True)

    if report.failed > 0 or not report.source_hashes_stable:
        sys.exit(3)


def _merge_resume(args: tuple[str, ...]) -> None:
    """Resume a saved merge session from a manifest."""
    if not args:
        click.echo("Error: requires a manifest file: alsan merge resume plan.json", err=True)
        sys.exit(1)

    manifest_path = args[0]
    mp = Path(manifest_path)
    if not mp.exists():
        click.echo(f"Error: manifest not found: {manifest_path}", err=True)
        sys.exit(1)

    try:
        manifest = MergeManifest.from_json(mp.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError) as e:
        click.echo(f"Error reading manifest: {e}", err=True)
        sys.exit(1)

    session = manifest.get_session()
    operations = manifest.get_operations()

    click.echo(f"Resumed session: {session.session_id}", err=True)
    click.echo(f"Workflow state: {session.workflow_state}", err=True)
    click.echo(f"Selected foundation: {session.selected_foundation}", err=True)

    completed = sum(1 for op in operations if op.is_completed() or op.is_verified())
    total = len(operations)
    click.echo(f"Progress: {completed}/{total} operations completed", err=True)

    for op in operations:
        state_val = op.state.value if hasattr(op.state, 'value') else str(op.state)
        if state_val in ("accepted", "awaiting_decision"):
            click.echo(f"  [PENDING] {op.title}", err=True)
        elif op.is_completed():
            click.echo(f"  [DONE] {op.title}", err=True)


@cli.command(name="watch")
@click.argument("path", type=str, required=True)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show detailed scan output")
def watch_command(path: str, verbose: bool) -> None:
    """Watch project directory for changes and re-scan on save."""
    watch_dir = Path(path).resolve()
    if not watch_dir.is_dir():
        click.echo(f"Error: '{path}' is not a directory", err=True)
        sys.exit(1)

    from alscan.watch import watch_directory
    from alscan.services import ScanOptions

    options = ScanOptions(verbose=verbose)
    _last_reported: dict[str, set[str]] = {}

    def event_cb(proj_name, result, new_findings, resolved_findings):
        if result is None:
            click.echo(f"  [new] {proj_name}")
            return
        now_str = time.strftime("%H:%M:%S")
        click.echo(f"[{now_str}] {proj_name} — {len(result.errors)} errors, "
                   f"{len(result.warnings)} warnings, {len(result.info)} info")
        if verbose and new_findings:
            for f in new_findings:
                click.echo(f"  + {f}")
        if verbose and resolved_findings:
            for f in resolved_findings:
                click.echo(f"  - {f}")

    click.echo(f"Watching {watch_dir}")
    click.echo("Press Ctrl+C to stop.")

    try:
        cancelled = [False]

        def check_cancelled():
            return cancelled[0]

        watch_directory(path, event_cb=event_cb, cancelled_cb=check_cancelled,
                       options=options)
    except KeyboardInterrupt:
        click.echo()
        click.echo("Stopped.")


if __name__ == "__main__":
    cli()
