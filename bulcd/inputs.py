"""Assembles the continuous multi-sensor evidence stream BULC-D updates through.

This is a PARTIAL implementation. See CLAUDE.md "Legacy source repos and
what's still missing" for the full picture; summary:

REAL, WORKING:
  - `resolve_study_area()` — turns StudyAreaConfig into an ee.Geometry.
  - `assemble_evidence_collection()` — harmonized Landsat 5/7/8/9
    Collection 2 Level 2 surface reflectance, cloud-masked via
    QA_PIXEL, reduced to one spectral index (NBR/SWIR/NDVI per
    config.reduction.band), filtered to each sensor's configured
    continuous year range + seasonal day-of-year window, merged into
    one ee.ImageCollection sorted by time. This is the "full archive as
    continuous evidence" piece of the modernization.
  - Sentinel-2 (added 2026-08-10): `COPERNICUS/S2_SR_HARMONIZED` joined
    to `COPERNICUS/S2_CLOUD_PROBABILITY` and masked via the standard
    community s2cloudless recipe (Google's own tutorial -
    https://developers.google.com/earth-engine/tutorials/community/sentinel-2-s2cloudless,
    referenced by S2CloudMaskConfig's docstring) - cloud-probability
    threshold + NIR dark-pixel shadow projection, not a novel
    reconstruction. Same DOY/year-range/reduction-band handling as
    Landsat via the shared `_reduce_band`/`_date_bounds` helpers.

STUBBED, NOT IMPLEMENTED:
  - Sentinel-1, MODIS, ALOS, NICFI, Dynamic World collection assembly
    (`assemble_evidence_collection` raises NotImplementedError if one
    of these is enabled in config).

PARTIAL, PARTLY CONFIRMED AGAINST THE REAL SOURCE:
  - `organize_inputs()` — the legacy `afn_organizeBULCD_Inputs`
    equivalent: fits the expectation-period harmonic regression (shape
    selected by config.modality) against a global baseline window
    (config.evidence.expectation_first_year/last_year), then scores the
    ENTIRE continuous evidence stream into z-scores (per
    config.sensitivity) against that fit - the "continuous stream"
    piece is a deliberate modernization divergence from the legacy's
    discrete expectation/target split (see
    docs/decisions/0003-continuous-evidence-replaces-expectation-target-split.md),
    not something to reconcile against source. Its real implementation
    lives in `6002.A2b.3-BULCD-Module-organizeBULCD_Inputs`
    (`alemlakes/r-2903-Dev`), fetched 2026-08-10
    (see docs/findings.md "organizeBULCD_Inputs obtained"). Two formulas
    are now CONFIRMED against it, not reconstructed: `_zscore_image()`'s
    denominator is `max(residual_stddev, denominator_factor)` clamped to
    `[-10, 10]` (not an additive epsilon), and `_fit_expectation_model()`'s
    `residual_stddev` is a plain sample standard deviation (`n-1`) of the
    observed-minus-fitted residuals, not a regression residual-standard-error
    (`n - num_regressors`). Still NOT confirmed: modality-priority
    resolution when multiple `ModalityConfig` flags are true (the source
    calls out to a still-missing harmonic-functions module for this), and
    R2's exact formula (also delegated to that missing module) - both
    still flagged inline as documented assumptions against Cardille &
    Fortin 2016 / Willis 2022 (see CLAUDE.md "Reference papers").

Assumes `ee.Initialize(...)` has already been called by the caller —
this module never calls it itself, so it has no opinion about which
GEE Cloud project you're billed against.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass

import ee

from bulcd.config.schema import (
    BULCDConfig,
    EvidenceConfig,
    ModalityConfig,
    S2CloudMaskConfig,
    SensitivityConfig,
    SensorEvidenceConfig,
    StudyAreaConfig,
)

# Landsat Collection 2 Level 2 surface reflectance: common band name -> native
# band. TM/ETM+ (L5/L7) and OLI (L8/L9) number the same spectral regions
# differently.
_LANDSAT_COLLECTION_ID = {
    "L5": "LANDSAT/LT05/C02/T1_L2",
    "L7": "LANDSAT/LE07/C02/T1_L2",
    "L8": "LANDSAT/LC08/C02/T1_L2",
    "L9": "LANDSAT/LC09/C02/T1_L2",
}
_LANDSAT_BAND_MAP = {
    "L5": {"red": "SR_B3", "nir": "SR_B4", "swir1": "SR_B5", "swir2": "SR_B7"},
    "L7": {"red": "SR_B3", "nir": "SR_B4", "swir1": "SR_B5", "swir2": "SR_B7"},
    "L8": {"red": "SR_B4", "nir": "SR_B5", "swir1": "SR_B6", "swir2": "SR_B7"},
    "L9": {"red": "SR_B4", "nir": "SR_B5", "swir1": "SR_B6", "swir2": "SR_B7"},
}
# USGS Landsat Collection 2 Level-2 Science Product Guide scale/offset for
# converting DN to surface reflectance.
_LANDSAT_SR_SCALE = 0.0000275
_LANDSAT_SR_OFFSET = -0.2

# Approximate start of each sensor's usable archive - default lower bound
# when a sensor's config doesn't set first_year.
_SENSOR_LAUNCH_YEAR = {"L5": 1984, "L7": 1999, "L8": 2013, "L9": 2021, "S2": 2015}

# Sentinel-2 surface reflectance + its companion per-pixel cloud-probability
# collection (s2cloudless) - see S2CloudMaskConfig's docstring for the
# tutorial this cloud-masking recipe follows.
_S2_SR_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
_S2_CLOUD_PROB_COLLECTION_ID = "COPERNICUS/S2_CLOUD_PROBABILITY"
_S2_BAND_MAP = {"red": "B4", "nir": "B8", "swir1": "B11", "swir2": "B12"}
_S2_SR_SCALE = 0.0001  # DN -> reflectance; S2 SR has no additive offset (unlike Landsat C2 L2)

_UNIMPLEMENTED_SENSORS = {"S1", "MO", "AL", "NI", "DW"}


def resolve_study_area(study_area: StudyAreaConfig) -> ee.Geometry:
    """Turns StudyAreaConfig's asset-or-coordinates pair into an ee.Geometry."""
    if study_area.aoi_coordinates is not None:
        return ee.Geometry.Polygon([study_area.aoi_coordinates])
    return ee.FeatureCollection(study_area.aoi_asset).geometry()


