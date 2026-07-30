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

NOT YET VALIDATED against real Earth Engine - see CLAUDE.md's standing
caveat on bulcd/inputs.py; same GEE-Cloud-project blocker applies here.
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


def dampen(update_factors: ee.Image, dampening_factor: float) -> ee.Image:
    """Cardille & Fortin (2016) section 4.6: `d * t + (1 - d) / n_classes`.

    Flattens update strength when classifications agree suspiciously well
    (the paper's own example: d=0.5 turned Burn's [0.79, 0.11, 0.32] update
    factors into [0.56, 0.22, 0.33]). dampening_factor=1.0 is a no-op - raw
    update factors pass through unchanged - but 1.0 is NOT the default
    upstream (see BULCAdvancedParams): a first live-EE run found no
    dampening produces extreme overconfidence over many sequential
    Events, so the default is 0.5, matching the paper's own tested value.
    """
    if dampening_factor == 1.0:
        return update_factors
    n_classes = update_factors.bandNames().size()
    uniform_share = ee.Image.constant(1).divide(n_classes)
    return update_factors.multiply(dampening_factor).add(
        uniform_share.multiply(1 - dampening_factor)
    )


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


def _argmax_label(probabilities: ee.Image) -> ee.Image:
    """Cardille & Fortin (2016) section 2.5: the BULC "classification" at
    any time step is just argmax over the current probability vector."""
    return probabilities.toArray().arrayArgmax().arrayGet([0]).rename("class")


def run_bulc(
    update_factor_collection: ee.ImageCollection,
    initial_prior: ee.Image,
    dampening_factor: float = 0.5,
) -> BulcResult:
    """Folds bayes_update() over a time-ordered update-factor collection.

    `update_factor_collection` must already be sorted by time (the caller's
    responsibility - bulcd/engine.py sorts via assemble_evidence_collection()
    upstream) and its images must match initial_prior's band count/order
    (see module docstring).
    """

    def _step(image: ee.Image, accumulator: ee.Dictionary) -> ee.Dictionary:
        accumulator = ee.Dictionary(accumulator)
        prior = ee.Image(accumulator.get("prior"))
        probability_stack = ee.List(accumulator.get("probability_stack"))
        classification_stack = ee.List(accumulator.get("classification_stack"))

        dampened = dampen(ee.Image(image), dampening_factor)
        posterior = bayes_update(prior, dampened)
        classification = _argmax_label(posterior)

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
