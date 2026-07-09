# Changelog

All notable changes to ALScan will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