def _mask_landsat_clouds(image: ee.Image) -> ee.Image:
    """Masks cloud/cloud-shadow/dilated-cloud pixels via QA_PIXEL.

    Bits 1 (dilated cloud), 3 (cloud), 4 (cloud shadow) - the standard
    Collection 2 Level 2 QA_PIXEL cloud mask.
    """
    qa = image.select("QA_PIXEL")
    mask = ee.Image(1)
    for bit in (1, 3, 4):
        mask = mask.And(qa.bitwiseAnd(1 << bit).eq(0))
    return image.updateMask(mask)


def _scale_landsat_sr(image: ee.Image) -> ee.Image:
    """Applies the Collection 2 Level 2 DN -> surface reflectance scale/offset."""
    optical_bands = image.select("SR_B.").multiply(_LANDSAT_SR_SCALE).add(_LANDSAT_SR_OFFSET)
    return image.addBands(optical_bands, None, True)


def _reduce_band(image: ee.Image, band: str, band_map: dict[str, str]) -> ee.Image:
    """Computes the configured single-band reduction from an image already
    carrying red/nir/swir1/swir2 (via band_map)."""
    red = image.select(band_map["red"])
    nir = image.select(band_map["nir"])
    swir1 = image.select(band_map["swir1"])
    swir2 = image.select(band_map["swir2"])

    if band == "nbr":
        return nir.subtract(swir2).divide(nir.add(swir2)).rename(band)
    if band == "ndvi":
        return nir.subtract(red).divide(nir.add(red)).rename(band)
    if band == "swir":
        # Assumption pending confirmation from organizeBULCD_Inputs source:
        # "SWIR" reduction is read as the raw SWIR1 band, not a normalized
        # index (unlike NBR/NDVI, which combine two bands).
        return swir1.rename(band)
    raise ValueError(f"Unknown reduction band: {band}")


