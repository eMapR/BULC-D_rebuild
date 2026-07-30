"""BULC-D orchestration - the legacy `afn_BULCD` equivalent.

Glues the two other new modules together, matching the legacy's real
split (see legacy/BULCD-Caller-Current.txt): `organize_inputs()`
(bulcd/inputs.py) produces a continuous z-score stream; this module bins
that stream and looks each bin up against the hand-tuned "custom
transition matrix" (Willis 2022 - see CLAUDE.md "Reference papers") to
build the per-timestep "update factor" images that `bulcd/bulc.py`'s
generic engine folds through Bayes' formula.

VALIDATED against real Earth Engine at four real test pixels AND one
full-AOI disturbance map - see CLAUDE.md "First live-EE verification" /
"Known-burn validation" / "Moderate-severity test" / "Major finding:
long stable baselines can mask real disturbance" / "Disturbance map".
`run_bulcd()` passes `recency_factor` through to `bulc.run_bulc()` - an
optional, off-by-default extension beyond the reconstructed classic
method, added to address a real, empirically-found failure mode - and
applies `_water_mask()` to the final output by default (matching the
legacy's always-on `afn_waterMask()`, whose source we don't have, against
the standard public JRC Global Surface Water dataset instead), after a
live disturbance map showed water bodies misclassified as "increase."
"""

from __future__ import annotations

import ee

from bulcd import bulc
from bulcd.config.schema import BULCDConfig
from bulcd.inputs import organize_inputs, resolve_study_area

# JRC Global Surface Water's "occurrence" band: % of 1984-2021 months
# observed as water. 50 is a common "seasonal to permanent water" cutoff,
# not a value taken from the legacy source - we don't have afn_waterMask()
# (legacy/BULCD-Caller-Current.txt)'s actual implementation, so this masks
# against a standard public dataset instead. See _water_mask()'s docstring.
_WATER_OCCURRENCE_THRESHOLD = 50.0

# Fixed band-order contract with bulc.py (see its module docstring):
# index 0 = decrease, 1 = unchanged, 2 = increase - matching the legacy
# caller's finalBulcProbs.select(0/1/2) usage (verified in
# legacy/BULCD-Caller-Current.txt).
_DECISION_CLASS_NAMES = ["decrease", "unchanged", "increase"]


def _bin_zscore(zscore_image: ee.Image, bin_cuts: list[float]) -> ee.Image:
    """Digitizes a continuous z-score image into bins 1..len(bin_cuts)+1
    (Willis 2022's 10 "collection bins" when bin_cuts has its default 9
    cut points) via chained greater-than comparisons."""
    bin_index = ee.Image.constant(1)
    for cut in bin_cuts:
        bin_index = bin_index.add(zscore_image.gt(cut))
    return bin_index.rename("bin")


def _bin_to_update_factors(
    binned_image: ee.Image, transition_matrix: list[list[float]]
) -> ee.Image:
    """Looks up each pixel's bin against transition_matrix's rows, producing
    the 3-band per-timestep update-factor image bulc.py consumes. Bins are a
    small fixed discrete set (1..10), so a chained .where() per class column
    is the simplest correct implementation - no need for a general lookup."""
    n_bins = len(transition_matrix)
    n_classes = len(transition_matrix[0])

    class_images = []
    for class_index in range(n_classes):
        band = ee.Image.constant(float(transition_matrix[0][class_index])).toFloat()
        for bin_number in range(2, n_bins + 1):
            band = band.where(
                binned_image.eq(bin_number), transition_matrix[bin_number - 1][class_index]
            )
        class_images.append(band.rename(_DECISION_CLASS_NAMES[class_index]))

    return ee.Image.cat(class_images)


def _water_mask(region: ee.Geometry) -> ee.Image:
    """Boolean mask, True where NOT water, per JRC Global Surface Water.

    Legacy equivalent: afn_waterMask() (legacy/BULCD-Caller-Current.txt),
    applied unconditionally before displaying/exporting finalBulcProbs -
    we don't have that module's source, so this uses the standard public
    JRC Global Surface Water dataset instead. Added 2026-07-30 after a
    live-EE disturbance map (see CLAUDE.md "Disturbance map") showed water
    bodies misclassified as "increase" - water's reflectance behaves
    nothing like the forest-tuned harmonic model this pipeline fits.
    """
    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").clip(region)
    is_water = occurrence.gt(_WATER_OCCURRENCE_THRESHOLD).unmask(0)
    return is_water.Not()


def run_bulcd(config: BULCDConfig) -> bulc.BulcResult:
    """Runs the full BULC-D pipeline: organize_inputs() -> bin + transition
    matrix -> bulc.run_bulc(). Raises ValueError up front if
    bulc_advanced_params.custom_transition_matrix isn't configured - there's
    no universal default (see BULCAdvancedParams docstring)."""
    advanced = config.bulc_advanced_params
    if advanced.custom_transition_matrix is None:
        raise ValueError(
            "run_bulcd() requires bulc_advanced_params.custom_transition_matrix to "
            "be set - see CLAUDE.md 'Reference papers' for Willis (2022)'s worked "
            "NBR12 example, but note it's index-specific, not a universal default "
            "(BAI needs a differently-shaped matrix per the same thesis)."
        )
    if len(config.bin_cuts) + 1 != len(advanced.custom_transition_matrix):
        raise ValueError(
            f"config.bin_cuts has {len(config.bin_cuts)} cut points (implying "
            f"{len(config.bin_cuts) + 1} bins) but custom_transition_matrix has "
            f"{len(advanced.custom_transition_matrix)} rows - these must produce "
            "the same number of bins."
        )

    organized = organize_inputs(config)

    def _to_update_factors(zscore_image: ee.Image) -> ee.Image:
        binned = _bin_zscore(ee.Image(zscore_image).select("zscore"), config.bin_cuts)
        return _bin_to_update_factors(binned, advanced.custom_transition_matrix)

    update_factor_collection = organized.lof_zscore.map(_to_update_factors)

    initial_prior = ee.Image.cat(
        [
            ee.Image.constant(1.0 / len(_DECISION_CLASS_NAMES)).rename(name)
            for name in _DECISION_CLASS_NAMES
        ]
    )

    result = bulc.run_bulc(
        update_factor_collection,
        initial_prior,
        dampening_factor=advanced.dampening_factor,
        recency_factor=advanced.recency_factor,
    )

    if config.study_area.mask_water:
        region = resolve_study_area(config.study_area)
        result.final_probabilities = result.final_probabilities.updateMask(
            _water_mask(region)
        )

    return result
