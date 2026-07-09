# Three-Way Analysis GUI Parity Audit

**Date:** 2026-07-09  
**Branch:** `three-way-validation-campaign`  

---

## Authoritative CLI/Core Capability Inventory

Inspected from `cli.py`, `services.py`, `merge/analysis.py`, `merge/plan.py`, `merge/inputs.py`.

| Capability | Core Support | CLI Support | Description |
|---|---|---|---|
| Base/Ours/Theirs inputs | `validate_three_way()` | `merge-plan`/`merge-report` args | Three file paths (.als or .json) |
| .als input | `parse_als()` | Yes | Gzipped XML parsing |
| Snapshot .json input | `load_snapshot_any()` | Yes | Snapshot v1 format |
| Mixed .als + .json | Rejected by `validate_three_way()` | Rejected (same type only) | All three must match |
| `--allow-unrelated` | `allow_unrelated` param | CLI flag | Skip lineage gating |
| `--allow-plausible` (partial) | `allow_plausible` param | Not exposed in CLI | Identity matching tolerance |
| `--output` flag | `validate_output_dest()` | CLI option | Write to file |
| No-clobber output | Yes | Yes | Rejects existing files |
| Reject .als output | Yes | Yes | Safety check |
| Reject backup/.alscan output | Yes | Yes | Safety check |
| JSON merge plan | `MergePlan.to_json()` | stdout or file | Structured JSON v2 |
| HTML conflict report | `render_merge_report()` | `--output` required | Standalone HTML |
| Exit codes (0/1/3) | N/A | Yes | 0=clean, 1=error, 3=conflicts |

---

## Parity Matrix

| Capability | Core | CLI | GUI Before | GUI After | Tests |
|---|---:|---:|---:|---:|---:|
| Base/Ours/Theirs selection | Yes | Yes | Yes | Yes | Yes |
| .als inputs | Yes | Yes | Yes | Yes | Yes |
| Snapshot inputs | Yes | Yes | Yes | Yes | Yes |
| Mixed inputs rejected | Yes | Yes | No | Yes | Yes |
| Allow unrelated | Yes | Yes | Yes | Yes | Yes |
| Allow plausible | Yes | No | No | Yes | Yes |
| Cancel analysis | N/A | N/A | No | Yes | Yes |
| ThreeWayDropArea | N/A | N/A | No | Yes | Yes |
| Input validation (UI) | Yes (service) | Yes (CLI) | No | Yes | Yes |
| Duplicate detection (UI) | Yes (service) | Yes (CLI) | No | Yes | Yes |
| Role explanation | N/A | Yes (help) | Partial | Yes | Yes |
| JSON plan export | Yes | Yes | Yes | Yes | Yes |
| HTML report export | Yes | Yes | Yes | Yes | Yes |
| Open HTML in browser | N/A | N/A | Yes | Yes | Yes |
| Open containing folder | N/A | N/A | No | Yes | Yes |
| No-clobber output | Yes | Yes | Yes | Yes | Yes |
| Collapse input after analysis | N/A | N/A | No | Yes | Yes |
| Result: conflicts | Yes | Yes | Yes | Yes | Yes |
| Result: auto-resolved | Yes | Yes | Yes | Yes | Yes |
| Result: identity matches | Yes | Yes | Yes | Yes | Yes |
| Result: track changes | Yes | Yes | Yes | Yes | Yes |
| Result: locator changes | Yes | Yes | Yes | Yes | Yes |
| Result: proposed order | Yes | Yes | Partial (buggy) | Yes | Yes |
| Source files untouched | Yes | Yes | Yes | Yes | Yes |
| Experimental badge | N/A | N/A | Yes (was) | No (removed) | Yes |
| No-merge disclaimer | N/A | N/A | Yes | Yes | Yes |
| No Apply/Restore buttons | N/A | N/A | Yes | Yes | Yes |
| Worker thread (non-blocking) | N/A | N/A | Yes | Yes | Yes |
| Error dialog (not raw traceback) | N/A | N/A | Yes | Yes | Yes |

---

## Gaps Fixed

