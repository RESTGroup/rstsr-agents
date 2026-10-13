---
name: api-cheatsheet-conventions
description: Policy for the RSTSR ↔ NumPy/SciPy cheat-sheet pages and their parity artifacts (the umbrella `rstsr` crate's `cheatsheet` module, its two integration tests, and the Python parity script). Use when adding, editing, or reviewing a cheat-sheet row, its Rust test, or the parity script; and when refreshing the crate doc pages (`api_specification`, `array_api_standard`) alongside them.
---

# api-cheatsheet-conventions

Normative conventions for the **cheat-sheet** pages of the umbrella `rstsr`
crate and their three representations. Companion to skill
`api-doc-conventions` (which governs per-item rustdoc docstrings); this skill
governs the cross-library comparison pages, whose rows are not per-item
docstrings and do **not** follow the `api-doc-conventions` templates.

Normative language is RFC-2119 style (MUST / MUST NOT / SHOULD / MAY).

## 0. Scope and enforcement

Applies when adding or editing:

- a page under `rstsr/src/docs/cheatsheet*.md` (or the `cheatsheet` module
  wiring in `rstsr/src/lib.rs`);
- a cheat-sheet integration test in `rstsr/tests/cheatsheet_*.rs`;
- a block in the Python parity script `rstsr/tests/cheatsheet/parity.py`;
- the crate doc pages refreshed alongside them (`rstsr-core/src/docs/
  api_specification.md`, `array_api_standard.md`, and the umbrella-local
  `rstsr/src/docs/array_api_standard_extension.md`).

Standing assumptions, unless a page states otherwise:

- **Row-major only.** Examples assume the device default order is `RowMajor`.
- **Curated, not exhaustive.** Pages cover common operations; the exhaustive
  identifier list is `api_specification`.
- **No doctests.** The pages are table-heavy; the Rust integration tests are
  the executable check. Fenced code in a page MUST be ```` ```rust,ignore ````
  or ```` ```text ```` so a future `cargo test -p rstsr --doc` cannot compile it.
- The pages live in the **umbrella `rstsr` crate** (not `rstsr-core`), because
  `rt::linalg` resolves only there. `rstsr/src/docs/api_specification.md` and
  `array_api_standard.md` are **symlinks** into `rstsr-core/src/docs/`; edit the
  rstsr-core targets. The cheatsheet pages are real files (do not symlink).

## 1. The artifact triad and the correspondence rule

Every cheat-sheet example has **one stable id** naming all three of its
representations:

| Representation | Where the id appears |
|---|---|
| Markdown page | the section/anchor the row belongs to |
| Rust assertion | `fn <id>()` in `rstsr/tests/cheatsheet_core.rs` or `cheatsheet_linalg.rs` |
| Python reference | `# [<page>] <id>` block in `cheatsheet_parity.py` |

The markdown is prose (not executed); the **Rust test is the executable truth**;
the Python block is the cross-library reference the expected values come from.
Adding or changing a row MUST touch all three. Because the pages are not
doctested, this rule is what keeps them honest.

## 2. Page and module layout

Two pages, one module, wired in `rstsr/src/lib.rs`:

```rust
pub mod cheatsheet {
    #![doc = include_str!("docs/cheatsheet.md")]
    #![allow(unused_imports)]
    #![cfg_attr(not(feature = "linalg"), allow(rustdoc::broken_intra_doc_links))]
    use crate::prelude::*;
    use rt::*;

    #[cfg(feature = "linalg")]
    pub mod linalg {
        #![doc = include_str!("docs/cheatsheet_linalg.md")]
        #![allow(unused_imports)]
        use crate::prelude::*;
        use rt::*;
        use rt::linalg::*;
    }
}
```

- The module compiles as real Rust; keep the `use` block minimal and correct.
- The `cfg_attr` (and the matching crate-root one) keeps the core page's link
  to `cheatsheet::linalg` from warning when `linalg` is off. `docs.rs` enables
  `linalg` via `[package.metadata.docs.rs]`.
- Link into the pages from `rstsr/notes_to_api_doc.md` (the crate-root table of
  contents).

## 3. Writing a row

- Table shape: `NumPy [/ SciPy] | RSTSR | Description`. NumPy is the primary
  reference; SciPy appears only where it is the better analogue (mostly the
  linalg page).
- The RSTSR cell MUST be the **exact call** used in the Rust test — same
  function, same argument group.
- Link policy: intra-doc-link an item only if it resolves in the enclosing
  module scope; otherwise write it as backticked code. Never link a linalg item
  from the core page.
- State per-group assumptions (feature, device, order) in the section lead-in.

## 4. Test authoring

- Integration tests link `rstsr` by name; `rstsr` has **no dev-dependencies**
  and its `rstsr-core/tests/test_utils/` (`TestCfg`, `specify_test!`) is **not**
  reachable — use `rt::allclose` / `rt::tensor_from_nested!` only.
- `to_vec()` accepts **1-D only**; reshape with `.reshape(-1)` for a flat
  compare, or assert `.shape()`.
- Some constructors return dyn-dim (`IxD`) tensors and need a type annotation
  (`let z: Tensor<f64, DeviceFaer, _> = rt::zeros(([2, 3], &device));`).
- Reductions (`sum`, `mean`, `max`, ...) return a **scalar**, not a 0-d tensor;
  `trace` returns a 0-d tensor (`.to_scalar()`).
- Prefer **invariant assertions** over magic constants — `l % lᵀ ≈ a` (cholesky),
  `q % r ≈ a` (qr), `u % diag(s) % vᵀ ≈ a` (svd), `a % x ≈ b` (solve),
  `a % inv(a) ≈ I`, `a % pinv(a) % a ≈ a`. Hardcode a value only when it comes
  from the parity script, and shape-check before `allclose` (it broadcasts).
- The linalg test is gated by `[[test]] required-features = ["linalg"]` in
  `rstsr/Cargo.toml`, so it is skipped without the feature.

## 5. Python parity script

`rstsr/tests/cheatsheet/parity.py`: run-and-print (like
`rstsr-core/tests/tracking/sync_numpy.py`), never generates code. Each block
prints `# [<page>] <id>` followed by the reference values. NumPy for the core
page; NumPy and SciPy for the linalg page. Import scipy defensively and skip the
SciPy-only blocks when it is absent.

## 6. Refreshing the spec pages

Sources of truth for identifiers: the export blocks in
`rstsr-core/src/prelude.rs`, `rstsr/src/prelude.rs`, and
`rstsr-linalg-traits/src/prelude.rs`. For each page, diff the backticked
identifier set against those exports: **fix every stale/renamed identifier**
(named in the page but no longer exported); **add only the curated important
missing set** — do not make the pages exhaustive. Do **not** add fenced `rust`
blocks to these pages (the `rstsr-core --doc` CI job runs). Refresh
`array_api_standard_extension.md`'s linalg statuses when `rt::linalg` changes.

## 7. Checklist

1. Add the row to the page (exact call) → 2. add `fn <id>()` to the matching
   Rust test → 3. add the `# [<page>] <id>` block to `parity.py`.
2. Run: `cargo test -p rstsr --test "*" --release` and
   `cargo test -p rstsr --test "*" --release --features linalg`.
3. `python3 rstsr/tests/cheatsheet/parity.py` runs clean.
4. `cargo doc -p rstsr --features linalg --no-deps` (and without `linalg`).
5. `cargo clippy -p rstsr --all-targets --all-features -- -D warnings` and
   `cargo fmt --all -- --check`.
