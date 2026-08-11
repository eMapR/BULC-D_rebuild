# 0009 — Two Mask-Propagation Bugs Were the Real Cause of Cell 8C's Classification Gap

**Status:** Implemented and validated 2026-08-10

## Context

Seven earlier confirmed, source-verified fixes this session
([0007](0007-posterior-leveler-regularization.md),
[0008](0008-day-step-size-temporal-binning.md), plus
`initializing_leveler`, the z-score denominator formula, additive
modality resolution, the adjusted R² formula, and per-sensor cloud
masking — see `docs/findings.md`) all validated correctly against real
production source but left cell 8C's classification `decrease`-dominant
(~82–91% at three test points), not matching the GUI's `unchanged`-
dominant render. Only `dayStepSize` binning ([0008](0008-day-step-size-temporal-binning.md))
produced meaningful movement; every other fix was inert to the decimal.

At the user's explicit direction ("yes, trace it", "use python to help
you"), the sequential Bayesian fold was hand-traced pixel-by-pixel in
plain Python against the real per-step bin sequence at the cell 8C
centroid (123 steps, 54 masked/no-data). A version treating masked steps
as true no-ops produced `unchanged`-dominant results matching the
evidence; only forcing the pipeline's actual (buggy) behavior reproduced
the observed `decrease`-dominant discrepancy. This isolated the bug to
mask handling, not any remaining formula/parameter mismatch.

**Bug 1 — `bulcd/engine.py`'s `_bin_to_update_factors()`.** Its `.where()`
chain starts from a fully-valid `ee.Image.constant(matrix[0])` and
conditions each subsequent `.where(binned_image.eq(n), ...)` on
`binned_image`, which is masked on no-data days. `.where(cond, value)`
does not propagate `cond`'s own mask onto the output — confirmed by
direct query at a known-masked date (2024-03-17, cell 8C centroid): the
function returned `[0.83, 0.08, 0.08]` (bin 1's row, the single most
extreme "decrease" value in the entire transition matrix) instead of
staying masked. Every no-data day (44% of steps at the centroid) was
silently injected into the Bayesian fold as maximum-confidence "decrease"
evidence.

**Bug 2 — `bulcd/bulc.py`'s `run_bulc()`'s `_step()`.** Even after fixing
Bug 1, `bayes_update()` immediately called `.unmask(prior)`, so a no-data
step's posterior became a fully-valid copy of `prior` before
`posterior_leveler`'s `dampen()` ran on it — pulling every no-data step's
"prior" partway toward uniform, when it should have been an exact
no-op. Confirmed against the real `BULC-Minimal-Module-107` source
(`legacy/BULC-Minimal-Module-107.txt` lines 590–600,
`afn_hiddenBULCIterateWithOptions`): production computes
`currentProbs.mask(oneEventValidValues)`, runs the Bayes ratio and
`afn_dayIRebalancingV3` (posterior_leveler) on that masked slice only,
and merges the result onto the *untouched* prior via
`.where(oneEventValidValues, posteriorProbsValidPixels1D)` — rebalance
happens strictly before the merge, never after.

## Decision

**Bug 1 fix:** `_bin_to_update_factors()` now ends with
`.updateMask(binned_image.mask())`, forcing the output to actually
respect the input's mask.

**Bug 2 fix:** `bayes_update()` no longer calls `.unmask(prior)` itself —
it now stays masked wherever `update_factors` is masked, matching
production's `currentProbs.mask(oneEventValidValues)` slice. `_step()`
applies `posterior_leveler`'s `dampen()` and `discount()` (both
mask-preserving arithmetic, so no-ops wherever still masked) to that
masked posterior, and only then calls `.unmask(prior)` once, at the very
end — mirroring production's rebalance-then-merge order exactly.

## Consequences

VALIDATED against real Earth Engine at the same three cell 8C points
used throughout this investigation. Bug 1 alone flipped the
classification from `decrease`-dominant to `unchanged`-dominant at all
three points for the first time in this investigation:

| Point | Before (all 7 prior fixes applied) | After Bug 1 fix |
|---|---|---|
| centroid | decrease 0.82 / unchanged 0.13 | decrease 0.128 / **unchanged 0.739** |
| red_pt_1 | (decrease-dominant) | decrease 0.097 / **unchanged 0.805** |
| red_pt_2 | (decrease-dominant) | decrease 0.203 / **unchanged 0.628** |

Bug 2 fix (on top of Bug 1) pushed all three points further toward
`unchanged`, closer still to the GUI's render:

| Point | After Bug 1 only | After Bug 1 + Bug 2 |
|---|---|---|
| centroid | unchanged 0.739 | **unchanged 0.906** |
| red_pt_1 | unchanged 0.805 | **unchanged 0.914** |
| red_pt_2 | unchanged 0.628 | **unchanged 0.833** |

Both bugs share a root cause worth naming explicitly: **Earth Engine's
mask propagation through `.where()`/`.unmask()` is not automatic and not
symmetric** — a masked *condition* does not mask its output, and
`.unmask(x)` unconditionally replaces masked pixels regardless of
whether that's the semantically correct fallback at that point in a
multi-step pipeline. Every EE image chain in this codebase that mixes
masked and valid inputs is worth re-auditing with this specific failure
mode in mind — these two were found via one deliberate trace at one
pixel, not an exhaustive audit.

Explains, in hindsight, why the seven earlier fixes validated correct
but stayed inert: none of them touched mask handling, so all seven were
real, correct improvements operating downstream of (and masked by) these
two bugs' dominant, systematically wrong "decrease" signal on every
no-data day. This is very likely the resolution of the entire cell 8C
investigation, though it remains validated at three points, not a
full-AOI or pixel-exhaustive comparison against the GUI's actual
rendered output.
