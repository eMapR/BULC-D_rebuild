# 0007 — Posterior-Leveler Regularization: A Confirmed Missing Piece of the Real Method

**Status:** Implemented 2026-08-10, default not yet finalized

## Context

A real GUI-vs-rebuild comparison for cell 8C (`configs/cell_8c_comparison.yaml`)
surfaced a stark discrepancy: the rebuild's render came back ~95%
"decrease," the GUI's ~90% "unchanged" — looking inverted, not just
differently confident. Diagnosis ruled out an indexing/ordering bug (bin
assignment and matrix lookup both traced correctly against real z-scores
and dates) and instead found real z-score medians near-zero to slightly
*positive* at every sampled point, yet `final_probabilities` showing
`decrease` with confidence like `0.9999999999999998` against `10^-16` to
`10^-112` for the other two classes — an unbounded, runaway result, not
a plausible reading of near-neutral input data.

The user fetched `BULC-Minimal-Module-107`'s actual source
(`alemlakes/r-2909-BULC-Releases`, saved to
`legacy/BULC-Minimal-Module-107.txt`) directly from the GEE Code Editor.
It revealed that the real per-Event loop
(`afn_hiddenBULCIterateWithOptions`) applies dampening TWICE per step,
not once:

1. The transition table itself is pre-dampened
   (`transitionLeveler`/`transitionMinimum`) — this is what
   `BULCAdvancedParams.dampening_factor`/`bulc.py`'s `dampen()` already
   modeled correctly (see [0004](0004-dampening-factor-default-0.5.md)).
2. **The POSTERIOR is re-dampened after every single Bayes update**
   (`afn_dayIRebalancingV3`: `posterior*posteriorLeveler +
   posteriorMinimum`) — a second, separate regularization step
   `bulc.py` never implemented at all.

Both steps share the identical formula shape as `dampen()` — confirmed
by the real numbers: `posteriorMinimum (0.0333...) = (1 -
posteriorLeveler(0.9)) / 3`, `transitionMinimum (0.1) = (1 -
transitionLeveler(0.7)) / 3`. Without step 2, nothing bounds how extreme
the running posterior can get across many sequential steps — small,
non-adversarial biases in real data compound multiplicatively into
runaway confidence at the edge of float64 precision, exactly what was
observed.

## Decision

Add `posterior_leveler` as a new parameter: `bulc.py`'s `dampen()`
(already fully generic) is reused for both dampening steps rather than
writing a second function. `run_bulc()` applies
`dampen(posterior, posterior_leveler)` immediately after
`bayes_update()`, before the (unrelated, novel) `discount()`/
`recency_factor` step. Threaded through
`BULCAdvancedParams.posterior_leveler` (`config/schema.py`,
`config/loader.py`, validated `0 < x ≤ 1` identically to
`dampening_factor`/`recency_factor`), and `engine.py`'s `run_bulcd()`.

**Default stays `1.0` (no-op) for now** — same rollout discipline as
[0004](0004-dampening-factor-default-0.5.md)'s `dampening_factor`
history: implement with a safe, behavior-preserving default first,
validate empirically against real Earth Engine, then set a considered
default via a follow-up to this decision. Unlike
[0005](0005-recency-weighting-extension.md)'s `recency_factor`, this is
**not** a novel addition beyond the reconstructed method — it's a
confirmed, faithful piece of the real classic BULC algorithm that was
simply missing. That argues for eventually defaulting it to production's
real value (`0.9`) rather than treating it as permanently opt-in, but
that call is deferred until broader validation exists beyond the one
comparison run below.

## Consequences

VALIDATED at the three points from the original inversion finding
(cell 8C centroid + two solid-"decrease" sample points): confidence
dropped from the runaway `{decrease: 0.9999999999999998, unchanged:
1.3e-16, increase: 4.2e-84}` to a bounded, sane `{decrease: 0.914,
unchanged: 0.043, increase: 0.043}` — a dramatic, confirmed fix for the
overconfidence bug.

**Does not fully resolve the GUI-vs-rebuild disagreement.** The
plurality classification at all three points is still `decrease`, not
`unchanged` like the GUI. The real source also revealed a second,
separate gap this decision does NOT address: production initializes its
starting prior from a real `baseLandCoverImage` (one-hot per pixel,
leveled by `initializingLeveler`, also confirmed `0.7`), not a flat
uniform prior like `engine.run_bulcd()` currently constructs. What
`baseLandCoverImage` actually contains for a BULC-D run isn't given in
`BULC-Minimal-Module-107` itself (plausibly "assume unchanged," but
unconfirmed) — see `docs/findings.md` "BULC-Minimal-Module-107 obtained,
posterior_leveler fix" for the full writeup and next steps.
