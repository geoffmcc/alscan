# ALScan Feature Roadmap Handoff

## 1. Repository State

| Field | Value |
|---|---|
| Version | 0.7.0 (pyproject.toml) |
| Branch | milestone-2-csv |
| Commit | cc3dfa5 (v0.7.1 + Milestone 1 merged) |
| Working tree | 3 new files, 3 modified (Milestone 2 uncommitted) |
| CLI/service tests | 758 passed, 1 skipped (environment-dependent) |
| GUI tests | 229 passed |
| Warnings-as-errors | Clean (`-W error`) |
| Packaging | Wheel builds successfully, includes csv.py |
| Date updated | 2026-07-09 |

## 2. Product Principles

- CLI and GUI are equal first-class interfaces over shared core services
- GUI never shells out to CLI — both call shared Python services/structured models
- Source `.als` files remain read-only
- No merged `.als` generation, no automatic repairs
- Professional UX in both interfaces
- Documentation must match reality; no fake or placeholder features
- No misleading merge, restore, repair, or backup claims
- Snapshots are structural metadata, not complete project backups

## 3. Roadmap Table

| Seq | Title | Status |
|-----|-------|--------|
| 1 | MIDI Note Content Health Checks | COMPLETED |
| 2 | CSV Export | COMPLETED |
| 3 | Result Signal and Classification Cleanup | NOT STARTED |
| 4 | Configurable Health-Check Thresholds | NOT STARTED |
| 5 | Plugin Version Tracking | NOT STARTED |
| 6 | Missing Sample Search and Candidate Suggestions | NOT STARTED |
| 7 | Watch Mode and Continuous Monitoring | NOT STARTED |
| 8 | Device Parameter Comparison | NOT STARTED |
| 9 | Per-Device Identity for Three-Way Analysis | NOT STARTED |
| — | Health trend dashboard | DEFERRED |
| — | Full `.als` merge or repair | DEFERRED |
| — | DAW-agnostic support | DEFERRED |
| — | Cloud accounts or sync | DEFERRED |

### Milestone 1 — MIDI Note Content Health Checks

- **User value:** Catch corrupted MIDI imports (empty clips, overlapping notes causing stuck notes), silent velocity bugs
- **Scope:** Three new checks using already-parsed `clip.notes` data
  - `empty_midi_clips` — MIDI clips with no playable notes (info)
  - `overlapping_notes` — same-pitch overlapping notes in same clip (warning)
  - `extreme_velocity` — near-silent or max-velocity notes (info)
- **Prerequisites:** None (parser already extracts MIDI notes)
- **Likely files:** `src/alscan/checks/midi.py` (new), `src/alscan/checks/__init__.py`, tests
- **CLI:** Auto-discovered via check registry; appears in scan, list-checks, batch, JSON/HTML
- **GUI:** Auto-discovered; appears in scan page, checks page, batch
- **Tests:** 33 new tests covering empty clips, populated clips, audio clips ignored, real overlaps, adjacent notes, different pitches, floating-point tolerance, duplicate notes, large clips, normal/edge velocities, registration, CLI output, JSON, HTML
- **Documentation:** README check list updated, check count updated (19→22)
- **Packaging:** No new dependencies; `midi.py` included in wheel
- **Risks:** Low — pure read-only checks on already-tested data
- **Completion evidence:** All three checks work, 33/33 tests pass, full suite 723 passed with `-W error`

### Milestone 2 — CSV Export

- **User value:** Spreadsheet analysis, CI/dashboard integration for batch scans
- **Scope:** `--format csv` for scan and batch; shared service layer; GUI export
- **Prerequisites:** None
- **Likely files:** `src/alscan/report/csv.py` (new), `cli.py`, `services.py`, GUI pages, tests
- **Risks:** Minimal — stdlib `csv`, no new dependencies

### Milestone 3 — Result Signal and Classification Cleanup

- **User value:** Less noisy summaries, accurate warning/error counts
- **Scope:** Omit unchanged locators from merge output; move snapshot-hash notice out of warnings; distinguish health findings from metadata notices
- **Prerequisites:** None
- **Likely files:** `src/alscan/merge/analysis.py`, `plan.py`, report modules, GUI
- **Risks:** Low — small targeted changes, well-tested paths