def _date_bounds(sensor_code: str, cfg: SensorEvidenceConfig) -> tuple[str, str]:
    """Resolves a sensor's (possibly open-ended) year range to concrete ISO dates."""
    first_year = cfg.first_year or _SENSOR_LAUNCH_YEAR[sensor_code]
    last_year = cfg.last_year or (datetime.date.today().year + 1)
    return f"{first_year}-01-01", f"{last_year}-01-01"


def _landsat_evidence(
    sensor_code: str, cfg: SensorEvidenceConfig, study_area: ee.Geometry, band: str
) -> ee.ImageCollection:
    start, end = _date_bounds(sensor_code, cfg)
    band_map = _LANDSAT_BAND_MAP[sensor_code]

    collection = (
        ee.ImageCollection(_LANDSAT_COLLECTION_ID[sensor_code])
        .filterBounds(study_area)
        .filterDate(start, end)
        .filter(ee.Filter.calendarRange(cfg.first_doy, cfg.last_doy, "day_of_year"))
        .filter(ee.Filter.lt("CLOUD_COVER", cfg.cloud_cover_threshold))
    )

    def _process(image: ee.Image) -> ee.Image:
        image = _mask_landsat_clouds(image)
        image = _scale_landsat_sr(image)
        reduced = _reduce_band(image, band, band_map)
        return reduced.copyProperties(image, image.propertyNames())

    return collection.map(_process)


