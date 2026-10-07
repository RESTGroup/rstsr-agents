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
- **Trait-bound placement (tensor vs device)**:
  - element-type (`T`) requirements belong at the device operator/impl level, not
    on tensor-layer functions; the tensor layer carries device-trait bounds only
    (e.g. `B: OpAddAPI<T, D>`) - see `tensor/operators/op_binary_common.rs`.
    Exceptions: arithmetic operator overloading (`op_binary_arithmetic.rs`) and
    `op_with_func.rs`;
  - a device op needing element behavior (ordering, zero tests, ...) states the
    bound on its device impl (e.g. `T: ExtSortCmp` in
    `device_cpu_serial/searching.rs`); element callbacks like
    `&dyn Fn(&T) -> bool` are not GPU-meaningful and do not belong in device-op
    signatures;
  - tensor-layer functions are thin wrappers: layout/argument checks, output
    allocation via `uninit_impl`, then the device op. `outof_cpu_vec` is a last
    resort (host-buffer import); prefer caller-allocated buffers filled by the
    device op.
- **Fast paths for known dtypes** dispatch by `TypeId` and re-type the raw
  buffers (unsafe reference casts guarded by the `TypeId` equality) instead of
  widening the public bound - the blas-crate matmul `impl_uninit_dispatch!` and
  `device_cpu_serial/set.rs`'s `for_each_fast_dtype!` are the reference shapes.
- **Tensor arguments in free functions**: when the function only reads its
  tensor inputs, take `impl TensorViewAPI<Type = T, Backend = B, Dim = D>`
  instead of `&TensorAny<R, T, B, D>` - it accepts owned tensors, references,
  `&mut`, and views by value, and drops the `R` parameter and its `DataAPI`
  bound (reference: the reductions; the manip/sort/set wave follows). Functions
  that need ownership or repr capabilities keep `R` generic bounds (e.g.
  `roll_f`'s `DataIntoCowAPI`, `diff_f`'s `DataCloneAPI`).
- **Tuple-style overloads (API traits)**: implement the `TensorView<'_, T, B, D>`
  value form alongside the `&TensorAny<R, ...>` form (all cross combinations
  for multi-tensor tuples), so callers never need a `&` on a view - reference:
  `op_binary_common.rs`, `sorting.rs` / `searching.rs` / `set.rs`.
- **Named multi-output structs** (e.g. `UniqueCounts`): convert to and from the
  plain tuple through `From` in both directions, and document the `.into()`
  usage in the function docstring.
- **Flattened visit order follows the device default order**: row-major
  flattens row-major, column-major flattens column-major (the `reshape(-1)`
  order, matching `iter()`). Applies to `repeat` / `roll` with `axis = None`,
  `nonzero`, and the `unique_*` first-occurrence sequence; device kernels take
  the order as a `FlagOrder` parameter from `self.default_order()`.
- **Multi-index iteration**: reuse rstsr-common's layout iterators
  (`IndexedIterLayout`, `IterLayoutRowMajor` / `IterLayoutColMajor`) instead of
  hand-rolled index generators.

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
