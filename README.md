# alscan

**Ableton Live Project Health Scanner** — analyze, version, and merge `.als` project files from the command line.

```bash
pip install alscan
alscan scan "My Song/"
```

## Features

- **Structural change tracking** — snapshot project structure, diff across versions, view change history
- **19 health checks** — missing samples, broken plugins, frozen tracks, CPU-heavy plugins, duplicate samples, empty groups, warped clips, master chain plugins, and more
- **Rich terminal output** — color-coded findings grouped by severity (error/warning/info)
- **HTML report** — dark-themed static report with summary cards and track listing
- **JSON output** — machine-readable output with `--format json`
- **Exit codes** — `--exit-code` flag exits with code 1 when errors are found
- **Cross-platform** — Windows, macOS, Linux
- **Batch scanning** — scan all projects under a directory with `--recursive`
- **Extensible** — add custom checks with the `@register` decorator

## Quick Start

```bash
# Scan a single project directory
alscan scan "~/Ableton Projects/My Song Project/"

# Generate an HTML report
alscan scan "~/Ableton Projects/My Song Project/" --format html

# Open the report in your browser
alscan scan "~/Ableton Projects/My Song Project/" --format html --browser

# Scan all projects under a folder
alscan scan "~/Ableton Projects/" --recursive

> **Note**: `--output` is not supported with `--recursive`. Each project's report is printed to stdout only.

# List all available checks
alscan list-checks

# Capture a project snapshot
alscan snapshot "~/Ableton Projects/My Song Project/"

# Compare two .als project files
alscan diff "My Song.als" "My Song Backups/v2.als"

# View snapshot history
alscan log "My Song Project/"
```

> **Troubleshooting**: If `alscan scan <directory>` says "Multiple .als files found", the directory contains more than one project. Pass the explicit path to the `.als` file instead: `alscan scan "~/Ableton Projects/My Song/My Song.als"`.

## Output Example

```
alscan v0.3.0 — Scan Report
═══════════════════════════════════════
Project: My Song Project
Creator: Ableton Live 12.4.2 · 120.0 BPM
9 audio · 12 midi · 4 group · 4 return · 0 master

  ╷
  │  ERRORS  │  2
  │ WARNINGS │  3
  │    INFO  │ 24
  ╵

──────────────────── Errors ────────────────────
  ✗ Missing Sample: "Loop_03_100bpm_C#maj.WAV"
    not found at: C:\Users\...\Loop_03_100bpm_C#maj.WAV
    → Re-link the sample in Ableton or use Collect All and Save

  ✗ Missing Plugin: "Serum"
    not found at: C:\Program Files\VST\Serum.dll
    → Install the missing plugin or update its path

─────────────────── Warnings ───────────────────
  ⚠ Frozen Track with External Plugins
    Track "Synth" has 2 external plugin(s) while frozen
    → Unfreeze to verify plugins are available
```

## Checks

| Check | Severity | Description |
|-------|----------|-------------|
| `missing_samples` | error | Audio files referenced but not found on disk |
| `broken_plugins` | error | VST/AU plugins referenced but not found on disk |
| `frozen_plugins` | warning | Frozen tracks with plugins that may not re-open |
| `frozen_tracks` | warning | Tracks that are frozen |
| `empty_tracks` | info | Tracks with no clips |
| `unused_returns` | warning | Return tracks that appear unused |
| `empty_groups` | info | Group tracks with no children |
| `unnamed_tracks` | info | Tracks with no user-assigned name |
| `duplicate_track_names` | info | Tracks sharing the same name |
| `duplicate_samples` | info | Same sample used across multiple tracks |
| `missing_pack_samples` | info | Live Pack samples that may not be installed |
| `high_device_count` | info | Tracks with unusually many devices |
| `cpu_heavy_plugins` | info | Known CPU-intensive plugins |
| `high_latency_plugins` | info | Plugins known for introducing high latency |
| `unfrozen_heavy_tracks` | info | Tracks with many clips/devices that could be frozen |
| `warped_clips` | info | Audio clips with warping enabled |
| `master_chain_plugins` | info | Master track has plugin devices |
| `extreme_tempo` | info | Project tempo outside 40–200 BPM range |
| `no_locators` | info | Project has no locators/markers |

## HTML Report

Use `--format html --browser` to generate a dark-themed static HTML report in the project directory:

```
alscan scan "My Song/" --format html --browser
# → Writes alscan-report.html and opens it in your browser
```

The report shows summary cards (errors/warnings/info counts), all findings with severity badges, a project stats grid, and a full track listing table.

## JSON Output

Use `--format json` for machine-readable output:

```bash
alscan scan "My Song/" --format json
```

Combine with `--pretty` (default: on), `--exit-code`, and `--output`:

```bash
alscan scan "My Song/" --format json --output report.json --exit-code
echo $?  # 0 if no errors, 1 if errors found
```

The JSON includes project metadata, track counts, and all findings with severity, check name, message, location, and suggestion.

## Versioning

Track your project's evolution with snapshot, diff, and log commands.

> **Note**: The `snapshot` command creates an `.alscan/snapshots/` directory in the project folder. This directory is excluded from Git via `.gitignore`.

```bash
# Save a structural snapshot of the project
alscan snapshot "My Song/"
# → Writes .alscan/snapshots/My Song-<timestamp>-<uuid>.json

# Compare two .als project files
alscan diff "My Song.als" "My Song Backups/v2.als"

# Compare a project against a previous snapshot
alscan diff "My Song.als" "My Song/.alscan/snapshots/My Song-20260706-abc123.json"

# Compare two snapshots
alscan diff "My Song/.alscan/snapshots/v1.json" "My Song/.alscan/snapshots/v2.json"

# → Shows: tempo, time signature, locator, track, device, and clip count changes
#   (structural metadata only — not a complete Ableton project comparison)

# View snapshot history
alscan log "My Song/"
# → Lists all snapshots with timestamps, BPM, track/device counts
```

Snapshots capture **structural metadata only**: project tempo/time sig/creator, track list with device/clip counts, plugin references, and a structural fingerprint (not audio content). The `Backup/` folder is excluded from recursive scanning.

## Privacy & Security

Reports and snapshots contain metadata that may include sensitive information:

- **Plugin file paths** can reveal your username (e.g., `C:\Users\…`)
- **Track names** may reflect unreleased song titles, client names, or working titles
- **Creator field** shows the Ableton Live registration name

Review reports before sharing them.  Snapshots are stored locally in `.alscan/` and are excluded from Git via `.gitignore`.

## Platform Compatibility

| OS         | Status                                       |
|------------|----------------------------------------------|
| Windows    | Tested via WSL; native PyInstaller builds    |
| macOS      | PyInstaller builds; manual testing needed    |
| Linux      | Supported for CI; Ableton does not run here  |

**Known limitations**:
- Atomic file operations (`os.link`) require both paths on the same filesystem volume
- Network filesystems (NFS, SMB) may not guarantee atomic no-clobber writes
- Long paths (>260 chars) on Windows are not handled — use Python 3.12+ or short paths
- `Path.is_junction()` (Windows) requires Python 3.12

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/geoffmcc/alscan
cd alscan
pip install -e ".[dev]"

# Run tests
pytest

# Regenerate test fixtures
python -m tests.fixtures.generate
```

## Roadmap

- **v0.1** ✅ Project health scanning
- **v0.2** ✅ Extended checks, JSON output, exit codes
- **v0.3** ✅ Project versioning (snapshot / diff / log) — [pending release](https://github.com/geoffmcc/alscan/pull/2)
- **v0.4** — Project merging (three-way merge)

## License

MIT