def _s2_with_cloud_probability(
    study_area: ee.Geometry, start: str, end: str, cloud_cover_threshold: float
) -> ee.ImageCollection:
    """Joins S2 SR imagery to its per-pixel cloud-probability companion
    collection by `system:index` - the standard s2cloudless join pattern."""
    sr_collection = (
        ee.ImageCollection(_S2_SR_COLLECTION_ID)
        .filterBounds(study_area)
        .filterDate(start, end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_cover_threshold))
    )
    cloud_prob_collection = (
        ee.ImageCollection(_S2_CLOUD_PROB_COLLECTION_ID).filterBounds(study_area).filterDate(start, end)
    )
    joined = ee.Join.saveFirst("s2cloudless").apply(
        primary=sr_collection,
        secondary=cloud_prob_collection,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    return ee.ImageCollection(joined)


def _mask_s2_clouds(image: ee.Image, cloud_mask_cfg: S2CloudMaskConfig) -> ee.Image:
    """Cloud + cloud-shadow mask via s2cloudless probability + a NIR
    dark-pixel shadow projection - the standard community s2cloudless
    recipe (see S2CloudMaskConfig's docstring for the tutorial), not a
    novel reconstruction. Requires `image` to carry the joined
    's2cloudless' property from `_s2_with_cloud_probability`."""
    cloud_prob = ee.Image(image.get("s2cloudless")).select("probability")
    is_cloud = cloud_prob.gt(cloud_mask_cfg.cld_prb_thresh).rename("clouds")

    not_water = image.select("SCL").neq(6)
    sr_band_scale = 1e4  # unscaled DN range of S2 SR bands, before _scale_s2_sr runs
    dark_pixels = (
        image.select("B8")
        .lt(cloud_mask_cfg.nir_drk_thresh * sr_band_scale)
        .multiply(not_water)
        .rename("dark_pixels")
    )
    shadow_azimuth = ee.Number(90).subtract(ee.Number(image.get("MEAN_SOLAR_AZIMUTH_ANGLE")))
    cloud_projection = (
        is_cloud.directionalDistanceTransform(shadow_azimuth, cloud_mask_cfg.cld_prj_dist * 10)
        .reproject(crs=image.select(0).projection(), scale=100)
        .select("distance")
        .mask()
        .rename("cloud_transform")
    )
    shadows = cloud_projection.multiply(dark_pixels).rename("shadows")

    is_cloud_or_shadow = is_cloud.add(shadows).gt(0)
    cloud_shadow_mask = (
        is_cloud_or_shadow.focalMin(2)
        .focalMax(cloud_mask_cfg.buffer * 2 / 20)
        .reproject(crs=image.select(0).projection(), scale=20)
        .rename("cloudmask")
    )
    return image.updateMask(cloud_shadow_mask.Not())


def _scale_s2_sr(image: ee.Image) -> ee.Image:
    """Applies the S2 SR DN -> reflectance scale (no additive offset, unlike Landsat)."""
    optical_bands = image.select("B.*").multiply(_S2_SR_SCALE)
    return image.addBands(optical_bands, None, True)


def _s2_evidence(cfg: SensorEvidenceConfig, study_area: ee.Geometry, band: str) -> ee.ImageCollection:
    start, end = _date_bounds("S2", cfg)
    cloud_mask_cfg = cfg.s2_cloud_mask or S2CloudMaskConfig()

    collection = _s2_with_cloud_probability(study_area, start, end, cfg.cloud_cover_threshold).filter(
        ee.Filter.calendarRange(cfg.first_doy, cfg.last_doy, "day_of_year")
    )

    def _process(image: ee.Image) -> ee.Image:
        image = _mask_s2_clouds(image, cloud_mask_cfg)
        image = _scale_s2_sr(image)
        reduced = _reduce_band(image, band, _S2_BAND_MAP)
        return reduced.copyProperties(image, image.propertyNames())

    return collection.map(_process)


def _evidence_date_and_doy_bounds(
    evidence: EvidenceConfig,
) -> tuple[int, int, int, int]:
    """Union (not intersection) of every enabled sensor's resolved year
    range and DOY window.

    CONFIRMED 2026-08-10 against the real afn_gatherCollectionsAndReduce
    source (515-gatherCollections27b): production computes ONE combined
    groupStartDOY/groupEndDOY (min firstDOY / max lastDOY across all
    enabled sensors) and ONE combined year list, then bins the ENTIRE
    multi-sensor stream against that single shared window - not a
    per-sensor window. For configs where every enabled sensor already
    shares the same DOY/year range (e.g. this project's cell 8C config)
    the union is a no-op; this matters once sensors have genuinely
    different windows.
    """
    first_years: list[int] = []
    last_years: list[int] = []
    first_doys: list[int] = []
    last_doys: list[int] = []
    for sensor_code, sensor_cfg in evidence.sensors.items():
        if not sensor_cfg.enabled:
            continue
        start, end = _date_bounds(sensor_code, sensor_cfg)
        first_years.append(int(start[:4]))
        last_years.append(int(end[:4]) - 1)  # end is exclusive (see _date_bounds)
        first_doys.append(sensor_cfg.first_doy)
        last_doys.append(sensor_cfg.last_doy)
    return min(first_years), max(last_years), min(first_doys), max(last_doys)


def _bin_evidence_by_day_step(
    collection: ee.ImageCollection,
    band: str,
    day_step_size: int,
    first_year: int,
    last_year: int,
    first_doy: int,
    last_doy: int,
) -> ee.ImageCollection:
    """Aggregates a raw per-image evidence stream into day_step_size-day
    temporal bins, collapsing every image inside a bin into ONE median
    image per bin.

    CONFIRMED 2026-08-10 against the real afn_gatherCollectionsAndReduce
    source (515-gatherCollections27b) - this was a genuine gap, not a
    tuning knob: `dayStepSize` was previously parsed into config and never
    used anywhere. Production divides the DOY/year range into
    dayStepSize-day bins, gathers every image from every enabled sensor
    that falls in a bin, and takes the median across the WHOLE bin,
    producing exactly one "Event" per bin regardless of how many raw
    images (0, 1, or several, across any sensor) landed in it - not one
    Event per raw image, which is what this rebuild did before this fix.
    Bin timestamp = the bin's END (matches production's
    `.set('system:time_start', end.millis())`).

    Empty bins: production seeds every bin's gather list with a
    structurally-valid-but-effectively-nodata "dummy" image so `.median()`
    never collapses to a zero-band result - reproduced here by unioning in
    a fully self-masked placeholder image of the right band name before
    reducing, so `.median()` always returns a correctly-shaped image (real
    data where any exists, masked where none does) instead of erroring on
    an empty ImageCollection.

    Implementation note: an earlier version of this function used
    `.map()` over the bin list with an independent `.filterDate()` inside
    - each of ~140 bins re-scanning the full evidence collection - which
    built a computation graph large enough to hit "User memory limit
    exceeded" even for a single-point query. `ee.Join.saveAll()` is the
    standard, efficient EE idiom for "group elements of one collection by
    date-range membership in another" and avoids that blowup entirely.
    """
    day_step_millis = day_step_size * 24 * 60 * 60 * 1000
    placeholder = ee.Image.constant(0).rename(band).selfMask()

    def _bin_starts_for_year(year: ee.Number) -> ee.List:
        start_millis = ee.Date.fromYMD(year, 1, 1).advance(ee.Number(first_doy).subtract(1), "day").millis()
        end_millis = ee.Date.fromYMD(year, 1, 1).advance(ee.Number(last_doy).subtract(1), "day").millis()
        return ee.List.sequence(start_millis, end_millis, day_step_millis)

    def _bin_feature(bin_start_millis: ee.Number) -> ee.Feature:
        start = ee.Date(bin_start_millis)
        end = start.advance(day_step_size, "day")
        return ee.Feature(None, {"start": start.millis(), "end": end.millis()})

    years = ee.List.sequence(first_year, last_year)
    bin_starts = ee.List(years.map(_bin_starts_for_year)).flatten()
    bins = ee.FeatureCollection(bin_starts.map(_bin_feature))

    # bin.start <= image.system:time_start < bin.end
    time_filter = ee.Filter.And(
        ee.Filter.lessThanOrEquals(leftField="start", rightField="system:time_start"),
        ee.Filter.greaterThan(leftField="end", rightField="system:time_start"),
    )
    joined = ee.Join.saveAll(matchesKey="images").apply(bins, collection, time_filter)

    def _bin_image(bin_feature: ee.Feature) -> ee.Image:
        bin_feature = ee.Feature(bin_feature)
        images = ee.ImageCollection(ee.List(bin_feature.get("images"))).merge(
            ee.ImageCollection([placeholder])
        )
        return images.median().set("system:time_start", bin_feature.getNumber("end"))

    return ee.ImageCollection(joined.map(_bin_image))


def assemble_evidence_collection(config: BULCDConfig) -> ee.ImageCollection:
    """Builds the continuous, multi-sensor, single-band evidence stream.

    Real, working implementation for Landsat 5/7/8/9 and Sentinel-2. Raises
    NotImplementedError for any other enabled sensor (see module docstring).
    Each raw satellite image is first cloud-masked and reduced to one band
    per sensor, then binned into `evidence.day_step_size`-day windows and
    median-combined within each window (see `_bin_evidence_by_day_step()`)
    - the actual "Event" granularity production uses, confirmed 2026-08-10.
    """
    study_area = resolve_study_area(config.study_area)
    band = config.reduction.band
    collections = []

    for sensor_code, sensor_cfg in config.evidence.sensors.items():
        if not sensor_cfg.enabled:
            continue
        if sensor_code in _LANDSAT_COLLECTION_ID:
            collections.append(_landsat_evidence(sensor_code, sensor_cfg, study_area, band))
        elif sensor_code == "S2":
            collections.append(_s2_evidence(sensor_cfg, study_area, band))
        elif sensor_code in _UNIMPLEMENTED_SENSORS:
            raise NotImplementedError(
                f"Evidence assembly for sensor '{sensor_code}' is not implemented yet "
                "(see bulcd/inputs.py module docstring and CLAUDE.md 'Legacy source "
                "repos and what's still missing')."
            )
        else:
            raise ValueError(f"Unrecognized sensor code: {sensor_code}")

    if not collections:
        raise ValueError("No enabled sensors produced an evidence collection.")

    merged = collections[0]
    for other in collections[1:]:
        merged = merged.merge(other)

    # Explicit toFloat() cast before merge-driven use elsewhere: merging
    # heterogeneous per-sensor collections without this can raise a
    # "homogeneous image collection" type mismatch (same gotcha noted in
    # the sibling GeoTimeSeries project's CLAUDE.md for harmonized_collection()).
    merged = merged.map(lambda img: img.toFloat()).sort("system:time_start")

    first_year, last_year, first_doy, last_doy = _evidence_date_and_doy_bounds(config.evidence)
    return _bin_evidence_by_day_step(
        merged, band, config.evidence.day_step_size, first_year, last_year, first_doy, last_doy
    )


@dataclass
class ExpectationFit:
    """Per-pixel harmonic regression fit to the expectation-period baseline.

    `coefficients` is a multi-band image, one band per entry in
    `regressor_names`, in the same order (see `_select_modality_regressors`).
    """

    coefficients: ee.Image
    regressor_names: list[str]
    r2: ee.Image
    residual_stddev: ee.Image


@dataclass
class OrganizedInputs:
    """Return type of organize_inputs() - the legacy `bulcD_input` object,
    generalized from a single expectation/target-period comparison to a
    continuous evidence stream (see module docstring)."""

    evidence_collection: ee.ImageCollection
    expectation_r2: ee.Image
    expectation_residual_stddev: ee.Image
    # One 'fitted' band added per timestep across the FULL evidence
    # collection (not just the baseline window) - legacy's expectCollectionFit,
    # generalized so the same fitted curve can be inspected/plotted at any
    # point in the continuous stream, not just within the expectation period.
    expectation_fitted_collection: ee.ImageCollection
    # One z-score image per evidence timestep (legacy targetLOFAsZScore,
    # generalized from a single target-period image to a continuous stream -
    # the modernization's central algorithmic change).
    lof_zscore: ee.ImageCollection


def _select_modality_regressors(modality: ModalityConfig) -> list[str]:
    """Resolves ModalityConfig's (possibly multiple) true flags to one
    concrete list of harmonic regressor band names (see _add_harmonic_terms).

    ASSUMPTION pending real organizeBULCD_Inputs source confirmation: the
    one real legacy example (BULCD-InputParameters-v5) sets both `constant`
    and `unimodal` true simultaneously, and ModalityConfig's own docstring
    already flags this as unresolved. Here: richest enabled shape wins,
    in order trimodal > bimodal > unimodal > linear > constant.
    """
    if modality.trimodal:
        # bimodal/trimodal's own first-order term is still "sin" only, no
        # "cos" - unlike unimodal below, that's NOT yet confirmed against
        # a real production run (only unimodal's regressor list has been
        # observed live, see CLAUDE.md "Legacy-GUI parameter matching").
        # Plausibly the same gap, left alone until actually confirmed.
        return ["constant", "sin", "cos2", "sin2", "cos3", "sin3"]
    if modality.bimodal:
        return ["constant", "sin", "cos2", "sin2"]
    if modality.unimodal:
        # CONFIRMED 2026-08-10 against a real GUI run's Console output
        # (cell 8C - see CLAUDE.md "Legacy-GUI parameter matching"):
        # production's own printed `harrrmonic names (Optical)` was
        # ["constant","cos","sin"] - the full first-order harmonic, NOT
        # Willis (2022) eq. 6's simplified constant+sin-only fit this
        # used to implement. Live evidence overrides the thesis here.
        return ["constant", "cos", "sin"]
    if modality.linear:
        return ["constant", "t"]
    # Fallback regardless of modality.constant's own value - a regression
    # needs at least an intercept term, so "no seasonal shape selected"
    # and "constant explicitly selected" resolve to the same regressor set.
    return ["constant"]


def _add_harmonic_terms(image: ee.Image) -> ee.Image:
    """Adds constant/time/harmonic regressor bands to a single evidence image.

    Uses continuous fractional years since an arbitrary epoch (not
    day-of-year mod 365, which Willis (2022) eq. 4/5/6 use) as the time
    axis `t`, so `sin(2*pi*t)` still completes exactly one cycle per year
    but stays continuous across an expectation window spanning multiple
    years - a generalization of the thesis's single-year formulation,
    needed here because our expectation window is a configurable
    multi-year range rather than the legacy's fixed one-year period. This
    is the standard Earth Engine harmonic-regression idiom (Google's own
    time-series-modeling tutorial), not a novel formula.
    """
    epoch = ee.Date("1970-01-01")
    years_since_epoch = image.date().difference(epoch, "year")
    two_pi_t = ee.Image.constant(years_since_epoch).multiply(2 * math.pi).toFloat()
    return (
        image.addBands(ee.Image.constant(1).rename("constant").toFloat())
        .addBands(ee.Image.constant(years_since_epoch).rename("t").toFloat())
        .addBands(two_pi_t.cos().rename("cos"))
        .addBands(two_pi_t.sin().rename("sin"))
        .addBands(two_pi_t.multiply(2).cos().rename("cos2"))
        .addBands(two_pi_t.multiply(2).sin().rename("sin2"))
        .addBands(two_pi_t.multiply(3).cos().rename("cos3"))
        .addBands(two_pi_t.multiply(3).sin().rename("sin3"))
    )


def _add_fitted_band(
    image: ee.Image, coefficients: ee.Image, regressor_names: list[str]
) -> ee.Image:
    """Adds a 'fitted' band = sum(coefficient_i * regressor_i) to an image
    that already carries the harmonic regressor bands (_add_harmonic_terms).
    Works at ANY timestep, not just within the expectation window - this is
    what lets the same fit score the full continuous evidence stream."""
    fitted = (
        image.select(regressor_names)
        .multiply(coefficients)
        .reduce(ee.Reducer.sum())
        .rename("fitted")
    )
    return image.addBands(fitted)


def _fit_expectation_model(
    expectation_collection: ee.ImageCollection, modality: ModalityConfig, band: str
) -> ExpectationFit:
    """Fits the per-pixel harmonic expectation model (Willis 2022 eq. 4/6)
    against the baseline window only, and computes R2/residual stddev
    against that same baseline - the standard GEE harmonic-regression
    reduce-then-arrayFlatten idiom."""
    regressor_names = _select_modality_regressors(modality)
    harmonic_expectation = expectation_collection.map(_add_harmonic_terms)

    regression_input = harmonic_expectation.select(regressor_names + [band])
    regression = regression_input.reduce(
        ee.Reducer.linearRegression(numX=len(regressor_names), numY=1)
    )
    coefficients = (
        regression.select("coefficients").arrayProject([0]).arrayFlatten([regressor_names])
    )

    fitted_expectation = harmonic_expectation.map(
        lambda img: _add_fitted_band(img, coefficients, regressor_names)
    )

    # CONFIRMED 2026-08-10 against the real organizeBULCD_Inputs source
    # (afn_summarizeICSimply's "StdDev" branch: plain
    # residuals.reduce(ee.Reducer.sampleStdDev()) over observed-minus-fitted
    # residuals) - production uses a straight sample standard deviation
    # (n-1 denominator), NOT a regression residual-standard-error
    # (n - num_regressors) like this used to compute. OLS residuals sum to
    # ~0 when the design includes a constant term (always true here), so
    # the two formulas differ only in that denominator.
    residuals = fitted_expectation.map(
        lambda img: img.select(band).subtract(img.select("fitted")).rename("residual")
    )
    residual_stddev = (
        residuals.select("residual").reduce(ee.Reducer.sampleStdDev()).rename("residual_stddev")
    )

    def _squared_residual(image: ee.Image) -> ee.Image:
        return (
            image.select(band)
            .subtract(image.select("fitted"))
            .pow(2)
            .rename("squared_residual")
        )

    ss_res = fitted_expectation.map(_squared_residual).reduce(ee.Reducer.sum()).rename("ss_res")

    observed_mean = expectation_collection.select(band).reduce(ee.Reducer.mean())
    ss_tot = (
        expectation_collection.select(band)
        .map(lambda img: img.subtract(observed_mean).pow(2).rename("squared_deviation"))
        .reduce(ee.Reducer.sum())
        .rename("ss_tot")
    )
    r2 = ee.Image(1).subtract(ss_res.divide(ss_tot)).rename("r2")

    return ExpectationFit(
        coefficients=coefficients,
        regressor_names=regressor_names,
        r2=r2,
        residual_stddev=residual_stddev,
    )


def _zscore_image(
    observed: ee.Image, fitted: ee.Image, residual_stddev: ee.Image, sensitivity: SensitivityConfig
) -> ee.Image:
    """(observed - fitted) / max(residual_stddev, denominator_factor), clamped to [-10, 10].

    CONFIRMED 2026-08-10 against the real organizeBULCD_Inputs source
    (`targetLOFAsZScore = rescaledResiduals.divide(expectationPeriodSD.max(ZScoreDenominatorFactor)).max(-10).min(10)`):
    z_score_denominator_factor is a FLOOR/clamp on residual_stddev (never
    let the denominator drop below this, preventing blowup in
    near-constant pixels like water), NOT an additive epsilon like this
    used to implement - and the result is explicitly clamped to [-10, 10].
    The clamp has little practical effect given this project's bin_cuts
    (any |z| > 2 already collapses into the same outermost bin), but is
    included for fidelity to the confirmed formula.
    """
    numerator = observed.subtract(fitted).multiply(sensitivity.z_score_numerator_factor)
    denominator = residual_stddev.max(sensitivity.z_score_denominator_factor)
    return numerator.divide(denominator).clamp(-10, 10).rename("zscore")


def organize_inputs(config: BULCDConfig) -> OrganizedInputs:
    """The legacy `afn_organizeBULCD_Inputs` equivalent (see module docstring
    for what's implemented against a reconstruction vs. the real source)."""
    if config.evidence.expectation_first_year is None or config.evidence.expectation_last_year is None:
        raise ValueError(
            "organize_inputs() requires evidence.expectation_first_year and "
            "expectation_last_year to be set - the baseline window the "
            "expectation model is fit against. See CLAUDE.md 'Design decision: "
            "the expectation baseline window'."
        )

    band = config.reduction.band
    evidence_collection = assemble_evidence_collection(config)

    expectation_start = f"{config.evidence.expectation_first_year}-01-01"
    expectation_end = f"{config.evidence.expectation_last_year}-01-01"
    expectation_collection = evidence_collection.filterDate(expectation_start, expectation_end)

    fit = _fit_expectation_model(expectation_collection, config.modality, band)

    harmonic_full = evidence_collection.map(_add_harmonic_terms)
    expectation_fitted_collection = harmonic_full.map(
        lambda img: _add_fitted_band(img, fit.coefficients, fit.regressor_names)
    )

    def _add_zscore(image: ee.Image) -> ee.Image:
        z = _zscore_image(
            image.select(band), image.select("fitted"), fit.residual_stddev, config.sensitivity
        )
        return image.addBands(z)

    lof_zscore = expectation_fitted_collection.map(_add_zscore).select("zscore")

    return OrganizedInputs(
        evidence_collection=evidence_collection,
        expectation_r2=fit.r2,
        expectation_residual_stddev=fit.residual_stddev,
        expectation_fitted_collection=expectation_fitted_collection,
        lof_zscore=lof_zscore,
    )
