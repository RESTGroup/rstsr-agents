---
name: lapacke-translation
description: Translate a LAPACK routine into the rstsr BLAS device driver layer (rstsr-blas-traits driver_impl + src/lapack_* builders), or retrofit an existing translation to the settled policy. Load before any new LAPACK driver translation, SVD/solve/eigh driver edit, or workspace/bridge/error-mapping change in rstsr-blas-traits.
---

# LAPACKE Translation (rstsr BLAS device drivers)

Operational recipe for translating a LAPACK routine into the
`rstsr-blas-traits` driver layer, or retrofitting an existing translation to
the settled policy. Two ADRs carry the "why": **ADR-0009**
(`rstsr-book/dev/adr/`) for the LAPACKE translation layer
(`driver_impl/lapack/**`, the raw-Fortran driver files), and **ADR-0010** for
the LAPACK interface layer (`src/lapack_*/`, the builders). This skill
carries the "how" only; each section below names the layer it belongs to. The
fact base behind the decisions (LAPACKE/scipy/numpy behavior studies) is
recorded in `rstsr-improve-trajectory/2026-10-11-lapacke-layer/FINDINGS.md`.

> **Gap-notice rule (mandatory)**: if a routine you are translating hits a
> situation this recipe does not cover, **stop and report** — tell the user
> the skill/ADR lacks coverage and needs updating. Do not improvise
> silently; different agents must converge on the same translation.

## 1. Where things live

```
rstsr-blas-traits/
├── src/{lapack_solve,lapack_eigh,lapack_svd}/   # LAPACK interface layer (ADR-0010)
│     XxxDriverAPI<T> trait + builder struct XX_<'a,B,T> (+ aliases S/D/C/ZXX)
├── driver_impl/lapack/                          # LAPACKE translation layer (ADR-0009, PRIMARY)
│     <family>/<routine>.rs                      # shared by vendor crates via symlinks
├── driver_impl/lapacke/                         # LAPACKE translation layer, passthrough (openblas+mkl only)
└── src/util/{util_tensor.rs,util_layout.rs}     # overwritable_convert, get_output_order, ...
```

The `XxxDriverAPI` trait (defined in `src/lapack_*`) is the seam between the
two layers: the builders call it, the `driver_impl/` trees implement it.

- `lapack` is the primary path (most BLAS vendors ship no LAPACKE in their
  shared library); `lapacke` stays as an optional feature for openblas+mkl.
  The two are **mutually exclusive crate features** — never compile both;
  validate by running the driver test suite under each config separately
  (numpy/scipy are the correctness oracle when they disagree).