### Milestone 4 — Configurable Health-Check Thresholds

- **User value:** Tune checks to personal workflow; reduce false positives
- **Scope:** TOML config file, CLI `--config`, GUI settings page, per-check named settings
- **Prerequisites:** None
- **Risks:** Medium — check signature changes must be backward-compatible

### Milestone 5 — Plugin Version Tracking

- **User value:** Collaboration diagnostics; version mismatch detection
- **Scope:** Opportunistic version extraction from VST/VST3/AU XML; snapshot + diff integration
- **Prerequisites:** None
- **Risks:** Medium — version availability varies by plugin format

### Milestone 6 — Missing Sample Search

- **User value:** Actionable missing-sample findings
- **Scope:** Search configured/library paths; confidence-scored candidates; GUI browser
- **Prerequisites:** None
- **Risks:** Medium — performance on large libraries, false positives on common filenames

### Milestone 7 — Watch Mode

- **User value:** Continuous monitoring; instant feedback on save
- **Scope:** CLI `alscan watch`, GUI monitoring panel, debounce, stability checks
- **Prerequisites:** None
- **Risks:** Medium — Ableton multi-write save behavior, cross-platform filesystem events

### Milestone 8 — Device Parameter Comparison

- **User value:** Much more useful diffs; see what parameter actually changed
- **Scope:** Native device enabled/bypassed, named parameters, float tolerances, human-readable output
- **Prerequisites:** None
- **Risks:** Medium — parameter XML varies by device type

### Milestone 9 — Per-Device Identity for Three-Way Analysis

- **User value:** Accurate merge analysis when devices are reordered or edited
- **Scope:** Device identity heuristics, confidence levels, validation campaign
- **Prerequisites:** Milestones 3, 8
- **Risks:** Medium-High — heuristic matching complexity

## 4. Current Milestone

**Selected:** Milestone 3 — Result Signal and Classification Cleanup

**Why next:** Low effort, high impact on user trust. Removes noise from summaries without information loss. Three targeted changes: omit unchanged locators, reclassify snapshot-hash notice, distinguish metadata from health findings.

**Exact acceptance criteria:**
- Unchanged locators omitted from merge plan/report locator_changes
- Real locator changes (added/removed/moved/renamed) remain visible
- Snapshot-hash notice excluded from warning count
- Summary counts and cards reflect real health findings
- CLI, GUI, JSON, and HTML agree

## 5. Session History

### 2026-07-09 — Milestone 2: CSV Export

**Files changed:**
- `src/alscan/report/csv.py` (new) — CSV report module with formula-injection protection
- `src/alscan/cli.py` — added "csv" to format choices, CSV dispatch in _scan_single and recursive
- `src/alscan/services.py` — updated ScanOptions Literal, render_health_report for CSV
- `src/alscan/gui/pages/scan_page.py` — added "csv" to format combo, Export CSV button, _export_csv method
- `tests/test_csv_report.py` (new) — 35 tests
- `README.md` — added CSV output row, updated GUI export description
- `docs/feature-roadmap-handoff.md` — this document updated

**Behavior added:**
- `--format csv` for single and batch/recursive CLI scans
- `--format csv --output <file>` for file output
- GUI: Export CSV button on scan page, CSV file filter
- Formula-injection protection: leading `=`, `+`, `-`, `@` prefixed with `'`
- Deterministic column order: project, project_path, severity, check_name, title, message, location, suggestion, file_path
- Batch CSV: all projects in one CSV with project column, scan errors as rows
- Shared service layer: `render_health_report(result, "csv")`

**Exact commands run:**
```bash
python -m pytest -q -W error --tb=short          # 758 passed, 1 skipped
python -m build --wheel                           # Successful, csv.py included
```

**Exact test totals:**
- Pre-existing (post-M1): 723 passed, 1 skipped
- New: 35 tests (all pass)
- Total CLI/services: 758 passed, 1 skipped
- Total GUI: 229 passed (unchanged)

**Manual checks:**
- `alscan scan clean.als --format csv` → valid CSV with header + 1 row
- `alscan scan all_checks.als --format csv` → valid CSV with findings
- `alscan scan fixtures/ --recursive --format csv` → batch CSV
- `alscan scan clean.als --format csv --output test.csv` → file written
- `alscan scan --help` shows csv in format choices

