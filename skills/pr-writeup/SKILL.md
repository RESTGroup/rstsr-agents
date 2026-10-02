---
name: pr-writeup
description: Write RSTSR pull-request titles and bodies in the house style - a changelog-ready "Changes" part (category bullets, no PR ids) plus a short "Details" part. Use when opening or editing a PR, drafting a PR description, or preparing a branch for review with gh.
---

# PR writeup

## Workflow

1. Read the branch as a whole — `git log --oneline <base>..HEAD` and
   `git diff --stat <base>...HEAD` — and write from the diff, not from memory.
2. Draft the title and the two body parts below.
3. Create or edit the PR with a body file: `gh pr create --title "<title>" --body-file -`
   with a heredoc (or a scratch file you do not commit); later updates via
   `gh pr edit --body-file -`.

## Title

Same shape as the commit subject (`<crate>: <summary>`, see skill
`git-commit-coauthor`): lead with the main crate, add a short change-type tag in
parentheses when it helps, keep it to one line.

- `rstsr-core (fix): view-only iteration API`
- `rstsr-native-impl: blocked 2-D iteration for strided elementwise ops`
- `rstsr-book (dev): add ADR-0008 uninitialized allocation contract`

When several crates change non-trivially, start with the type
(`fix: ...`, `refactor: ...`).

## Body

Two parts, in this order.

### Part 1 — Changes (changelog-ready)

The release note for this PR: written so the section can be pasted into
`CHANGELOG.md` as-is (the *paste test*). The release manager appends the
repository PR reference when assembling a release, so never write
`(RESTGroup/rstsr#NN)` yourself.

Use the CHANGELOG category headings, in this order, dropping empty ones:

`API breaking changes` — `New features` — `Enhancement` — `Behavior change` —
`Bug Fix` — `Dev infrastructure` — plus the qualifier category
`API breaking changes (user should not feel that)` for breaks only trait
implementors or rare paths can hit.

This list is the common set, not a closed one — when a change genuinely fits no
category, add a heading in the same style and keep the same name when the
section is pasted into `CHANGELOG.md`.

Category fit:

- `API breaking changes` — a break users feel; put the migration step in the bullet.
- `New features` — an additive capability.
- `Enhancement` — performance, quality, docs, refactor.
- `Behavior change` — an observable change that is not a defect fix.
- `Bug Fix` — a fixed defect (regression, soundness, correctness).
- `Dev infrastructure` — CI, tooling, agent workflow, tracking.

Each bullet is one self-contained release note: present tense, the
function/type/crate named in backticks, what changed and why it matters.
Consolidate related micro-changes into one bullet.

### Part 2 — Details

The few notes a reviewer needs that a changelog reader does not:

- why this design, including the rejected alternative in a clause;
- known caveats, limits, and follow-up work;
- a number or two backing a performance claim;
- companion PRs in sibling repos, related issues;
- at most one line on tests, when it adds confidence.

Budget: a handful of bullets or a short paragraph. Five bullets is already
much; longer material belongs in the commit body or a code comment. When there
is no caveat, rationale, or measurement to report, omit the part.

## Calibration

AI drafts over-report, because they cannot tell what a reader needs; the human
bar is that every line changes what the reviewer does next — look here first,
watch this risk, trust this number. Lines that only prove the work happened
belong elsewhere:

- a walkthrough of files/functions touched (the diff shows it);
- full verification logs and pass-count matrices (CI shows them);
- an inventory of behavior left unchanged or deferred (silence is fine);
- a summary repeating Part 1.

## Example

A small bug fix, whole body:

```md
# Changes

## Bug Fix

- Fix `index_select` with an empty mask and `bool_select` with an all-false
  mask panicking on zero-size axes; both now return an empty selection.

# Details

- The panic came from `dim_select(axis, 0)` on a zero-size axis; the fix uses
  `dim_chop`.
```

## Attribution

End the body with the Agent/Model block (`PR summarized by`); its format and
registry live in skill `git-commit-coauthor`. Use that block as the PR footer,
rather than a vendor `Generated with ...` footer.
