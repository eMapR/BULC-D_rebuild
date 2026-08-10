"""Generic Bayesian updating engine - the low-level `BULC` core BULC-D wraps.

Implements Cardille & Fortin (2016, *Remote Sensing of Environment* 186)
directly (see CLAUDE.md "Reference papers" for the full math this is a
straight port of, Equations 1/2 and section 4.6's dampening factor). This
module is deliberately index/sensor/algorithm AGNOSTIC - it has no idea
what a z-score, a collection bin, or a burn index is. It only knows about
a running per-pixel, per-class probability vector (the "prior") and a
sequence of per-timestep "update factor" images that provide new evidence
to fold in via Bayes' formula. This mirrors the legacy's actual module
split: the still-unfetched `BULC-Minimal-Module-107` (this module's real
counterpart) vs. `afn_BULCD` (bulcd/engine.py's counterpart, which is
where z-scores/bins/transition-matrices belong).

In classic BULC, an "update factor" image is a row of a confusion matrix
built by cross-tabulating two classified Events (Producer's Accuracy per
class). In BULC-D, it's instead a row of a fixed, hand-tuned "custom
transition matrix" selected by a continuous index's z-score bin (see
bulcd/engine.py). Either way, from this module's point of view they're
just conditional-probability images - P(new evidence | each prior class)
- which is all Eq. 2 needs.

IMPORTANT band-order contract: `initial_prior` and every image in
`update_factor_collection` must carry the same number of bands, IN THE
SAME ORDER (Earth Engine's multi-band arithmetic pairs bands positionally,
not by name, when both operands have equal band counts) - the class
labels/order are entirely the caller's responsibility. BULC-D's engine.py
uses the convention [decrease, unchanged, increase] (matching the legacy
caller script's `finalBulcProbs.select(0/1/2)` band-index usage, verified
in legacy/BULCD-Caller-Current.txt).

VALIDATED against real Earth Engine at four real test pixels (see
CLAUDE.md "First live-EE verification" / "Known-burn validation" /
"Moderate-severity test" / "Major finding: long stable baselines can
mask real disturbance").

`discount()`/`run_bulc()`'s `recency_factor` parameter is NOT part of
Cardille & Fortin (2016) or Willis (2022) - it's a genuine algorithmic
addition made 2026-07-30 to address a real, empirically-found failure
mode (see CLAUDE.md "Recency weighting" below), not a port of anything
in the reconstructed source material. Defaults to `1.0` (off), so the
engine is faithful to the reconstructed classic method unless a caller
opts in - "preserve the Bayesian updating core" (CLAUDE.md modernization
goal) means this should never be silently on.

`run_bulc()`'s `posterior_leveler` parameter, by contrast, IS part of
the real classic method - confirmed 2026-08-10 against the actual
BULC-Minimal-Module-107 source (legacy/BULC-Minimal-Module-107.txt).
Production's per-step loop (`afn_hiddenBULCIterateWithOptions`) applies
a SECOND dampening step to the posterior after every Bayes update
(`afn_dayIRebalancingV3`), separate from the transition-table dampening
`dampening_factor`/`dampen()` already models. Without it, posteriors can
compound toward unbounded confidence over many sequential steps in a way
production's own math never allows - see `dampen()`'s docstring and
docs/decisions/ for the full story. Defaults to `1.0` (no-op) pending
empirical validation, same rollout discipline as `dampening_factor`.
"""

from __future__ import annotations

from dataclasses import dataclass

import ee


@dataclass
class BulcResult:
    """Output of a full run_bulc() pass over an update-factor collection.

    `probability_stack`/`classification_stack` are ee.ImageCollection,
    not Python lists - the number of update-factor images isn't known
    client-side without an extra network round trip, and ee.ImageCollection
    is the natural, idiomatic container for "one image per timestep" in
    Earth Engine (freely convertible to a flattened multi-band ee.Image via
    .toBands() downstream if a caller wants that shape instead). This is a
    deliberate divergence from the legacy's single multi-band Image fields
    (`allBULCLayers`/`allProbabilityLayers`) toward something more directly
    useful for "expose intermediate probability/uncertainty surfaces, not
    just a final change map" (Vision doc modernization goal).
    """

    final_probabilities: ee.Image
    probability_stack: ee.ImageCollection
    classification_stack: ee.ImageCollection


def dampen(image: ee.Image, leveler: float) -> ee.Image:
    """Cardille & Fortin (2016) section 4.6: `d * t + (1 - d) / n_classes`.

    Generic re-leveling toward uniform - used TWICE in run_bulc(), matching
    two distinct steps confirmed in the real BULC-Minimal-Module-107 source
    (legacy/BULC-Minimal-Module-107.txt): once on the incoming update
    factors before the Bayes update (`dampening_factor` /
    production's `transitionLeveler`+`transitionMinimum`), and again on the
    resulting posterior after it (`posterior_leveler` / production's
    `posteriorLeveler`+`posteriorMinimum`, via `afn_dayIRebalancingV3`).
    Both are literally the same formula in production - confirmed by the
    numbers (`posteriorMinimum` 0.0333... = `(1-0.9)/3`,
    `transitionMinimum` 0.1 = `(1-0.7)/3`) - so one function serves both.

    The paper's own example: d=0.5 turned Burn's [0.79, 0.11, 0.32] update
    factors into [0.56, 0.22, 0.33]. leveler=1.0 is a no-op - the image
    passes through unchanged - but 1.0 is NOT dampening_factor's default
    upstream (see BULCAdvancedParams): a first live-EE run found no
    dampening produces extreme overconfidence over many sequential
    Events, so its default is 0.5, matching the paper's own tested value.
    """
    if leveler == 1.0:
        return image
    n_classes = image.bandNames().size()
    uniform_share = ee.Image.constant(1).divide(n_classes)
    return image.multiply(leveler).add(uniform_share.multiply(1 - leveler))


