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

1. **Find the NumPy test.** NumPy tests live at `../other-repos/numpy/numpy/_core/tests`
   or `.../numpy/lib/tests`. Identify the test function(s) covering this function.
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

### Step 3 - API documentation (the docstring, on the *core function*)

#### Core vs variant functions

- **Core function** = the panic version that returns a view, e.g. `transpose`.
  Fully document it.
- **Variant functions** = `transpose_f` (fallible), `into_transpose` (ownership-token,
  panic), `into_transpose_f`, `TensorAny::t()`, `permute_dims` (alias). Give them
  minimized docs - same title as the core function plus `See also [<core_func>]`.
- Exception: `reshape` is fully documented alongside its core form.

Minimized variant style:
```rust
/// Permutes the axes (dimensions) of an array.
///
/// See also [`transpose`].
```

#### Core-function docstring sections (in order)

1. **Title** - reuse NumPy/SciPy/array-api's if one exists; else write your own.
2. **Explanation** - only if necessary.
3. **Row/column-major warning** - only for functions whose behavior differs by
   default order (`reshape`, `asarray`, broadcasting). Use:
   ```rust
   /// <div class="warning">
   ///
   /// **Row/Column Major Notice**
   ///
   /// This function behaves differently on default orders ([`RowMajor`] and [`ColMajor`]).
   ///
   /// </div>
   ```
   Add a subsection + example for the differing behavior (returns you to Step 2).
4. **Parameters** / **Returns** - document overloads and ownership notes for
   `into_*` variants (they take ownership, change layout only, not data).
5. **Examples** - **must follow the doc test** from Step 2.
6. **Notes of API accordance** - differences vs NumPy (links to `numpy_differences.md`).
7. **See Also** - related functions, then variants of this function, then variants of
   associated functions.
8. **Panics** - only when relevant.

## Final checklist

- [ ] Parity test passes on `entry_row_cpu` and `entry_row_faer`.
- [ ] Provenance header byte-matches a `numpy_coverage.csv` row.
- [ ] Doc test output pasted from actual run, not invented.
- [ ] `numpy_coverage.csv` row added/refreshed (incl. `numpy_source_hash`).
- [ ] Any divergence recorded in `numpy_differences.md` (tagged).
