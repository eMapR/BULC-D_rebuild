"""Post-run analysis of a BULC-D result - the legacy `afn_interpretBULCDResult`
equivalent. Unlike every other module this rebuild is built against, the
REAL source for this one is fetched: `6002.C2-BULCD-Module-analyzeOutputs`
(`alemlakes`'s `r-2902-Dev` repo), saved at
`legacy/6002.C2-BULCD-Module-analyzeOutputs.txt`. This module is a partial
port of it, not a reconstruction from papers like most of the rest of this
package.

REWORKED 2026-08-18 for the restored expectation/target split
(`docs/decisions/0010`) - and, in the course of that rework, corrected
against the real source above (previously only its EXISTENCE and general
"first crossing, no persistence" shape were known - see CLAUDE.md's
`r-2902-Dev` entry, fetched 2026-08-10 but not yet acted on here). Two
real, load-bearing corrections came out of reading it directly:

1. **Production's `wasItEver`/timing analysis reads the raw PROBABILITY
   stack, thresholded per-class, not the argmax classification.** The
   real source's `wasItEver` (line 20-47) and "timing"/`firstChange`
   section (line 90-145) both operate on `probabilityStackThroughTime`
   (this rebuild's `bulc.py` `BulcResult.probability_stack` - each Event's
   full 3-band posterior, band-selected by class name, e.g. `probCls1` for
   "down"/decrease) compared against a threshold
   (`wasItEverValue`/`timingThreshold`) - never on a derived
   per-Event argmax "winning class" the way the previous version of this
   module (and `classification_stack`) did. This module's functions now
   take `probability_stack`, not `classification_stack`, to match.
2. **"When did it change" is the FIRST threshold crossing, no unbroken-run
   requirement** (`firstChange`, line 110-137: `changeIndices.reduce(ee.Reducer.min())`
   over per-Event indices where `prob1.gt(timingThreshold)`) - confirming
   what CLAUDE.md already flagged from the 2026-08-10 fetch. This directly
   replaces the previous `year_of_change()`, which searched for a
   PERSISTENT run holding through the end of the stack - a materially
   different, stricter question the real source does not ask, and which
   was already known to lag real disturbances by over a decade under the
   old long-continuous-stream design (`docs/findings.md`'s "Year of
   change" entry). `first_change_year()` below is the real definition;
   under the restored short target-period design, it also naturally
   answers what `docs/decisions/0010` called the collapsed "did it change
   within this target window" question - the target period usually spans
   one calendar year, so a match anywhere returns that one year.

Not a full port: still missing are the exact production threshold VALUES
(`dropThresholdToDenoteChange`/`gainThresholdToDenoteChange`/
`timingThreshold`, part of the still-unfetched `BULCD-AnalysisParameters-v5`)
- `threshold` is a required argument below, not defaulted, rather than
guess a number with no source. Also not ported: the DOY-based date
conversion (`orangeDateDOY`, which reconstructs a calendar date from a
step index via `dayStepSize`/`targetFirstDOY` because production's
`probabilityStackThroughTime` bands aren't independently dated) - this
rebuild's `probability_stack`/`classification_stack` Events already carry
real `system:time_start` dates (`bulc.py`'s `_step()`), so
`first_change_year()` reads the real calendar year directly instead of
reconstructing one; and the raw-index magnitude sanity check
(`largeDropOrange`, which additionally requires the target period's mean
index below a threshold AND the expectation period's mean index above
one) - would need `organize_inputs()` to expose per-period mean index
images, which it doesn't yet.

`zscore_anomaly_mask()` is the other, independent "was pixel abnormal"
question living in this module, at a different pipeline layer - not
present in the real source above at all (it's this rebuild's own fast/
noisy alternative to the Bayesian layer, still just a documented
reconstruction, same posture as `organize_inputs()`). It reads
`organize_inputs()`'s per-image z-score stream (`lof_zscore`) directly, no
Bayesian accumulation. Since `organize_inputs()` now scores z-scores over
the target period's collection only (`docs/decisions/0010`), this no
longer needs its own year filter - the collection passed in is already
scoped to the window being asked about, same as `probability_stack`.
"""

from __future__ import annotations

import ee

_COMPARISONS = {
    "gt": lambda image, value: image.gt(value),
    "gte": lambda image, value: image.gte(value),
    "lt": lambda image, value: image.lt(value),
    "lte": lambda image, value: image.lte(value),
    "eq": lambda image, value: image.eq(value),
    "neq": lambda image, value: image.neq(value),
}

# Far larger than any realistic Event count (even the old, superseded
# multi-decade continuous-stream design topped out around a few hundred) -
# used in first_change_year() to mark "never matched" positions so a plain
# min() reducer can distinguish them from a real, small, matched index
# without production's own index+1/-1 offset dance (see that function).
_UNMATCHED_SENTINEL = 1_000_000


def _matched_events(
    probability_stack: ee.ImageCollection, class_name: str, threshold: float, comparison: str
) -> ee.ImageCollection:
    if comparison not in _COMPARISONS:
        raise ValueError(f"comparison must be one of {sorted(_COMPARISONS)}, got {comparison!r}")
    compare = _COMPARISONS[comparison]
    return probability_stack.select(class_name).map(lambda image: compare(image, threshold))


