"""BULC-D orchestration - the legacy `afn_BULCD` equivalent.

Glues the two other new modules together, matching the legacy's real
split (see legacy/BULCD-Caller-Current.txt): `organize_inputs()`
(bulcd/inputs.py) produces the target period's z-score stream (scored
against the expectation period's fitted model - the restored
expectation/target split, docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md);
this module bins that stream and looks each bin up against the
hand-tuned "custom transition matrix" (Willis 2022 - see CLAUDE.md
"Reference papers") to build the per-timestep "update factor" images
that `bulcd/bulc.py`'s generic engine folds through Bayes' formula. No
logic here changed with 0010's restoration - this module only ever
consumed whatever z-score stream `organize_inputs()` handed it, which is
now typically a short single-season sequence instead of a multi-decade
one.

VALIDATED against real Earth Engine at four real test pixels AND one
full-AOI disturbance map - see CLAUDE.md "First live-EE verification" /
"Known-burn validation" / "Moderate-severity test" / "Major finding:
long stable baselines can mask real disturbance" / "Disturbance map"
(all under the prior continuous-stream design, docs/decisions/0003, now
superseded - revalidation against the restored split is still open).
`run_bulcd()` passes `recency_factor` through to `bulc.run_bulc()` - an
optional, off-by-default extension beyond the reconstructed classic
method, added to address a real, empirically-found failure mode of long
continuous streams that mostly can't occur now that target periods are
short again (see docs/decisions/0010's consequences) - and
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

# Hansen Global Forest Change's "treecover2000" band: % canopy cover as of
# year 2000. 10% is FAO's common minimum-canopy "forest" definition
# threshold, not a value taken from the legacy source - we don't have
# mckenzeBULCD.rtf's real forestMask asset either, so this is a standard
# public substitute, same posture as _water_mask(). See _forest_mask()'s
# docstring.
_FOREST_COVER_THRESHOLD = 10.0
_HANSEN_ASSET_ID = "UMD/hansen/global_forest_change_2025_v1_13"

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
    is the simplest correct implementation - no need for a general lookup.

    MAJOR BUG FIXED 2026-08-10: `band` starts as a fully-valid
    `ee.Image.constant(...)` (bin 1's value), and `.where(cond, value)`
    silently falls back to that starting value wherever `cond`
    (`binned_image.eq(bin_number)`) is masked - it does NOT propagate
    `binned_image`'s own mask through the chain. CONFIRMED via direct
    testing: a masked z-score/bin (no satellite data that day) produced
    update_factors of `[0.83, 0.08, 0.08]` - bin 1's row, the single most
    extreme "decrease" value in the entire matrix - instead of staying
    masked. Every masked/no-data step was silently injected into
    `bulc.run_bulc()`'s sequential fold as maximum-confidence "decrease"
    evidence rather than the intended no-op. This was found to be the
    dominant, previously-undetected explanation for cell 8C's persistent
    "decrease"-heavy classification despite seven other confirmed,
    validated fixes (posterior_leveler, initializing_leveler, z-score
    formula, dayStepSize, modality, R2, cloud masking) - a hand-traced
    Python simulation of the real per-pixel bin sequence, correctly
    treating masked steps as no-ops, produced `unchanged`-dominant
    results matching the evidence and the GUI's render; only forcing the
    real (buggy) mask-defaulting behavior reproduced the observed
    `decrease`-dominant discrepancy. The `.updateMask()` call below
    forces the output to actually respect `binned_image`'s mask.
    """
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

    return ee.Image.cat(class_images).updateMask(binned_image.mask())


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


