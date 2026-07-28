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

STUBBED, NOT IMPLEMENTED:
  - Sentinel-1/2, MODIS, ALOS, NICFI, Dynamic World collection assembly
    (`assemble_evidence_collection` raises NotImplementedError if one
    of these is enabled in config).
  - `organize_inputs()` — the legacy `afn_organizeBULCD_Inputs`
    equivalent: fitting the expectation-period regression (shape
    selected by config.modality), computing R2/residuals, and scoring
    the continuous evidence stream into z-scores (per
    config.sensitivity). This is the actual statistical core of
    BULC-D. Its real implementation lives in a GEE module
    (`6002.A2b.3-BULCD-Module-organizeBULCD_Inputs`, repo
    `alemlakes/r-2903-Dev`) we don't have source for. Reconstructing it
    from field names would risk silently deviating from "preserve the
    Bayesian updating core" (CLAUDE.md modernization goals) — so it's
    an explicit stub, not a guess.

Assumes `ee.Initialize(...)` has already been called by the caller —
this module never calls it itself, so it has no opinion about which
GEE Cloud project you're billed against.
"""

from __future__ import annotations

import datetime

import ee

from bulcd.config.schema import BULCDConfig, SensorEvidenceConfig, StudyAreaConfig

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
_LANDSAT_LAUNCH_YEAR = {"L5": 1984, "L7": 1999, "L8": 2013, "L9": 2021}

_UNIMPLEMENTED_SENSORS = {"S2", "S1", "MO", "AL", "NI", "DW"}


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
    first_year = cfg.first_year or _LANDSAT_LAUNCH_YEAR[sensor_code]
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


def assemble_evidence_collection(config: BULCDConfig) -> ee.ImageCollection:
    """Builds the continuous, multi-sensor, single-band evidence stream.

    Real, working implementation for Landsat 5/7/8/9. Raises
    NotImplementedError for any other enabled sensor (see module docstring).
    """
    study_area = resolve_study_area(config.study_area)
    band = config.reduction.band
    collections = []

    for sensor_code, sensor_cfg in config.evidence.sensors.items():
        if not sensor_cfg.enabled:
            continue
        if sensor_code in _LANDSAT_COLLECTION_ID:
            collections.append(_landsat_evidence(sensor_code, sensor_cfg, study_area, band))
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
    return merged.map(lambda img: img.toFloat()).sort("system:time_start")


def organize_inputs(config: BULCDConfig):
    """Placeholder for the legacy `afn_organizeBULCD_Inputs` equivalent.

    NOT IMPLEMENTED. Once we have the organizeBULCD_Inputs module source
    (see module docstring), this should return an object exposing
    (legacy field names in parens; some generalized from a single image
    to a continuous ImageCollection, which is the modernization's
    central algorithmic change):

      - evidence_collection: ee.ImageCollection
        (DONE - see assemble_evidence_collection() above)
      - expectation_r2, expectation_residuals: ee.Image
        (legacy theExpectationR2 / theExpectationResiduals)
      - expectation_summary_value, expectation_sd, expectation_mean: ee.Image
        (legacy expectationPeriodSummaryValue / SD / Mean)
      - lof_zscore: ee.ImageCollection, one z-score image per evidence
        timestep (legacy targetLOFAsZScore - generalized here from a
        single target-period image to a continuous stream)
    """
    raise NotImplementedError(
        "organize_inputs() requires the actual organizeBULCD_Inputs regression/"
        "z-score logic, which we don't have source for yet. "
        "assemble_evidence_collection() is implemented and usable on its own."
    )