def _event_years(image_collection: ee.ImageCollection) -> ee.List:
    """Calendar year of each Event, in the same time order as the collection.

    All pixels in a given run share the same sequence of Event dates (one
    evidence collection per AOI, not per pixel), so this is a single
    collection-wide list, not a per-pixel value. Requires every image to
    carry `system:time_start`, which `bulc.run_bulc()` sets on every
    `probability_stack`/`classification_stack` Event.
    """
    event_millis = image_collection.aggregate_array("system:time_start")
    return event_millis.map(lambda millis: ee.Date(millis).get("year"))


def was_it_ever(
    probability_stack: ee.ImageCollection,
    class_name: str,
    threshold: float,
    comparison: str = "gt",
) -> ee.Image:
    """Direct port of the real source's `wasItEver`/`howOftenWasIt`
    (`legacy/6002.C2-BULCD-Module-analyzeOutputs.txt` lines 20-47).

    Returns a 2-band image: "was_it_ever" (boolean - True if ANY Event's
    `class_name` probability satisfies `comparison threshold`, e.g.
    `class_name="decrease", threshold=0.5, comparison="gt"` for "was this
    pixel ever more than 50% likely to be decreasing") and
    "how_often_was_it" (fraction of Events that matched, 0-1).

    `class_name` is one of `bulcd/engine.py`'s `_DECISION_CLASS_NAMES`
    ("decrease"/"unchanged"/"increase") - `probability_stack`'s band
    names, confirmed by `bulc.py`'s band-order contract (see that
    module's docstring).
    """
    matches = _matched_events(probability_stack, class_name, threshold, comparison)
    match_count = matches.sum()
    n_events = probability_stack.size()
    was_it_ever_band = match_count.gte(1).rename("was_it_ever")
    how_often_band = match_count.divide(n_events).rename("how_often_was_it")
    return ee.Image.cat([was_it_ever_band, how_often_band])


def first_change_year(
    probability_stack: ee.ImageCollection,
    class_name: str,
    threshold: float,
    comparison: str = "gt",
) -> ee.Image:
    """Per-pixel calendar year of the FIRST Event where `class_name`'s
    probability satisfies `comparison threshold` - the real source's
    `firstChange` logic (`legacy/6002.C2-BULCD-Module-analyzeOutputs.txt`
    lines 110-137), with no persistent-run requirement: a single Event
    crossing the threshold is enough, even if a later Event doesn't.

    Masked wherever no Event ever crosses (there's no "year of change" for
    a pixel that never showed the signal). Under the restored, typically
    single-season target period, this usually resolves to one candidate
    year - the target period's own year - but generalizes correctly for a
    wider or non-contiguous target window.
    """
    matches = _matched_events(probability_stack, class_name, threshold, comparison)
    # ImageCollection.toArray() produces a 2-D array per pixel (image axis
    # x band axis), even though `class_name` selects a single band -
    # arrayProject([0]) collapses the size-1 band axis away, leaving a
    # plain 1-D time series (same idiom as bulc.py's array-image usage).
    match_array = matches.toArray().arrayProject([0])
    n_events = probability_stack.size()

    index_seq = ee.Array(ee.List.sequence(0, n_events.subtract(1)), ee.PixelType.float())
    position = ee.Image(index_seq)
    not_matched = match_array.multiply(-1).add(1)
    # Matched positions keep their own (small) index; unmatched positions
    # get pushed to a value no real index could reach - lets a plain
    # min() reducer read off "the first matched index" directly, with
    # "never matched" reading back out as the sentinel itself.
    candidate = position.multiply(match_array).add(not_matched.multiply(_UNMATCHED_SENTINEL))

    first_index = candidate.arrayReduce(ee.Reducer.min(), [0]).arrayGet([0])
    ever_matched = first_index.lt(_UNMATCHED_SENTINEL)
    # Clamp so arrayGet never sees an out-of-range index - the clamped
    # value is discarded anyway via the mask below.
    first_index = first_index.max(0).min(n_events.subtract(1)).toInt()

    years = ee.Array(_event_years(probability_stack), ee.PixelType.float())
    first_year = ee.Image(years).arrayGet([first_index]).rename("first_change_year")
    return first_year.updateMask(ever_matched)


def disturbance_mask_for_year(
    probability_stack: ee.ImageCollection,
    year: int,
    class_name: str,
    threshold: float,
    comparison: str = "gt",
) -> ee.Image:
    """Boolean mask: True where `first_change_year()` equals `year`
    exactly - i.e. pixels whose first threshold crossing into
    `class_name` happened in that specific calendar year."""
    return (
        first_change_year(probability_stack, class_name, threshold, comparison)
        .eq(year)
        .rename("disturbance_mask")
    )


def zscore_anomaly_mask(zscore_collection: ee.ImageCollection, threshold: float = -2.0) -> ee.Image:
    """Boolean mask: True where ANY image in `zscore_collection` (typically
    `organize_inputs()`'s `lof_zscore`, already scoped to the target
    period) has a z-score at or below `threshold` (default -2, matching
    the pipeline's own `bin_cuts` default's most extreme cut - see
    bulcd/config/schema.py).

    This is the FAST layer, not the robust one: no Bayesian accumulation
    across Events at all, so it answers "was this window's data abnormal
    versus the expectation baseline," immediately, the moment the imagery
    exists. Unlike `was_it_ever()`/`first_change_year()`, a single
    cloud-shadow-contaminated or otherwise noisy image can trigger this
    just as readily as a real disturbance - there's no sustained-evidence
    requirement to filter that out. See module docstring for why both
    layers exist and when to use which.
    """
    min_zscore = zscore_collection.select("zscore").min()
    return min_zscore.lte(threshold).rename("zscore_anomaly")