1. **Cancel button** — Added to stop in-progress analysis.
2. **Allow plausible checkbox** — Passes `allow_plausible` to `create_merge_plan()`.
3. **ThreeWayDropArea** — Page now uses the dedicated `ThreeWayDropArea` class (was using generic `DropArea`).
4. **Input validation** — Pre-checks for empty paths, missing files, duplicate inputs, and mixed extensions before submitting to worker.
5. **Collapse input area** — After analysis completes, input area compacts to maximize result space, with "Change Sources" button to expand.
6. **Proposed track order display** — Fixed to use `entry["track"]["name"]` and `entry["position"]["after_base_track_id"]` etc. (was using wrong field names).
7. **Open containing folder** — After JSON/HTML export, prompts user to open the containing folder.
8. **Role explanation** — Added inline explanation of Base/Ours/Theirs roles.
9. **Change Sources button** — When input area is compacted, provides a way to un-compact.

## Remaining Observations (not blocking)

- `allow_plausible` is accepted by `validate_three_way()` but is "effectively unused in current gating" per code comments. The GUI exposes it for future use.
- Result tree uses older QTreeWidget style (not the newer CompareResultWidget used by the two-way compare page). This could be modernized but is not a parity gap.
- Mixed .als + .json inputs are rejected at the service level; the GUI also pre-validates this.
- No CLI flag exists for `allow_plausible`; if it becomes useful, a CLI flag should be added.

---

## Test Results

| Suite | Count | Result |
|-------|-------|--------|
| New GUI parity tests (automated) | 28 | 28 passed |
| Existing ThreeWayPage tests (automated) | 5 | 5 passed |
| three-way validation suite (automated) | 165 | 165 passed |
| Full suite `-W error` (automated) | 682 | 682 passed, 1 skipped |

All tests above are automated (pytest, pytest-qt). No manual testing was substituted for automated coverage.

## Verification

### Source-run smoke test (manual + programmatic)

Performed 2026-07-09:

| # | Workflow | Result |
|---|----------|--------|
| 1 | Page creates with all widgets | PASS |
| 2 | Base/Ours/Theirs roles clearly explained | PASS |
| 3 | Source selection via QLineEdit + Browse | PASS |
| 4 | ThreeWayDropArea accepts 3 files | PASS |
| 5 | Default options: allow_unrelated=False, allow_plausible=False | PASS |
| 6 | Analysis with snapshot fixtures produces correct MergePlan | PASS |
| 7 | Conflicts, auto-resolved, proposed order all present | PASS |
| 8 | allow_plausible flag passes through to create_merge_plan() | PASS |
| 9 | allow_unrelated with unrelated projects (rejected without, accepted with) | PASS |
| 10 | Cancel button appears during analysis, disconnects worker | PASS |
| 11 | Change Sources button visible after compaction | PASS |
| 12 | Input area collapses after analysis completes | PASS |
| 13 | JSON merge plan export (correct file, no-clobber) | PASS |
| 14 | HTML conflict report export (opens in browser) | PASS |
| 15 | Duplicate inputs rejected at UI validation level | PASS |
| 16 | Source file hashes unchanged after all operations | PASS |

### Packaged-build verification

| Check | Result |
|-------|--------|
| Build command | `pyinstaller --name alscan --onefile --noconsole --clean` |
| Build successful | YES |
| Generated artifact | `dist/alscan.exe` (52 MB) |
| CLI packaging functional (source) | Confirmed via `python -m alscan merge-plan --help` |
| Packaged EXE runtime smoke | NOT VERIFIED (PyInstaller EXE startup too slow for automated subprocess test) |


---

## GUI Parity Verdict

### GUI PARITY GATE PASSED

Every applicable CLI/core capability has a GUI equivalent. All defaults match. Every GUI control passes its value through to the shared service. JSON and HTML exports produce correct output. Source safety is verified. All tests pass with warnings as errors.

---

## Confirmation

- Experimental status was removed during graduation (2026-07-09)
- No merged `.als` was produced or applied
- Source projects remained unchanged throughout all testing
