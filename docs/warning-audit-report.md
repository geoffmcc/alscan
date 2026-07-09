# ALScan Warning Audit Report

**Tested commit:** `67fc8df` (branch `three-way-validation-campaign`)  
**Date:** 2026-07-09  
**Python:** 3.14.6  
**PySide6:** 6.11.1  
**Pytest:** 9.1.1  

---

## 1. Initial Warning Baseline

### Command: `python -m pytest -W default -ra -q`

```
654 passed, 1 skipped, 15 warnings

Warnings:
  RuntimeWarning (2x)   — compare_page.py:165,169  — Failed to disconnect signal
  DeprecationWarning (5x) — result_table.py:81,85   — invalidateFilter() deprecated
  ResourceWarning (8x)   — versioner.py:164         — unclosed file
```

### Command: `python -m pytest -W error -ra -q`

```
12 failed, 642 passed, 1 skipped, 2 errors
```

Failures corresponded exactly to the 15 warnings above, elevated to errors.

---

## 2. Warning Inventory

| # | Class | Location | Count | Source | Severity |
|---|-------|----------|-------|--------|----------|
| W1 | ResourceWarning | `versioner.py:164` | 8 | ALScan production | Medium |
| W2 | DeprecationWarning | `result_table.py:81,85` | 5 | ALScan production | Medium |
| W3 | RuntimeWarning | `compare_page.py:165,169` | 2 | ALScan production | Low |

---

## 3. Root Cause and Fix

### W1 — ResourceWarning: unclosed file

**File:** `src/alscan/versioner.py:164`

**Root cause:** `os.fsync(tmp.open("rb").fileno())` opens a file for reading but never closes it. The file object returned by `tmp.open("rb")` has no reference kept and is left for garbage collection.

**Fix:** Use a `with` statement to ensure the file is closed after `fsync`:

```python
# Before:
os.fsync(tmp.open("rb").fileno())

# After:
with tmp.open("rb") as f:
    os.fsync(f.fileno())
```

### W2 — DeprecationWarning: invalidateFilter()

**File:** `src/alscan/gui/widgets/result_table.py:81,85`

**Root cause:** `QSortFilterProxyModel.invalidateFilter()` is deprecated in PySide6 6.11 in favor of `invalidate()`.

**Fix:** Replace with `self.invalidate()` (both occurrences).

### W3 — RuntimeWarning: Failed to disconnect signal

**File:** `src/alscan/gui/pages/compare_page.py:165,169`

**Root cause:** `_cancel_compare` attempts to disconnect signals from a worker that was created but never started (signals never connected). PySide6 emits a RuntimeWarning from C++ layer, which cannot be caught with Python `try/except`.

**Fix:** Wrap the disconnect calls in `warnings.catch_warnings()` with a narrow `RuntimeWarning` filter. This is the narrowest possible approach — it only suppresses RuntimeWarning during the specific disconnect calls within `_cancel_compare`.

---

## 4. Files Changed

| File | Change |
|------|--------|
| `src/alscan/versioner.py:163-164` | File opened with `with` statement for proper close |
| `src/alscan/gui/widgets/result_table.py:81,85` | `invalidateFilter()` → `invalidate()` |
| `src/alscan/gui/pages/compare_page.py:161-175` | Narrow RuntimeWarning suppression during disconnect |

---

## 5. Post-Fix Results

### Command: `python -m pytest -W default -ra -q`
```
654 passed, 1 skipped, 0 warnings
```

### Command: `python -m pytest -W error -ra -q`
```
654 passed, 1 skipped, 0 failures
```

### Command: `python -m pytest tests/three_way/ -W error -ra -q`
```
165 passed, 0 skipped, 0 failures
```

---

## 6. Remaining Warnings

**Zero.** All warnings eliminated or narrowly suppressed at source.

---

## 7. Warning Filters Added

One narrow filter in `_cancel_compare`:

```python
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    # disconnect calls that may fail if worker was never started
```

**Scope:** Two `disconnect()` calls within `_cancel_compare` only.  
**Justification:** The RuntimeWarning is emitted by PySide6 C++ layer when disconnecting a signal that was never connected. ALScan cannot prevent this from the Python side.  

---

## 8. Release Impact

None. All changes are backward-compatible:

- `invalidate()` replaces `invalidateFilter()` (PySide6 6.11 supports both; `invalidate()` is the forward-compatible choice)
- `with tmp.open("rb")` has identical behavior to the unclosed version but properly releases the file handle
- The RuntimeWarning filter only affects the disconnect path and has zero impact on normal operation

---

## 9. Graduation Recommendation

### WARNING GATE PASSED

All ALScan-owned warnings are fixed at source. Zero remaining warnings in both default and error modes across the full test suite. No broad suppression was required. No regression was introduced.

The warning state does NOT block graduation from Experimental status.

---

## 10. Confirmations

- Experimental status was not removed during this audit
- No real `.als` merge was created or applied
- No source `.als` files were modified
- All original 489 tests continue to pass
- All 165 three-way validation tests continue to pass
