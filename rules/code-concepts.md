# Code Concepts (rstsr-core quick reference)

Read this when writing or reviewing rstsr-core (and trait/device crate) code.
Recovered from the pre-`rstsr-agents` rules; names verified against v0.8.0.

## Core concepts

- **Tensor types**: `TensorAny<R, T, B, D>`: (representation/ownership, dtype,
  backend/device, dimensionality).
- **Ownership aliases** (all are `TensorBase<S, D>` specializations, i.e.
  `(storage, dimensionality)`):
  - `Tensor<T, B, D>` (owned), `TensorView<'a, T, B, D>`, `TensorMut<'a, T, B, D>`,
    `TensorCow<'a, T, B, D>`, `TensorArc<T, B, D>`.
- **Layout**: `Layout<D>` contains shape (list of `usize`), stride (list of
  `isize`), and offset (`usize`).
- **Composition**: a tensor is (storage = (repr/ownership, data), layout = (shape,
  stride, offset)). Layout-only operations do not touch data.

## Manipulation & ownership semantics (naming convention)

- Layout change (no data change): basic-indexing/slicing, transpose/permute,
  broadcast, etc.
  - `into_<func>`: consumes ownership, returns ownership (`TensorAny` ->
    `TensorAny`), e.g. `into_shape` -> `Tensor`.
  - `to_<func>`: borrows, returns a view (no copy), e.g. `to_shape_assume_contig`
    -> `TensorView`.
- Conditional copy-on-write (copy only if the new layout cannot be a view):
  `reshape` / `to_shape` -> `TensorCow`; `into_shape` -> owned `Tensor`;
  `change_shape_with_args` takes `ReshapeArgs` (order, copy) explicitly. Fast
  variants that skip the layout check: `*_assume_contig`.
- Explicit copy: advanced indexing, `to_contig`, etc.

## Code style

- **Trait-based**: operations are defined as traits, implemented per device
  backend, e.g. `OpAddAPI`, `OpSinAPI`, `DeviceChangeAPI`.
- **Naming convention** (usual, exceptions exist):
  - traits add `API` suffix; device traits add `Device` prefix;
  - fallible functions add `_f` suffix and return `Result<T>` (rstsr's custom
    result type, `rstsr_common::error`);
  - panic version has no `_f` suffix; inside the crate use `rstsr_unwrap()`
    (not plain `unwrap()`) so backtrace information is preserved.
- **Trait-based overloading** (prefer tuple-argument overloads):
  - `rt::asarray`: `rt::asarray((vec, &device))`, `rt::asarray((&slice, &device))`, ...
  - `rt::add(&a, &b)` (views) vs `rt::add(a, &b)` (owned; may reuse storage of `a`).
- **Other conventions**:
  - prefer `fn foo(bar: impl Bar)` over `fn foo<T>(bar: T) where T: Bar` when the
    bound is simple (no composition or multiple bounds);
  - prefer `impl<T> where T: Trait` over `impl<T: Trait>` for readability, unless
    the bound is trivial (`Clone`, `Default`, ...).

## Common commands

See skill `cargo-inst` for the full set. Quick forms:

```bash
# one test case, row-major entries
RUST_BACKTRACE=1 cargo test -p rstsr-core --test entry_row_cpu \
  --features "backtrace row_major" --no-default-features -- \
  core_func::manipulation::test_reshape::numpy_reshape::regression --exact --nocapture

# API doc build (crate level, not workspace level)
RUSTDOCFLAGS="--html-in-header katex-header.html" cargo doc --no-deps
```
