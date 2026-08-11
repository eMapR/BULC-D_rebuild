# 0003 — Continuous Evidence Stream + Global Expectation Baseline Window (Replaces Legacy's Expectation/Target Split)

**Status:** Decided 2026-07-29. **Superseded 2026-08-11 by
[0010](0010-restore-expectation-target-split-for-gui-parity.md)**, per
explicit direction that the rebuild should match the legacy GUI's
structure as closely as possible, not just its formulas. Kept here as the
historical record of why the continuous-stream design was chosen in the
first place — the reasoning below no longer reflects the implemented
schema.

## Context

The legacy's core method treats a short "expectation" window of imagery
as ground truth for "normal, undisturbed forest," then compares one
separate, fixed "target" window against it — once. This is the exact
thing the Vision doc's primary modernization goal pushes against: "use
the full Landsat archive (1984–present) as continuous evidence," not a
discrete expectation-vs-target comparison.

The concept of an expectation model fit against which later imagery is
scored still has to exist somewhere in the new engine — it just needs to
work over a continuous stream instead of one fixed window.

## Decision

- The schema collapses expectation + target into one continuous
  per-sensor `EvidenceConfig` window per sensor.
- A single **global** `expectation_first_year`/`expectation_last_year`
  baseline window (not per-sensor, not derived from any sensor's own
  `first_year`/`last_year`) is applied as a plain date filter on the
  already-merged, sensor-agnostic evidence stream, and a harmonic
  regression is fit once against it.
- **The target period has no code representation at all.** The *same*
  fitted expectation curve is applied to score **every image in the
  entire evidence stream, forever** — including the baseline years
  themselves (a deliberate sanity check) and every year after, as far as
  the archive goes. Concretely, in `bulcd/inputs.py`:

  ```python
  harmonic_full = evidence_collection.map(_add_harmonic_terms)  # EVERY image
  expectation_fitted_collection = harmonic_full.map(
      lambda img: _add_fitted_band(img, fit.coefficients, fit.regressor_names)
  )
  lof_zscore = expectation_fitted_collection.map(_add_zscore).select("zscore")
  ```

  `bulcd/engine.py`'s `run_bulcd()` then bins each timestep's z-score and
  folds them through the sequential Bayesian updater one at a time. The
  legacy's single "expectation vs. one target period" comparison becomes
  a continuous *sequence* of comparisons — every image is its own
  mini-comparison against the same fixed expectation model, each one a
  fresh piece of evidence folded into the running posterior via Bayes'
  rule.
- `loader.py` validates the baseline window overlaps at least one enabled
  sensor's configured range, but the window itself is a deliberate
  domain/forest-history choice of which real calendar years count as
  "normal, undisturbed forest" for a given AOI — not something derived
  automatically.

## Consequences

This is the core structural change the rebuild hinges on — the literal
code-level meaning of "use the full Landsat archive as continuous
evidence." It is also the direct cause of a major downstream limitation:
see `docs/findings.md` "Major finding: long stable baselines can mask
real disturbance" and "Year of change... a major lag finding" — the
longer/more stable the chosen baseline, the harder a later genuine
disturbance is to detect under naive sequential Bayesian updating. See
also [0004](0004-dampening-factor-default-0.5.md) and
[0005](0005-recency-weighting-extension.md), both partial mitigations for
that consequence.
