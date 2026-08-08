---
name: core-col-major-transfer
description: STUB - reserved for col-major rstsr-correctness tests (tests/col_major/). Col-major is NOT NumPy-parity; the transfer difficulties are undocumented. Design deferred.
---

# core-col-major-transfer: STUB (deferred)

This skill is a **placeholder**. The col-major test track is intentionally deferred -
see ADR-0002 and `test-conventions` §1.

## Why it is separate

- NumPy is row-major (C-order) by default. **Col-major tests are not NumPy-parity** -
  they test rstsr's own column-major convention (the Fortran/Julia convention). So they
  cannot be "transferred" from NumPy; they are rstsr-internal correctness tests.
- `col_major` is compile-time mutually exclusive with `row_major`, so col-major tests
  live in a separate entry binary (`entry_col_cpu.rs`, gated by the `col_major`
  feature), not mixed into the row-major entries.
- The only NumPy col-major coverage is the `order='F'` cases (e.g. in `reshape`), which
  *are* parity and stay in `core_func/` under the row-major authoring flow.

## What this skill will cover (when designed)

- How to author a col-major correctness test in `tests/col_major/`.
- The transfer/mapping difficulties from row-major behavior to col-major behavior,
  recorded in `tracking/numpy_differences.md` under the `col-major-transfer` tag.
- Whether a `col × Faer` entry is needed (currently deferred).

## Until then

Row-major parity work proceeds without this skill. Do not create `tests/col_major/`
contents yet - only the reserved directory exists.
