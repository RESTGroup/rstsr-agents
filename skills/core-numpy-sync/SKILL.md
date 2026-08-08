---
name: core-numpy-sync
description: Semi-automatically detect when NumPy's test surface changes and flag rstsr-core parity tests for re-translation. Run when bumping the pinned NumPy version. Agent-driven, not a bare script.
---

# core-numpy-sync: detect NumPy test-surface drift

Run when the pinned NumPy version (in the header of
`rstsr-core/tests/tracking/numpy_coverage.csv` and `numpy_differences.md`) is bumped.
This is an **agent workflow**, not a fully-automatic script - NumPy changes need human
judgment to re-translate. No auto-translation of Python to Rust happens here.

## Inputs

- Pinned NumPy checkout, at a tagged version, path configurable (commonly
  `../other-repos/numpy`, checked out at the new tag).
- `rstsr-core/tests/tracking/numpy_coverage.csv` (the current checklist).

## Steps

1. **Enumerate NumPy's current test functions** for the tracked surface
   (`_core/tests/` + `lib/tests/`). The robust way is
   `pytest --collect-only -q` from the NumPy checkout, which yields pytest nodeids
   (`path::Class::method`, possibly parametrized). Fall back to AST/regex parsing of
   the `.py` files only if pytest is unavailable.
2. **Diff against the checklist:**
   - **New** NumPy functions (in NumPy, not in CSV) -> propose rows with status
     `not-applicable` (no rstsr analog) or `todo` (analog exists, needs translation).
   - **Removed** NumPy functions (in CSV, not in NumPy) -> mark the row `removed`,
     note the version.
   - **Renamed/moved** -> match by best effort (method name + neighboring class),
     update the path, note the rename.
3. **Detect content drift on `transferred` rows.** Recompute `numpy_source_hash`
   (hash of the NumPy test function's source text at the new version) and compare to
   the CSV's stored hash. Changed hash -> the translated rstsr test may be stale; flag
   it for re-review.
4. **Produce a drift report** (stdout or a temp file under `.claude/scratch/`):
   new / removed / renamed / drifted, with the NumPy diff context. This is the input
   to the human/AI re-translation pass.
5. **Hand off.** A human or the `core-test` skill then:
   - re-translates drifted `transferred` rows (updating the rstsr test + provenance
     line + `numpy_source_hash`),
   - decides `not-applicable` vs `todo` for new functions,
   - updates `numpy_differences.md` if a divergence appears or disappears.
6. **Update the version header** in both tracking files to the new pinned version
   only after the re-translation pass settles.

## Helpers

A small Python helper under `rstsr-core/tests/tracking/sync_numpy.py` may back steps
1-4 (the `gen_rand_vec.py` precedent means Python in the test tree is accepted). The
agent orchestrates it and interprets the output - the script does not edit tests.

## What this does not do

- Translate Python tests to Rust (that is `core-test`'s job).
- Run as CI. NumPy bumps are rare and need review; run manually on version bump.
