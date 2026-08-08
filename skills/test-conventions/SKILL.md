---
name: test-conventions
description: Shared conventions for rstsr-core tests. Read before authoring any core test; the core-test / core-numpy-sync / core-issue-regression skills all assume this.
---

# Test Conventions (rstsr-core)

Reference for every core-test authoring task. The other `core-*` skills point here
instead of repeating this. See also skill `cargo-inst` for compile/test commands,
`rstsr-core/tests/CONTEXT.md` for the glossary, and `rstsr-book/dev/` for design
rationale and ADRs (e.g. ADR-0002, the entry-binary test matrix).

## 1. Folder taxonomy

```
rstsr-core/tests/
├── test_utils/          # TestCfg, assert_equal, specify_test!, tensor_from_nested
├── core_func/           # parity tests: mod numpy_<func> (transferred) / mod custom_<func>
├── doc_draft/           # doc tests: mod doc_<func> (examples destined for docstrings)
├── col_major/           # (planned) col-major rstsr-correctness, NOT NumPy parity
├── test_issues/         # issue regression tests (one file per issue)
├── tracking/            # numpy_coverage.csv + numpy_differences.md
├── entry_row_cpu.rs     # type DeviceType = DeviceCpuSerial; RowMajor  (wired now)
├── entry_row_faer.rs    # type DeviceType = DeviceFaer;       RowMajor (planned - see ADR-0002)
├── entry_col_cpu.rs     # #![cfg(feature="col_major")]; CpuSerial      (planned - see ADR-0002)
└── tensor_sum.rs        # standalone integration test (not part of the entry matrix)
```

- `core_func/` and `doc_draft/` mirror the same category tree (`manuplication/`,
  `linalg/`, ...). A function's parity test lives in `core_func/`; its doc test lives
  in `doc_draft/`. They are separated files, authored together.
- **No `.npy` / no `rstsr-test-manifest` in core.** Small tensors use
  `rt::tensor_from_nested!`; other cases pass a Rust `Vec` to `rt::asarray`.
  Large reference data is a device-crate concern, not core's.

## 2. Entry binaries & the device matrix

Each `entry_<order>_<device>.rs` is one cargo test binary. It defines `type DeviceType`
and `static TESTCFG`, then `mod core_func; mod doc_draft; mod test_issues;`. The shared
body is **not** duplicated - the matrix is formed by binaries. See ADR-0002
(`rstsr-book/dev/adr/adr-0002-entry-binary-test-matrix.mdx`).

```rust
// entry_row_cpu.rs
mod core_func;
mod doc_draft;
mod test_issues;
mod test_utils;

pub use rstsr::prelude::*;
pub use std::sync::LazyLock;
pub use test_utils::TestCfg;

pub use DeviceCpuSerial as DeviceType;

pub static TESTCFG: LazyLock<TestCfg<DeviceType>> = LazyLock::new(|| {
    let mut device = DeviceType::default();
    device.set_default_order(RowMajor);
    TestCfg::init(device, vec![], None) // skip=[], allow=None
});
```

- `entry_row_faer.rs` (planned) swaps `DeviceFaer as DeviceType`.
- `entry_col_cpu.rs` (planned) starts with `#![cfg(feature = "col_major")]` and `mod col_major;`
  instead of `core_func` (col-major body is separate - it is **not** NumPy parity).
- Only `entry_row_cpu.rs` is wired in the repo today; `entry_row_faer.rs` /
  `entry_col_cpu.rs` are part of the ADR-0002 design but not yet present.
- Gate with `[[test]]` `required-features` in `rstsr-core/Cargo.toml` so row/col
  binaries cannot collide (col_major is compile-time mutually exclusive with
  row_major).
- **Device scope now:** only `DeviceCpuSerial` (row-major) is wired in the repo.
  `DeviceFaer` and col-major entry binaries are part of the ADR-0002 design but not yet
  present. The structure is future-ready for device crates (OpenBLAS, MKL, ...) which
  symlink `test_utils/` + `core_func/` + `doc_draft/` and write their own
  `entry_<device>.rs`. BLAS-backend devices use a *different* testing strategy and are
  out of scope for `core-*` skills.

## 3. `specify_test!` / `TestCfg` (runtime gating)

