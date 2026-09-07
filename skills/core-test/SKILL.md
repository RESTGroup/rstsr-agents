---
name: core-test
description: Author a rstsr-core function's parity test (core_func/), doc test (doc_draft/), and API docstring. Rstsr-core only - BLAS-backend devices use a different strategy. Follows skill test-conventions.
---

# core-test: author parity test, doc test, and docstring

Refers to skill `test-conventions` for folder layout, entry binaries, `specify_test!`,
provenance format, tensor creation, and tracking hygiene. Read it first. Refers to
`cargo-inst` for compile/test commands.

**Scope:** rstsr-core functions only. **Not** for BLAS-backend device crates - they
have their own testing strategy and their own (future) skills.

## Must know

- RSTSR may be incorrect or behave differently from NumPy. If so, report it. **Never
  cheat by weakening the test target to make it pass.**
- A function's parity test (`core_func/`), doc test (`doc_draft/`), and docstring are
  authored together as one unit of work.

## Workflow

### Step 1 - Parity test (in `core_func/<category>/test_<func>.rs`)

1. **Find the NumPy test.** First locate the pinned NumPy checkout: read the
   path from the repository root's `AGENTS.local.md` (`Reference checkouts:`
   entry); if it is not recorded there, ask the user. Then look in
   `numpy/_core/tests` or `numpy/lib/tests` of that checkout. Identify the test
   function(s) covering this function.
2. **Translate** following `test-conventions` §4 (provenance header + commented-Python
   pairing). Module `numpy_<func>`, `FUNC = "numpy_<func>"`.
3. **If NumPy has no test** for this function, write a `custom_<func>` module with 2-10
   cases hitting the 1-3 edge cases that matter. `FUNC = "custom_<func>"`.
4. **Map NumPy functions to rstsr.** Check `rstsr-core/src/prelude_dev.rs` for
   implemented functions. Some NumPy constructs have no direct equivalent
   (`flatten()` == `reshape(-1)`); if no rstsr equivalent exists, skip that case and
   note it in `tracking/numpy_differences.md`.
5. **Run** on the device matrix (`cargo-inst`): at minimum `entry_row_cpu`, then
   `entry_row_faer`. Use `--nocapture` to inspect output.
6. **Update tracking** (`test-conventions` §6): add the row to `numpy_coverage.csv`
   (status, `rstsr_test`, `numpy_source_hash`) and any divergence to
   `numpy_differences.md`.

Style (see `test_transpose.rs` for a full example):

```rust
use crate::test_utils::*;
use rstsr::prelude::*;
use super::CATEGORY;
use crate::TESTCFG;

#[cfg(test)]
mod numpy_transpose {
    use super::*;
    static FUNC: &str = "numpy_transpose";

    #[test]
    fn test_multiarray() {
        // numpy: v2.4.2 | _core/tests/test_multiarray.py::TestMethods::test_transpose (L2221)
        crate::specify_test!("test_multiarray");

        let mut device = TESTCFG.device.clone();
        device.set_default_order(RowMajor);
        // ... commented NumPy + rstsr equivalent, per test-conventions §4
    }
}
```

For a list of small cases in one NumPy class (e.g. `TestRegression::test_reshape*`),
use the compact `// CASE <name> (line N)` sub-header - see `test_reshape.rs`
`numpy_reshape::regression`.

For error cases, first try the fallible form (`assert!(tensor.transpose_f(-2, -5).is_err())`);
only if the function has no `_f` variant, catch the panic with
`std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| ...))` and assert the
error (see `broadcast_arrays_f` usage in `test_broadcast_shapes.rs`).

### Step 2 - Doc test (in `doc_draft/<category>/test_<func>.rs`)

1. **Find inspiration** in NumPy/SciPy/array-api docstrings, or write your own.
2. Write `mod doc_<func>` (`FUNC = "doc_<func>"`). Each `#[test]` builds an example,
   runs it, prints with `println!("{result}")` (tensors use Display, not Debug).
3. **Run first**, capture stdout via `--nocapture`, then paste the actual output as
   comments - never invent the output before running.
4. Assert with `rt::allclose`/`assert_equal`. For layout/shape/strides print with
   `{:?}` (Debug).

```rust
mod doc_transpose {
    use super::*;
    static FUNC: &str = "doc_transpose";

    #[test]
    fn test_doc() {
        crate::specify_test!("test_doc");
        let mut device = TESTCFG.device.clone();
        device.set_default_order(RowMajor);

        let x = rt::tensor_from_nested!([[[0, 1], [2, 3]], [[4, 5], [6, 7]]], &device);
        let result = x.swapaxes(0, 2);
        println!("{result}");
        // [[[ 0 4]
        //   [ 2 6]]
        //
        //  [[ 1 5]
        //   [ 3 7]]]    <- pasted from actual --nocapture output
        let target = rt::tensor_from_nested!([[[0, 4], [2, 6]], [[1, 5], [3, 7]]], &device);
        assert!(rt::allclose(&result, &target, None));
    }
}
```

### Step 3 - API documentation (the docstring, on the *anchor function*)

**Follow skill `api-doc-conventions`** (this repository) - it *is* the
normative policy (tiers, anchor vs variants, canonical section order, row/col
notices, doctest rules, overloads, API accordance, micro-style). Terminology in
`CONTEXT.md` at the repository root. Reference exemplars: `transpose.rs`,
`reshape.rs`, `asarray.rs` in `rstsr-core/src/tensor/`.

Workflow essentials (details in the policy):

- **Anchor function** = the panic version that returns a view, e.g. `transpose`.
  Fully document it; **variants** (`_f`, `into_*`, `TensorAny::` methods) and
  aliases get minimized docs (`See also [<anchor>]`).
- The docstring's **examples must come from the Step 2 doc test**: copy from the
  run, keep shown output byte-identical, add hidden `#` setup lines.
- Every function gets a **row/col-major notice** - warning div + per-mode
  examples when behavior differs, the standard one-liner when identical.
- Record NumPy differences inline in `# Notes of API accordance` **and** in
  `tracking/numpy_differences.md` (tagged `intentional` / `bug`).

## Final checklist

- [ ] Parity test passes on `entry_row_cpu` and `entry_row_faer`.
- [ ] Provenance header byte-matches a `numpy_coverage.csv` row.
- [ ] Doc test output pasted from actual run, not invented; output-string
      assertion added to the `doc_draft` twin for displayed output.
- [ ] `cargo test -p rstsr-core --doc` green (docstring examples compile and pass).
- [ ] Docstring complies with skill `api-doc-conventions`.
- [ ] `numpy_coverage.csv` row added/refreshed (incl. `numpy_source_hash`).
- [ ] Any divergence recorded in `numpy_differences.md` (tagged).
