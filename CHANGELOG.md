# Changelog

All notable changes to ALScan will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.9.0] — 2026-07-10 (unreleased)

### Added
- **Guided Merge** — manual read-only merge workflow for combining divergent Ableton Live Set versions
  - Interactive CLI wizard with foundation selection, decision review, and manual execution tracking
  - 9-stage GUI wizard with session save/open/resume, destination validation, and verification
  - Merge session persistence via versioned `MergeManifest` JSON format
  - Foundation recommendation engine with penalty-based candidate scoring
  - Ordered merge plan generation from three-way analysis results
  - Destination verification engine (tempo, time sig, tracks, locators)
  - Source immutability enforcement with hash capture and recheck
  - Changed-source detection blocking stale session resumption
  - CLI/GUI manifest interoperability
- Pluggable automation executor architecture with `ALS_WRITING_ENABLED` safety flag
- Repository `.als` policy enforcement script (`scripts/check_als_policy.py`)
- Synthetic fixture ID allocator and pointee allocator for parser testing

### Changed
- Three-way analysis terminology: "auto-resolved" → "automatically reconcilable" in user-facing text
- Session state transitions now guarded with valid transition map
- `is_verified()` now returns `True` only for `VERIFICATION_PASSED`; `has_verification_result()` added for broader checks
- `atomic_publish` hardened against symlinks and cross-device links
- `version_is_supported` now checks both major and minor version

### Fixed
- `IdentityMatch.ours_track_id` / `.theirs_track_id` defaults changed from `0` (valid track ID) to `None`
- Manifest `from_json` properly warns on incompatible session data instead of silently swallowing TypeError
- `_deserialize_operation` raises clear error for unknown enum values instead of crashing with opaque TypeError
- `_redact_session` deep-copies source dicts to prevent mutation of live session data
- Safety preflight operations correctly report `unverifiable` instead of `pass`
- Locator move verification compares values before claiming pass
- Empty track names return `unverifiable` instead of passing removal checks
- `_check_source_stability` reports `no_captured_hash` when captured hash is missing
- Parser handles `<Color Value="N"/>` (Live 12) with fallback to `<ColorIndex Value="N"/>`

### Security
- Automatic `.als` writing is disabled: `ALS_WRITING_ENABLED = False` with registration-time enforcement
- Executor registry rejects non-manual executors while writing is disabled
- No CLI flag, GUI control, manifest field, or environment variable can bypass the safety flag

## [0.8.0] — 2026-07-09

### Added
- MIDI note content health checks: `empty_midi_clips`, `overlapping_notes`, `extreme_velocity`
- CSV export format (`--format csv`) for CLI scan and batch, plus GUI Export CSV button
- Configurable health-check thresholds via `.alscanrc` TOML config file and `--config` CLI flag
- Plugin version tracking: VST3/AU version extraction, version-including snapshots, version change detection in diffs
- Missing sample search: `--search-paths` CLI option, confidence-ranked candidates, auto-discovery of Ableton Library paths
- Watch mode: `alscan watch <dir>` for continuous project monitoring with debounce and new/resolved finding detection
- Device parameter comparison: Device On/named parameters extracted from native devices, float-tolerant comparison in diffs
- Per-device identity for three-way merge analysis: devices matched across versions by signature, auto-resolved single-branch changes

### Changed
- Unchanged locators omitted from merge plan/report output
- Snapshot-hash compatibility notice moved from warnings to `notices` metadata field
- Platform compatibility: Python runs natively on Windows (WSL not required)
- Removed dead GUI format selector in scan page; dedicated export buttons provide clearer workflow

### Fixed
- `Finding` import in service layer (latent runtime crash when checks fail)
- `--candidate-limit` CLI option now properly propagated through the scan pipeline
- AU plugin subtype identifiers no longer misrepresented as version numbers
- Sample search now consistently case-insensitive on all platforms
- Various dead code and unused imports removed
- Duplicated `_invoke_check` logic consolidated into shared service layer
- Brittle hardcoded check count tests replaced with name-based assertions

### Security
- Formula injection protection in CSV export: leading `=`, `+`, `-`, `@` prefixed with `'`

## [0.7.1] — 2026-07-09

### Fixed
- Check failure surfacing in scan results
- CLI/GUI parity for cross-platform open_folder
- Finding deduplication in batch scans

## [0.7.0] — 2026-07-09

### Added
- Three-way merge analysis graduated from Experimental status
- Validation campaign with 165 dedicated tests
- GUI parity audit (28 parity items)
- About dialog

### Fixed
- Zero warnings with `-W error` flag

## [0.6.0] — 2026-07-08

### Changed
- Redesigned compare result UI with human-readable diff presentation

## [0.5.0] — 2026-07-08

### Added
- PySide6 desktop GUI with 8-page navigation
- Catppuccin dark/light/system theme support

### Changed
- Relicensed to GPL-3.0-only

## [0.4.1] — 2026-07-07

### Fixed
- Tempo reading from MasterTrack/ArrangerAutomation for Live 12 format

## [0.4.0] — 2026-07-07

### Added
- Three-way structural merge analysis (experimental)
- MergePlan v2 document model
- Offline HTML merge conflict report renderer
- Deepened structural diff for tracks and devices

## [0.3.2] — 2026-07-06

### Added
- `--snapshot` option to `diff` command

## [0.3.1] — 2026-07-06

### Fixed
- Blank PyInstaller executable (missing `__main__` guard)
- Release metadata

## [0.3.0] — 2026-07-06

### Added
- Project versioning: `snapshot`, `diff`, `log` commands
- I/O safety: atomic writes, identity capture, stability checking
- Security hardening for report output
- Locator diff in project comparison

## [0.2.0] — 2026-07-05

### Added
- JSON output format (`--format json`)
- 4 new health checks
- Exit codes (`--exit-code`)
- Batch scanning improvements

## [0.1.0] — 2026-07-04

### Added
- Initial release: project health scanning
- 15 health checks for Ableton Live projects
- Terminal output with Rich formatting
- `.als` XML parser with secure defaults