Every test function begins with `crate::specify_test!("<item>")`. This checks
`[CATEGORY, FUNC, ITEM]` against `TESTCFG`'s skip/allow lists and returns early if
skipped. It is the mechanism for **per-device skips without recompilation** - a device
crate's entry passes its own skip list to `TestCfg::init`.

```rust
#[cfg(test)]
mod numpy_transpose {
    use super::*;
    static FUNC: &str = "numpy_transpose";

    #[test]
    fn test_multiarray() {
        crate::specify_test!("test_multiarray");
        let mut device = TESTCFG.device.clone();
        device.set_default_order(RowMajor);
        // ...
    }
}
```

`CATEGORY` is a `static &str` per category module (e.g. `manuplication`), `FUNC` per
test module, `ITEM` per test function (the `specify_test!` argument).

## 4. Provenance convention (mandatory for transferred tests)

Every NumPy-transferred test function carries a header citing the NumPy source. The
path+class+method must be **byte-identical** to a row in `tracking/numpy_coverage.csv`.

```rust
#[test]
fn test_multiarray() {
    // numpy: v2.4.2 | _core/tests/test_multiarray.py::TestMethods::test_transpose (L2221)
    crate::specify_test!("test_multiarray");

    // a = np.array([[1, 2], [3, 4]])            <- commented NumPy, one block
    // assert_equal(a.transpose(), [[1, 3], [2, 4]])
    let a = rt::tensor_from_nested!([[1, 2], [3, 4]], &device);   <- rstsr equivalent, immediately below
    let expected = rt::tensor_from_nested!([[1, 3], [2, 4]], &device);
    assert_equal(rt::transpose(&a, None), &expected, None);
}
```

Rules:
1. `numpy: <version> | <path>::<Class>::<method> (L<line>)` - one header per test fn.
2. Every NumPy assertion is a comment immediately followed by its rstsr translation.
3. Version lives in the header (not per-line) and matches the file header in the
   tracking files.
4. Space a blank line between distinct test cases.

When the NumPy test is a list of small cases (e.g. a regression class), use the
compact `// CASE <name> (line N)` sub-header style - see `test_reshape.rs`
`numpy_reshape::regression` for the example.

## 5. Tensor creation & comparison

- Nested literals: `rt::tensor_from_nested!([[1, 2], [3, 4]], &device)`.
- Ranges/shapes: `rt::arange((n, &device)).into_shape(shape)`, `rt::zeros((shape, &device))`,
  `rt::ones((shape, &device))`. Always annotate the dtype for zeros/ones:
  `let t: Tensor<f64, _> = rt::zeros((shape, &device));`. Replace `np.empty` with
  `rt::zeros`. Replace `np.random.randn` with `rt::arange` (deterministic) where possible.
- From a `Vec`: `rt::asarray((vec, shape, &device))`.
- Value equality: `assert_equal(&result, &target, None)` - shape-checked then `rt::allclose`.

### `allclose` broadcast gotcha

`rt::allclose` is **broadcast-permissive** - two tensors of *different* shapes can be
"allclose". `assert_equal` is safe (it `assert_eq!`s shapes first). If you use raw
`rt::allclose`, assert the shape explicitly, or prefer `assert_equal`. Document the
choice wherever raw `allclose` is used.

### Expected errors

Prefer the `_f` fallible variant: `assert!(tensor.transpose_f(-2, -5).is_err())`. If
that still panics, use
`std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| a.reshape_f(new_shape)))`
and assert on the result.

## 6. Tracking hygiene

When you add or change a parity test, update **both** tracking files:
- `tracking/numpy_coverage.csv` - add/refresh the row (status, `rstsr_test` path, note,
  and `numpy_source_hash` = hash of the NumPy test function source at the pinned
  version).
- `tracking/numpy_differences.md` - if rstsr diverges (intentional or a bug), add an
  entry tagged `intentional` / `bug` / `col-major-transfer`.

A divergence is either a bug (fix it) or an intentional difference (record it). Never
leave a divergence only in a code comment.

## 7. Fixtures / parametrization

Use `rstest` only when a test genuinely needs setup/teardown or table-driven
parametrization across dtypes/shapes. Do not adopt it blanketly; most parity tests are
single-case and read better as plain `#[test]` functions.