- Per-routine dtype duplication in vendor files uses two
  `duplicate_item` blocks (real `[f32]/[f64]`, complex
  `[Complex<f32>]/[Complex<f64>])` — complex needs `*mut` casts and
  `T::Real` scalars.
- Real/complex-parallel variant (sysv): routines whose complex form splits
  into symmetric/Hermitian twins use a `HERMI` substitution column in the
  duplicate table. `duplicate` substitutes the token textually, so the impl
  header must stay non-generic (`impl SYSVDriverAPI<T, HERMI>`) — a
  `const HERMI: bool` generic there would receive the literal and fail
  (E0207/E0425). The real block keeps its own table and generic impl.
- `blas_int` is `i32` (or `i64` under feature `ilp64`) — keep every FFI-side
  integer as `blas_int`; never hard-code `as i32` casts on info/ld values.

## 2. Input policy — interface layer, ADR-0010 (per tensor argument)

Classify each 2-D tensor input, then apply:

| Case | Meaning | Action |
|---|---|---|
| **f-prefer** (incl. f-contig) | column stride structure; `ld` = `stride[0]`-derived leading stride (need NOT equal nrows) | **zero-copy pass** by raw pointer with derived `lda` |
| **c-contig / c-prefer** | row-major structure | **clone** into the call order (bridge copy in) |
| **fully non-contiguous** | neither (e.g. sliced both dims, broadcast) | **clone** into the call order (rstsr extension — LAPACKE cannot express this) |

- Routines that **overwrite** their input (factorizations gesv/getrf/potrf/
  sysv, in-place solves): clone-or-consume **regardless of contiguity**
  (use `overwritable_convert[_with_order]`; only genuinely-owned buffers
  are written through). A view-only f-prefer input to a destructive call
  must be materialized first.
- 1-D arguments (w, s, ipiv, tau, b-vector): order is irrelevant; require
  or force contiguity (`.into_contig_f()` on views) before pointerizing.
- **One order rule per call**: the builder picks one order for the whole
  call through `get_output_order(&[first-class output tags], &[(c_prefer,
  f_prefer) votes], device.default_order())` — an explicit `out=` wins
  first-class; input votes decide otherwise; both-prefer and neither-prefer
  inputs are neutral (ambiguous falls to the device default). Do not
  hand-roll `match (c_prefer, f_prefer)` blocks (the 1-column-`b` mismatch
  of legacy gesv/sysv came from exactly that).

## 2a. Output policy

One order per call (Section 2's "order rule"): the builder picks the call
order from the input preference (f-prefer → ColMajor, c-prefer → RowMajor,
ambiguous → device default), and **fresh outputs are allocated in the call
order** — for prefer inputs the output strides follow the input layout.
Values stay numpy-parity; only strides differ for minority-layout inputs.
(In-place/overwritable outputs keep their buffer's order — scipy
`overwrite_*` semantics; the call order makes that the input's own order.)
- View-only f-prefer inputs always pass zero-copy (Section 2), independent
  of the output policy.
- Zero-size (`min(m,n) == 0`): synthesize the LAPACK result in the builder
  without calling the driver — identity sub-blocks (jobz='A' ⇒ U=I_m,
  VT=I_n; 'S' ⇒ zero-width), empty `s`/`w` — **in the call order**, same as
  fresh outputs. Never exercise the driver at m==0/n==0.

## 2b. Bridge copies

- The F↔C bridge is a full-matrix transpose through the orderchange kernels.
  The driver files call the serial kernel (`orderchange_out_*_ix2_cpu_serial`).
  Whether the copy should instead run under the device's threading policy is
  **undecided** (ADR-0009) — do not add threading knobs, and do not treat the
  serial call as a bug to fix.
- **Full-matrix copies** for every bridged matrix. No triangle-only
  (`dsy_trans`-style) variants in this campaign — uniform kernel inventory;
  triangle-only is a sanctioned future optimization (see ADR-0009).
- Bridge failures must surface as `Err` — never `.unwrap()` a bridge result.

## 3. Vendor file shape — translation layer, ADR-0009 (driver_impl/lapack/<family>/<routine>.rs)

Two tiers in ONE file, mirroring LAPACKE's `xxx` / `xxx_work` split; the
trait method signature is UNCHANGED (do not refactor trait definitions):

```rust
// "_work"-equivalent: LAPACKE _work tier. lwork = -1 ⇒ LAPACK query semantics.
// Carries the layout 3-way branch: ColMajor → direct FFI (caller lds);
// RowMajor → template lds MAX(1, rows), transposed temporaries
// (orderchange bridges), call, transpose back; per-branch query
// short-circuit. Bridge/allocation failure ⇒ -1010/-1011 sentinels.
// `pub` for cross-crate symlink reachability, but internal-purpose:
// never re-exported through any prelude.
pub unsafe fn dgesvd_work(
    order: FlagOrder,
    jobu: char, jobvt: char, m: usize, n: usize,
    a: *mut T, lda: usize, s: *mut T::Real,
    u: *mut T, ldu: usize, vt: *mut T, ldvt: usize,
    work: *mut T, lwork: blas_int,
    rwork: *mut T::Real,            // complex only
) -> blas_int;

// trait impl: the lapacke_xxx high-level tier — formula-sized workspaces
// BEFORE the query (per Section 3a), query call → hardened read-back
// (Section 3a) → allocate → compute call, both through xxx_work.
unsafe fn driver_dgesvd(..) -> blas_int { ... }
```

- Query call and compute call are **textually separate statements**, both
  routed through `xxx_work`.
- Workspace ownership + clamps + query read-back hardening live in the
  **trait impl** (the wrapper above), NOT in the thunk and NOT in
  `src/lapack_*/` generic code — the generic builder carries only policy
  (order choice, input/output conversion, zero-size synthesis, error
  mapping).
- Keep the routine's Fortran argument order inside the thunk signature
  (the `order: FlagOrder` parameter is the rstsr extension replacing
  LAPACKE's `matrix_layout`).

## 3a. Workspace policy (per routine family)

LAPACKE-faithful: query where LAPACKE queries, documented formula where
LAPACKE exposes no query.

| Routine(s) | work | iwork | rwork |
|---|---|---|---|
| gesv, getrf, potrf | — | — | — |
| getri | query | — | — |
| sysv | query | — | — |
| syev, sygv | query | — | complex: formula `MAX(1, 3n−2)` |
| syevd, sygvd | **double query** (lwork+liwork in one call) | (queried) | complex: query |
| gesvd | query | — | complex: formula `MAX(1, 5·min(m,n))` |
| gesdd | query | formula `MAX(1, 8·min(m,n))` **before** the work query | complex: formula (`jobz='N'`: `7·minmn` safe-upper; else `minmn·MAX(5·minmn+7, 2·maxmn+2·minmn+1)`) |

Hardening (mandatory, all O(1) budget):

- Query with the **real (col-major) lds**, never placeholder values.
- `MAX(1, ·)` around every formula term.
- `lwork == 0 → 1` clamp after every query read-back.
- **Checked** int conversion of query values (no silent `as` truncation).
- `nextafter` guard for **f32/c64** query values (work(1) travels the f32
  mantissa; ≥2^24 rounds down on integer conversion → undersized buffer).
- **No fudge factors** (scipy's 1.01 rejected — OpenBLAS-getri-specific).
- Complex routines needing rwork at query time: allocate the formula-sized
  rwork **before** the query call (never pass an empty rwork to a query).

### `superb` (gesvd only)

The Fortran routine has no superb argument; it returns the bidiagonal
superdiagonal in the workspace. Copy out after the compute call: real
`superb[i] = work[i+1]`, complex `superb[i] = rwork[i]`, for
`i < min(m,n)−1`. Keep the 4-tuple return (s, u, vt, superb) at the driver
tier; higher layers may discard it.

## 3b. Error mapping (info origin: ADR-0009; decode: ADR-0010)

- The thunk returns **raw LAPACK info** in the routine's **Fortran argument
  numbering** — the leading-dimension checks included, so the index is
  checkable against the Fortran source. No LAPACKE `info−1` shift (that
  exists only because LAPACKE inserts `matrix_layout` as arg 1; we have no
  such arg).
- The builder layer maps (use `util_error::map_lapack_info`):
  - `info < 0` → `Error` "illegal argument in `<routine>` arg `<-info>`
    (internal bug, please report)";
  - `info > 0` → per-routine semantic message (e.g. "SVD did not converge",
    "matrix is singular / not positive definite");
  - `-1010`/`-1011` (tier-internal allocation/bridge sentinels, same values
    as LAPACKE's `LAPACK_WORK_MEMORY_ERROR`/`LAPACK_TRANSPOSE_MEMORY_ERROR`;
    real info magnitudes never reach 1010) → `MemoryError`.
- Replace any `rstsr_assert_eq!(info, 0, ..)` and bridge `.unwrap()` sites
  with the mapping above.

## 4. Test matrix (per routine)

Small sizes only (≤ 20 per side). Required dimensions:

1. **Dtype**: f64 always; c64 wherever the routine touches complex-specific
   paths (rwork/superb/conj) — gesvd/gesdd minimum.
2. **Layout × input**: for EACH matrix input, run at least: f-contig,
   f-prefer with `ld > dim` (e.g. 5×3 in a 5×6 buffer), c-contig,
   c-prefer with `ld > dim`, fully non-contiguous (slice both dims).
   Results must agree with the f-contig run (values, not strides).
   + in-place variants where the routine overwrites (buffer identity where
   applicable).
3. **Zero-size**: m=0, n=0, both — assert identity sub-blocks / empty
   vectors per Section 2a.
4. **Both feature configs**: run the driver suite under `lapack` (default)
   and `lapacke` (openblas/mkl) separately.
5. **ipiv/jpvt assertions** (factorizations): 0-based values cross-checked
   against the same factorization computed on the f-contig input.
6. Per-vendor overrides live in the vendor crate (e.g. KML's
   `tests/driver_impl/f64/gesvd.rs` local override) — adjust only when
   compilation breaks; do not delete.

## 5. Step-by-step: translating a new routine

1. Read the LAPACKE source (`~/Git-Others/lapack/LAPACKE/src/lapacke_x<name>.c`)
   and the Fortran header comment (`~/Git-Others/lapack/SRC/x<name>.f`) —
   the workspace requirements and info>0 semantics are documented there.
2. Check Section 3a: does the routine query, double-query, or use formulas?
   If the table lacks the routine → **gap-notice rule**.
3. Write the builder (`src/lapack_<family>/<name>.rs`): input policy
   (Section 2), output policy (Section 2a), error mapping (Section 3b),
   zero-size synthesis.
4. Write the vendor file (Section 3): `xxx_work` thunk + thin trait impl.
   Two `duplicate_item` blocks (real/complex).
5. Register the new builder in `BlasDriverTraitList` and per-vendor
   `LapackDriverAPI` impls if required.
6. Write tests per Section 4. Run:

   ```bash
   RSTSR_DEV=1 cargo test -p rstsr-openblas --test tests_driver_impl
   # and under the lapacke config:
   RSTSR_DEV=1 cargo test -p rstsr-openblas --test tests_driver_impl --features lapacke
   ```

7. Verify against numpy/scipy (small inputs, both orders) when in doubt.

## 6. Deviations (deliberate, do not "fix" without a new grill)

- No NaN/finite pre-check (numpy precedent; hazard study in FINDINGS.md).
  Future path: an `_adv_` trait variant with user knobs — a
  separate structural task, do not implement opportunistically.
- No triangle-only bridge copies.
- Zero-size short-circuit synthesizes results (never calls the driver).
- lapack + lapacke both exist, mutually exclusive; `lapack` is primary.
- No batching (2-D only) at the driver tier.
- Bridge-copy threading is **undecided** (ADR-0009) — do not add threading
  knobs, and do not "fix" the serial `orderchange_out_*_cpu_serial` calls.
