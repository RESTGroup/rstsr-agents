# RSTSR API Documentation

The ubiquitous language for documenting rstsr-core's rustdoc API. This context
covers the *documentation* domain only - which functions get documented, how
docstring families relate, and how examples are verified. Library-implementation
terms (tensor, device, layout) live in `rules/code-concepts.md` and source, not
here; testing-domain terms (parity test, provenance) live in
`rstsr/tests/CONTEXT.md`. Normative rules live in skill `api-doc-conventions`
(`skills/api-doc-conventions/SKILL.md`); this file only fixes the words.

## Language

### Documentation model

**Anchor function**:
The single member of a function family that carries the full docstring -
the panic-version free function returning a view (e.g. `transpose`). All other
family members point to it. *Avoid:* "core function" (collides with the crate
name `rstsr-core`), "main function", "common function".

**Variant**:
A family member documented minimally (title + `See also [anchor]`) because it
only differs in failure mode or ownership: the fallible `_f` form, the
ownership-consuming `into_*` / `to_*` / `change_*` forms. *Avoid:* "wrapper"
(a wrapper is an implementation detail, not a documented surface).

**Alias**:
A `pub use` re-export of the anchor under another name (`transpose` as
`permute_dims`, `expand_dims` as `unsqueeze`). Inherits the anchor's docstring;
never documented separately.

**Associated method**:
The `TensorAny::`-method form of a free function (`TensorAny::transpose`). A
variant in documentation terms; enumerated in the anchor's see-also, not
documented standalone.

**Overload**:
One tuple-argument form of an overloaded function (`rt::asarray((vec, shape,
&device))` vs `rt::asarray(vec)`). Enumerated exhaustively in the anchor's
Overloads Table; examples cover only typical forms.

**Overloads Table**:
The `# Overloads Table` docstring section listing every overload, grouped by
output type (`asarray` is the exemplar).

### Tiers

**Full tier**:
User-facing anchor functions: complete docstring (structure, row/col notice,
examples, API accordance, see-also). Assignment list in skill
`api-doc-conventions` §1.1.

**Minimal tier**:
Variants, aliases, macro-generated operator traits, storage/device internals:
summary line + see-also only.

**Type/module floor**:
Types get an accurate summary paragraph (body free-form); public modules get a
`//!` one-liner.

### Artifacts

**doc_draft twin**:
The `tests/doc_draft/<category>/test_<func>.rs` test that a docstring example
MUST originate from - written and run first, its real output pasted into the
docstring second. Direction of truth for every example.

**Row/col-major notice**:
The explicit order-behavior statement every full-tier docstring carries: the
identical-behavior one-liner, or the warning div + per-mode examples when
behavior differs by device default order.

**API accordance**:
The `# Notes of API accordance` section: array-api / NumPy / RSTSR signature
triple with links, plus inline statements of differences.

**Differences report**:
The NumPy-differences registry `rstsr-core/tests/tracking/numpy_differences.md`
(per-function headings, `intentional`/`bug`/`col-major-transfer` tags) and its
future rstsr-book mirror. Three layers: registry (source of truth, agent-facing)
/ docstring (self-contained statement) / book page (human-facing).

**Doc coverage checklist**:
`rstsr-core/tests/tracking/doc_coverage.csv` - module-level rows tracking
documentation status. Drives the retrofit; distinct from API-conformance status
in `src/docs/array_api_standard.md`. *Avoid:* "doc tracking file" (ambiguous
with the numpy coverage checklist).

**API doc campaign**:
The planned retrofit of rstsr-core docstrings to this policy, in batches
(`plans/2026-09-api-doc-campaign.md`). Policy is binding-on-touch outside the
campaign; the campaign is the only vehicle for wholesale rewrite.
