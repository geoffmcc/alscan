# alscan

**Ableton Live Project Health Scanner** — analyze, version, and merge `.als` project files from the command line.

```bash
pip install alscan
alscan scan "My Song/"
```

## Features

- **15 health checks** — missing samples, broken plugins, frozen tracks, CPU-heavy plugins, duplicate samples, empty groups, and more
- **Rich terminal output** — color-coded findings grouped by severity (error/warning/info)
- **HTML report** — dark-themed static report with summary cards and track listing
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

# List all available checks
alscan list-checks
```

## Output Example

```
alscan v0.1.0 — Scan Report
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

## HTML Report

Use `--format html --browser` to generate a dark-themed static HTML report in the project directory:

```
alscan scan "My Song/" --format html --browser
# → Writes alsan-report.html and opens it in your browser
```

The report shows summary cards (errors/warnings/info counts), all findings with severity badges, a project stats grid, and a full track listing table.

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

- **v0.1** ✅ Project health scanning (current)
- **v0.2** — Extended checks, JSON output, batch scanning improvements
- **v0.3** — Project versioning (snapshot / diff / restore)
- **v0.4** — Project merging (three-way merge)

## License

MIT
