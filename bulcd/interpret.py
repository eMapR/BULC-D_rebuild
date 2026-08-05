"""Post-run analysis of a BULC-D result - the legacy `afn_interpretBULCDResult`
equivalent (module `6002.C2-BULCD-Module-analyzeOutputs`, owned by
`alemlakes`'s `r-2902-Dev` repo - we don't have that source; see CLAUDE.md
"Legacy source repos and what's still missing").

`bulcd/bulc.py`'s `classification_stack` is a time-ordered sequence of
per-Event argmax classifications, one integer "class" band per Event
(0=decrease, 1=unchanged, 2=increase - bulcd/engine.py's
`_DECISION_CLASS_NAMES` order). On its own it only answers "what's the
class right now" (`final_probabilities`) - it doesn't say WHEN a pixel's
classification changed, which is what a "disturbance in year Y" query
needs. This module adds that: `year_of_change()` finds, per pixel, the
calendar year of the earliest Event that begins an unbroken run of a
target class lasting through the end of the stack.

NOT a port of the real `afn_interpretBULCDResult` - a reconstruction
built to answer a specific, narrower question (change year), not the
legacy's full analysis surface ("was it ever," drop/gain probability,
etc.). Treat as a documented assumption pending the real source, same
posture as `organize_inputs()`.

Two genuinely different "was pixel abnormal in year Y" questions live in
this module, at two different layers of the pipeline (see CLAUDE.md "Year
of change" for the full discussion of why both exist):
  - `zscore_anomaly_mask_for_year()` reads `organize_inputs()`'s per-image
    z-score stream directly - immediate, no lag, but no protection against
    a single noisy/cloud-contaminated image.
  - `year_of_change()`/`disturbance_mask_for_year()` read the actual
    BULC-D sequential classification (`bulc.py`'s `classification_stack`)
    - noise-robust by design (that robustness IS the point of "preserve
    the Bayesian updating core"), but can lag a real disturbance by many
    years before the running classification commits to it (validated:
    12 years at default settings, at the known 2003 B&B Complex Fire
    point).
"""

from __future__ import annotations

import ee


def _event_years(classification_stack: ee.ImageCollection) -> ee.List:
    """Calendar year of each Event, in the same time order as the stack.

    All pixels in a given run share the same sequence of Event dates (one
    evidence collection per AOI, not per pixel), so this is a single
    collection-wide list, not a per-pixel value.
    """
    event_millis = classification_stack.aggregate_array("system:time_start")
    return event_millis.map(lambda millis: ee.Date(millis).get("year"))


def year_of_change(
    classification_stack: ee.ImageCollection, target_class_index: int = 0
) -> ee.Image:
    """Per-pixel calendar year of the start of a persistent run of
    `target_class_index` (default 0 = "decrease", bulcd/engine.py's
    convention) lasting through the LAST Event in the stack.

    Masked wherever the pixel's final Event isn't `target_class_index` -
    there's no "year of change" for a pixel that isn't currently classified
    as changed. This deliberately does NOT detect "changed, then recovered"
    - a pixel that flips to decrease and later flips back to unchanged
    before the stack ends has no persistent suffix run and is masked here,
    same as a pixel that never changed at all. That's a real limitation
    (see module docstring - the real `afn_interpretBULCDResult` likely
    handles this; we don't have its source), not an oversight: this
    function only answers "when did the CURRENT state begin," not a full
    change-history log.

    Requires `classification_stack` to carry `system:time_start` on every
    image, which `bulc.run_bulc()` has done since 2026-07-30 (see CLAUDE.md
    "Year of change") - an older classification_stack won't work here.
    """
    # pixelType is required (not just optional) here because the values are
    # a computed ee.List, not a Python literal - ee.Array can't infer a
    # numeric type from something it can't inspect client-side.
    years = ee.Array(_event_years(classification_stack), ee.PixelType.int32())
    n_events = classification_stack.size()

    # A plain 0..N-1 index sequence, built server-side (n_events is an
    # ee.Number, not known client-side) - same length/shape contract as
    # `years` above, both broadcast identically to every pixel.
    index_seq = ee.Array(ee.List.sequence(0, n_events.subtract(1)), ee.PixelType.float())

    # ImageCollection.toArray() produces a 2-D array per pixel (image axis x
    # band axis), even though "class" is a single band - arrayProject([0])
    # collapses the size-1 band axis away, leaving a plain 1-D time series.
    class_array = classification_stack.toArray().arrayProject([0])
    is_mismatch = class_array.neq(target_class_index)

    # arraySlice doesn't support a negative step (no native reverse), so
    # instead of scanning backward, find the LAST mismatching index directly:
    # at each position p, "(p+1) if mismatch else 0", then take the array
    # max. The result is (index of last mismatch)+1 - i.e. the first index
    # of the unbroken target-class run through the end of the series. If
    # there's no mismatch at all, this is 0 (the whole series is the target
    # class). If the very last position itself is a mismatch, this equals
    # n_events (one past the end) - out of range, which is exactly the
    # "no persistent run reaches the end" case and gets masked below.
    mismatch_position_plus_one = ee.Image(index_seq).add(1).multiply(is_mismatch)
    change_index = mismatch_position_plus_one.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0])

    is_currently_target = change_index.lt(n_events)
    # Clamp so arrayGet never sees an out-of-range index - the clamped value
    # is discarded anyway via the mask below.
    change_index = change_index.min(n_events.subtract(1)).max(0).toInt()

    years_image = ee.Image(years)
    change_year = years_image.arrayGet([change_index]).rename("change_year")

    return change_year.updateMask(is_currently_target)


def disturbance_mask_for_year(
    classification_stack: ee.ImageCollection, year: int, target_class_index: int = 0
) -> ee.Image:
    """Boolean mask: True where `year_of_change()` equals `year` exactly -
    i.e. pixels whose persistent shift to `target_class_index` began in
    that specific calendar year, not merely "changed by" that year (see
    year_of_change()'s docstring for what it does/doesn't capture)."""
    return year_of_change(classification_stack, target_class_index).eq(year)


def zscore_anomaly_mask_for_year(
    zscore_collection: ee.ImageCollection, year: int, threshold: float = -2.0
) -> ee.Image:
    """Boolean mask: True where ANY image within calendar year `year` has a
    z-score at or below `threshold` (default -2, matching the pipeline's
    own `bin_cuts` default's most extreme cut - see bulcd/config/schema.py).

    This is the FAST layer, not the robust one: it reads
    `organize_inputs()`'s per-image z-score stream (`lof_zscore`) directly,
    with no Bayesian accumulation across Events at all - so it answers "was
    this year's data abnormal versus the expectation baseline," immediately,
    the moment the imagery exists. Unlike `disturbance_mask_for_year()`, a
    single cloud-shadow-contaminated or otherwise noisy image can trigger
    this just as readily as a real disturbance - there's no sustained-
    evidence requirement to filter that out. See module docstring / CLAUDE.md
    "Year of change" for why both layers exist and when to use which.
    """
    year_start = f"{year}-01-01"
    year_end = f"{year + 1}-01-01"
    year_images = zscore_collection.filterDate(year_start, year_end)
    min_zscore = year_images.select("zscore").min()
    return min_zscore.lte(threshold).rename("zscore_anomaly")
