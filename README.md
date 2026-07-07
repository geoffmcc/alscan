# alscan

**Ableton Live Project Health Scanner** — analyze, version, and compare `.als` project files from the command line.

## Installation

### Prebuilt binaries (recommended)

Download the latest release for your platform from the [Releases page](https://github.com/geoffmcc/alscan/releases):

| Platform | Download |
|----------|----------|
| Windows  | `alscan-x.x.x.exe` |
| macOS    | `alscan-x.x.x.dmg` |

These are standalone, self-contained builds — no Python or other dependencies required. Simply download and run.

### From source (developers)

```bash
git clone https://github.com/geoffmcc/alscan
cd alscan
pip install -e ".[dev]"

# Verify
alscan --version
alscan --help
```

To build a wheel without the source link:

```bash
pip install build
python -m build --wheel
pip install dist\alscan-*.whl        # Windows
pip install dist/alscan-*.whl         # macOS / Linux
```

## Quick Start

```bash
# Install (see installation above), then:
alscan --help

# Scan a project for issues
alscan scan "~/Ableton Projects/My Song/"

# Generate an HTML health report
alscan scan "~/Ableton Projects/My Song/" --format html --browser

# Capture a structural snapshot
alscan snapshot "~/Ableton Projects/My Song/"

# Compare two project versions
alscan diff "My Song.als" "My Song Backups/v2.als"

# Experimental: output a JSON merge plan
alscan merge-plan base.als ours.als theirs.als --output plan.json

# Experimental: render an HTML conflict report
alscan merge-report base.als ours.als theirs.als --output report.html
```

## Features

| Area | What it does |
|------|-------------|
| **Health scanning** | 19 checks: missing samples, broken plugins, frozen tracks, CPU-heavy plugins, duplicate samples, empty groups, warped clips, master chain plugins, and more |
| **Versioning** | Capture structural snapshots, diff across versions, view change history |
| **Conflict analysis** | Experimental three-way structural merge analysis with offline HTML reporting |
| **Rich terminal output** | Color-coded findings grouped by severity (error / warning / info) |
| **HTML reports** | Dark-themed static health report with summary cards and track listing |
| **JSON output** | Machine-readable output with `--format json` |
| **Exit codes** | `--exit-code` flag exits with code 1 when errors are found; merge-report uses 0/2/3/1 |
| **Batch scanning** | Scan all projects under a directory with `--recursive` |
| **Cross-platform** | Windows, macOS, Linux |

## Commands

| Command | Description | Status |
|---------|-------------|--------|
| `scan` | Run health checks on a project directory or `.als` file | Stable |
| `list-checks` | List all available health checks | Stable |
| `snapshot` | Save a structural metadata snapshot of a project | Stable |
| `diff` | Compare two `.als` files or snapshots | Stable |
| `log` | View snapshot history for a project | Stable |
| `merge-plan` | Analyze three versions and output a JSON merge plan | Experimental |
| `merge-report` | Analyze three versions and render an HTML conflict report | Experimental |

## Output Examples

### Terminal (default)

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

### JSON

```bash
alscan scan "My Song/" --format json --pretty --output report.json
```

Includes project metadata, track counts, and all findings with severity, check name, message, location, and suggestion.

### HTML Health Report

```bash
alscan scan "My Song/" --format html --browser
# → Writes alscan-report.html and opens it in your browser
```

Dark-themed static report with summary cards (error/warning/info counts), severity badges, project stats, and track listing table.

## Health Checks

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

## Versioning (snapshot / diff / log)

Capture structural metadata snapshots of your projects and compare them over time.

```bash
# Save a snapshot
alscan snapshot "My Song/"
# → Writes .alscan/snapshots/My Song-<timestamp>-<uuid>.json

# Compare two files or snapshots
alscan diff "My Song.als" "My Song Backups/v2.als"
alscan diff "My Song.als" "My Song/.alscan/snapshots/v1.json"
alscan diff "My Song/.alscan/snapshots/v1.json" "My Song/.alscan/snapshots/v2.json"

# View snapshot history
alscan log "My Song/"
```

> Snapshots capture **structural metadata only**: tempo, time signature, creator string, track list with device details and clip counts, volume, colour, group assignment, plugin references, and a structural fingerprint. No audio content.

> The `.alscan/snapshots/` directory is excluded from Git via `.gitignore`. The `Backup/` folder is excluded from recursive scanning.

### What `diff` shows

Tempo, time signature, locator, track layout, track names, volume, group assignment, colour, device lists (additions, removals, reordering), device and clip counts. Structural metadata only — not a complete Ableton project comparison.

## Merge Conflict Report (experimental)

> ⚠️ **Experimental.** This command analyzes structural differences but does not apply merges, write `.als` files, produce XML, or reconstruct projects.

```bash
alscan merge-report BASE OURS THEIRS --output report.html
```

`BASE`, `OURS`, and `THEIRS` may be `.als` files or alscan snapshot `.json` files — all three must be the same type.

Pass `--allow-unrelated` to analyze projects that do not share common ancestry (this will flag nearly everything as a conflict or addition).

### What it produces

An offline HTML report rendered from the MergePlan v2 document model:

- Source file labels and SHA-256 hashes
- Identity matches across all three versions
- Structural conflicts and auto-resolved changes
- Track-level changes (added, removed, modified, positional)
- Locator additions and removals
- Proposed track order
- Scope of analyzed fields

The report uses inline CSS only, no external network resources, and is safe for offline viewing.

### Privacy

Source file paths are reduced to basenames. Plugin-state data is redacted.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | No conflicts found (report still written) |
| `2` | `--output` not provided |
| `3` | Conflicts detected (report written) |
| `1` | Validation failure or I/O error |

### What it does NOT do

Create merged metadata, modify `.als` files, write XML, apply conflicts, interpret plugin state, or reconstruct Ableton projects.

## Merge Plan (experimental)

> ⚠️ **Experimental.** Same analysis engine as `merge-report`, but outputs a JSON merge plan instead of an HTML report.

```bash
alscan merge-plan BASE OURS THEIRS --output plan.json
```

Accepts the same inputs and `--allow-unrelated` flag as `merge-report`. The JSON output follows the MergePlan v2 schema and is intended for programmatic consumption or further tooling.

This command does not modify any input file.

## Platform Compatibility

| OS | Python install | Standalone binary |
|----|---------------|-------------------|
| Windows | Python 3.12+ via WSL | `.exe` on Releases |
| macOS | Manual testing needed | `.dmg` on Releases |
| Linux | Python 3.12+; CI-tested (Ubuntu) | Not provided |

Ableton Live does not run on Linux, but you can use `alscan` on a Linux server to scan or diff project files stored on a shared drive.

**Known limitations**:
- Atomic file operations (`os.link`) require both paths on the same filesystem volume
- Network filesystems (NFS, SMB) may not guarantee atomic no-clobber writes
- Long paths (>260 chars) on Windows are not handled — use Python 3.12+ or short paths
- `Path.is_junction()` (Windows) requires Python 3.12

## Privacy & Security

Reports and snapshots contain metadata that may include sensitive information:

- **Plugin file paths** can reveal your username (e.g., `C:\Users\…`)
- **Track names** may reflect unreleased song titles, client names, or working titles
- **Creator field** shows the Ableton Live registration name

Review reports before sharing them. Merge reports also show source labels, hashes, and structural change details. Snapshots are stored locally in `.alscan/` and excluded from Git via `.gitignore`.

## Uninstall

```bash
pip uninstall alscan
```

If you used a standalone PyInstaller build (macOS `.dmg` or Windows `.exe`), simply delete the downloaded file — it is fully self-contained and makes no system modifications.

## Development

```bash
git clone https://github.com/geoffmcc/alscan
cd alscan
pip install -e ".[dev]"

# Run tests
pytest

# Regenerate test fixtures
python -m tests.fixtures.generate

# Build
python -m build
```

## Roadmap

- **v0.1** ✅ Project health scanning
- **v0.2** ✅ Extended checks, JSON output, exit codes
- **v0.3** ✅ Project versioning (snapshot / diff / log)
- **v0.4** 🚧 Experimental three-way structural analysis and offline conflict reporting

## License

MIT