def _forest_mask(region: ee.Geometry, forest_mask_asset: str | None) -> ee.Image:
    """Boolean mask, True where land cover IS forest.

    Legacy equivalent: mckenzeBULCD.rtf's `forestMask` parameter
    (`StudyAreaConfig.forest_mask_asset`) - if the caller supplied that
    asset, use it directly (treated as a boolean/binary image: nonzero =
    forest). Otherwise falls back to the standard public Hansen Global
    Forest Change dataset's treecover2000 band, thresholded - we don't
    have the legacy's real forestMask asset, so this is a substitute, same
    posture as _water_mask(). Added 2026-07-30 after a real disturbance
    export (cell 2F, year 2025) showed false "change" above treeline -
    bare rock/permanent snow-ice terrain the forest-tuned harmonic
    expectation model was never fit to represent. Confirmed this isn't a
    seasonal snow-contamination issue (narrowing the evidence DOY window
    to peak summer did not remove the artifact) - it's a land-cover
    mismatch, which only an actual forest/non-forest mask fixes.
    """
    if forest_mask_asset:
        return ee.Image(forest_mask_asset).clip(region).selfMask().unmask(0).gt(0)
    tree_cover = ee.Image(_HANSEN_ASSET_ID).select("treecover2000").clip(region)
    return tree_cover.gte(_FOREST_COVER_THRESHOLD)


def study_area_mask(config: BULCDConfig) -> ee.Image | None:
    """Combined water/non-forest mask per `StudyAreaConfig.mask_water`/
    `mask_non_forest`, or None if both are off.

    `run_bulcd()` applies this to `final_probabilities` automatically, but
    `classification_stack`/`probability_stack`/`organize_inputs()`'s
    `lof_zscore` do NOT go through that step - any caller building an
    output image directly from those (e.g. bulcd/interpret.py's
    year_of_change()/zscore_anomaly_mask_for_year()) needs to apply this
    mask itself. Added 2026-07-30 alongside `mask_non_forest` after
    scripts/export_year_disturbance_map.py's first real export was found
    to have neither mask applied - a real gap, not by design.
    """
    if not (config.study_area.mask_water or config.study_area.mask_non_forest):
        return None
    region = resolve_study_area(config.study_area)
    mask = ee.Image.constant(1)
    if config.study_area.mask_water:
        mask = mask.And(_water_mask(region))
    if config.study_area.mask_non_forest:
        mask = mask.And(_forest_mask(region, config.study_area.forest_mask_asset))
    return mask


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
        zscore_image = ee.Image(zscore_image)
        binned = _bin_zscore(zscore_image.select("zscore"), config.bin_cuts)
        update_factors = _bin_to_update_factors(binned, advanced.custom_transition_matrix)
        # ee.Image.cat() (inside _bin_to_update_factors) doesn't carry
        # forward zscore_image's system:time_start - none of its inputs
        # (ee.Image.constant()/.where() chains) are derived from it. Without
        # this, every downstream bulc.run_bulc() step would be undated (see
        # CLAUDE.md "Year of change").
        return update_factors.set("system:time_start", zscore_image.get("system:time_start"))

    update_factor_collection = organized.lof_zscore.map(_to_update_factors)

    # CONFIRMED 2026-08-10 (6003.3c-BULC-AdvancedParameters real source):
    # production's baseLandCoverImage = ee.Image(2), a hardcoded one-hot
    # "unchanged" starting class (not derived from this AOI/run at all),
    # leveled by initializing_leveler via the same dampen()-shaped formula
    # as everything else. At the default initializing_leveler=0.0, dampen()
    # collapses this to flat uniform regardless of which class is one-hot -
    # identical to this rebuild's prior behavior, so this is backward
    # compatible until a caller opts in.
    one_hot_unchanged = ee.Image.cat(
        [
            ee.Image.constant(1.0 if name == "unchanged" else 0.0).rename(name)
            for name in _DECISION_CLASS_NAMES
        ]
    )
    initial_prior = bulc.dampen(one_hot_unchanged, advanced.initializing_leveler)

    result = bulc.run_bulc(
        update_factor_collection,
        initial_prior,
        dampening_factor=advanced.dampening_factor,
        recency_factor=advanced.recency_factor,
        posterior_leveler=advanced.posterior_leveler,
    )

    mask = study_area_mask(config)
    if mask is not None:
        result.final_probabilities = result.final_probabilities.updateMask(mask)

    return result