def bayes_update(prior: ee.Image, update_factors: ee.Image) -> ee.Image:
    """One step of Cardille & Fortin (2016) Eq. 2.

    posterior_c = update_factors_c * prior_c / sum_c(update_factors_c * prior_c)

    Missing data (update_factors masked at a pixel, e.g. cloud/no coverage
    at that timestep) leaves that pixel's prior probabilities unchanged -
    the paper's explicit rule (section 3.1/4.5), not a fallback hack.
    `.unmask(prior)` implements this directly: wherever the computed
    posterior is masked (because update_factors was masked there), the
    corresponding prior pixel value fills it in - exact per Eq. 2's silence
    on missing Events.
    """
    weighted = prior.multiply(update_factors)
    total = weighted.reduce(ee.Reducer.sum())
    posterior = weighted.divide(total)
    return posterior.unmask(prior)


def discount(probabilities: ee.Image, recency_factor: float) -> ee.Image:
    """Power-discounts a probability image so older accumulated evidence's
    influence decays geometrically relative to more recent evidence.

    posterior_c = probabilities_c^gamma / sum_c(probabilities_c^gamma)

    NOT part of the reconstructed classic BULC method (see module
    docstring) - an addition found 2026-07-30 to address a real failure
    mode: over long, mostly-stable evidence streams, many years of mild
    "confirm normal" evidence can compound (via repeated bayes_update()
    calls) into a lead that a later, genuine, sustained disturbance can't
    overturn even with aggressive dampening (see CLAUDE.md "Major
    finding"). Applying this after every bayes_update() call means each
    single step's influence on the running posterior decays by a factor
    of `recency_factor` for every subsequent step - so evidence from N
    steps ago carries roughly `recency_factor^N` of its original weight,
    while the most recent step is never discounted. recency_factor=1.0
    is a no-op (exact classic behavior, no decay).

    Verified empirically at four real test pixels: recency_factor=0.98
    flips a previously-invisible 9-year disturbance (masked by a 14-year
    stable baseline) to a correct classification, while leaving two
    unambiguous cases (a stable pixel, a confidently-detected real fire)
    correctly classified with high confidence, and leaving a genuinely
    ambiguous moderate-severity case appropriately unstable across nearby
    values - full comparison table in CLAUDE.md.
    """
    if recency_factor == 1.0:
        return probabilities
    discounted = probabilities.pow(recency_factor)
    total = discounted.reduce(ee.Reducer.sum())
    return discounted.divide(total)


def _argmax_label(probabilities: ee.Image) -> ee.Image:
    """Cardille & Fortin (2016) section 2.5: the BULC "classification" at
    any time step is just argmax over the current probability vector."""
    return probabilities.toArray().arrayArgmax().arrayGet([0]).rename("class")


def run_bulc(
    update_factor_collection: ee.ImageCollection,
    initial_prior: ee.Image,
    dampening_factor: float = 0.5,
    recency_factor: float = 1.0,
    posterior_leveler: float = 1.0,
) -> BulcResult:
    """Folds bayes_update() over a time-ordered update-factor collection.

    `update_factor_collection` must already be sorted by time (the caller's
    responsibility - bulcd/engine.py sorts via assemble_evidence_collection()
    upstream) and its images must match initial_prior's band count/order
    (see module docstring). `recency_factor` defaults to 1.0 (off, no
    departure from the reconstructed classic method) - see discount()'s
    docstring before turning it on. `posterior_leveler` also defaults to
    1.0 (no-op) pending empirical validation, but unlike recency_factor IS
    part of the real classic method (see module docstring and dampen()'s
    docstring) - production applies it after every Bayes update, not just
    dampening_factor's pre-update step.
    """

    def _step(image: ee.Image, accumulator: ee.Dictionary) -> ee.Dictionary:
        accumulator = ee.Dictionary(accumulator)
        prior = ee.Image(accumulator.get("prior"))
        probability_stack = ee.List(accumulator.get("probability_stack"))
        classification_stack = ee.List(accumulator.get("classification_stack"))

        source_image = ee.Image(image)
        dampened = dampen(source_image, dampening_factor)
        posterior = bayes_update(prior, dampened)
        posterior = dampen(posterior, posterior_leveler)
        posterior = discount(posterior, recency_factor)
        classification = _argmax_label(posterior)

        # Carry the source Event's date onto both outputs - neither is
        # otherwise dated, since both are built from arithmetic on `prior`/
        # `dampened` rather than derived from `source_image` directly. This
        # is what lets a caller later ask "which year did this pixel's
        # classification change" (bulcd/interpret.py) instead of only ever
        # seeing the final accumulated posterior. copyProperties() does NOT
        # work for this - it only copies non-system properties even when
        # named explicitly, silently dropping "system:time_start" - .set()
        # is required for system properties.
        event_time = source_image.get("system:time_start")
        posterior = posterior.set("system:time_start", event_time)
        classification = classification.set("system:time_start", event_time)

        return ee.Dictionary(
            {
                "prior": posterior,
                "probability_stack": probability_stack.add(posterior),
                "classification_stack": classification_stack.add(classification),
            }
        )

    initial_accumulator = ee.Dictionary(
        {
            "prior": initial_prior,
            "probability_stack": ee.List([]),
            "classification_stack": ee.List([]),
        }
    )

    result = ee.Dictionary(update_factor_collection.iterate(_step, initial_accumulator))

    return BulcResult(
        final_probabilities=ee.Image(result.get("prior")),
        probability_stack=ee.ImageCollection(ee.List(result.get("probability_stack"))),
        classification_stack=ee.ImageCollection(
            ee.List(result.get("classification_stack"))
        ),
    )