**Packaging result:**
- Wheel builds successfully, `alscan/report/csv.py` present
- No new dependencies

**Remaining limitations:**
- No CSV export on batch scan GUI page (only scan page)
- Batch CSV always goes to stdout, no `--output` with `--recursive`

### 2026-07-09 — Milestone 1: MIDI Note Content Health Checks

**Files changed:**
- `src/alscan/checks/midi.py` (new) — three check functions
- `src/alscan/checks/__init__.py` — added `midi` import
- `tests/test_midi_checks.py` (new) — 33 tests
- `tests/test_alscan.py` — updated `test_list_checks_returns_all` expected set and `test_all_checks_triggered` docstring
- `tests/test_services.py` — updated check count 19→22
- `README.md` — updated health check table (3 new rows), feature counts, page counts
- `docs/feature-roadmap-handoff.md` (new) — this document

**Behavior added:**
- `empty_midi_clips` (info): detects MIDI clips with duration > 0 and zero notes
- `overlapping_notes` (warning): detects same-pitch notes where one starts before another ends; 1e-6 tolerance; aggregates per clip; truncates pitch list at 10
- `extreme_velocity` (info): detects notes at velocity 0 (silent), 1-9 (nearly silent), and 127 (maximum)

**Exact commands run:**
```bash
python -m pytest -q -W error --tb=short          # 723 passed, 1 skipped
python -m build --wheel                           # Successful, midi.py included
pip install -e .[dev]                             # Successful
python -m alscan list-checks                      # 22 checks listed
```

**Exact test totals:**
- Pre-existing: 690 passed, 1 skipped
- New: 33 tests (all pass)
- Total CLI/services: 723 passed, 1 skipped
- Total GUI: 229 passed (unchanged)

**Manual checks:**
- `alscan list-checks` shows 22 checks with all 3 new ones correct
- `alscan scan` works on fixture projects (no new false positives)
- HTML report generation includes new check names
- JSON report generation includes new check names

**Packaging result:**
- Wheel builds successfully, `alscan/checks/midi.py` present in wheel
- No new dependencies added

**Remaining limitations:**
- Overlap detection does not support MIDI channels (parser captures pitch/time/duration/velocity)
- Velocity thresholds (SILENT_VELOCITY=0, NEAR_SILENT_VELOCITY=10) are hardcoded (configurable in Milestone 4)
- No per-clip severity differentiation (all findings at same severity level)
- midi.py does not import from other check modules — zero coupling

**Next milestone:** Milestone 2 — CSV Export

## 6. Decision Log

### 2026-07-09 — MIDI checks architecture

- **Check module placement:** Created new `midi.py` rather than adding to existing modules (misc.py, performance.py). Rationale: MIDI content is a distinct domain; misc.py is already a grab-bag; separation keeps modules focused.
- **Overlap tolerance:** 1e-6 seconds. Based on floating-point precision of Ableton's stored note timings. Adjacent notes (exact boundary) are not flagged.
- **Velocity threshold: NEAR_SILENT_VELOCITY=10.** Velocity 10 is the cutoff below which notes are flagged as "nearly silent." Velocity 10-126 are considered normal. Rationale: velocity 0 is silent (flag), velocity 1-9 are nearly-inaudible (flag), velocity 10 is audible in most instruments.
- **Zero-duration clips ignored:** Ableton sometimes creates zero-duration placeholder MIDI clips. These are not flagged by `empty_midi_clips` (only clips with duration > 0 and zero notes are flagged).
- **Aggregation strategy:** `overlapping_notes` aggregates all overlaps in a clip into a single finding (lists affected pitches). `extreme_velocity` aggregates by clip. `empty_midi_clips` produces one finding per empty clip. This avoids flooding output on large projects.
- **Pitch truncation:** When >10 pitches have overlaps, only the first 10 are listed with "and N more." Prevents massive output on corrupted clips with many overlapping pitches.
- **No new version bump:** Milestone 1 does not warrant a version change. pyproject.toml remains at 0.7.0. Version bumps follow semantic reasoning at release time.
- **Branch strategy:** Feature branch `milestone-1-midi-checks`. Not merged yet; awaiting review before merging to main.
