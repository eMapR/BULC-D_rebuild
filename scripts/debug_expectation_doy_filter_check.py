"""Checks whether the 2026-08-12 DOY-boundary evidence fix (removing a
per-image `ee.Filter.calendarRange(first_doy, last_doy, "day_of_year")`
filter from `_landsat_evidence()`/`_s2_evidence()` - see
docs/findings.md's "2026-08-12: RESOLVED" entry) also affects the
EXPECTATION period, not just the target period it was originally found
and confirmed against.

The fix itself lives in the shared `_landsat_evidence()`/`_s2_evidence()`
functions that `assemble_evidence_collection()` calls for BOTH periods
(`organize_inputs()` calls it once for `config.evidence.expectation`,
once for `config.evidence.target`) - so the code fix already applies to
both by construction, there's no separate bug to find in the code. What
this checks is empirical: does cell 8C's real EXPECTATION year (2024,
DOY 74-288) actually have any image that lands in a DIFFERENT bin (or a
bin with a different image count) once the old per-image DOY filter is
reapplied on top of the current (fixed) evidence collection?

Method: reconstructs the OLD (pre-fix) per-sensor evidence collection by
reapplying the removed calendarRange filter on top of the current, real
`_landsat_evidence()`/`_s2_evidence()` output (equivalent to the removed
filter, since calendarRange only depends on system:time_start/date, not
pixel values - filtering post-hoc produces the same set of images as
filtering first). Then runs BOTH the fixed and reconstructed-old merged
collections through the exact same binning logic
`_bin_evidence_by_day_step()` uses internally (duplicated here only to
inspect the intermediate per-bin `images` join list size, which
`_bin_evidence_by_day_step()` itself doesn't expose) and compares,
bin-by-bin, how many raw images matched each bin.

An earlier version of this script only compared bin COUNT (fixed vs.
old-buggy) and treated equal counts as "no difference" - wrong, because
bin count is fixed by the date-range formula alone (every bin exists as
a placeholder even with zero matching images) and is insensitive to
exactly this kind of bug, where the bug changes a bin's CONTENT (which
raw images median together), not how many bins exist. The corrected
version below compares per-bin image counts directly, the same
granularity the original target-period bug was actually found at.

Usage:
    conda run -n bulcd python scripts/debug_expectation_doy_filter_check.py
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd.config.loader import load_config
from bulcd.inputs import (
    _LANDSAT_COLLECTION_ID,
    _evidence_date_and_doy_bounds,
    _landsat_evidence,
    _s2_evidence,
    resolve_study_area,
)

CONFIG_PATH = "configs/cell_8c_comparison.yaml"

config = load_config(CONFIG_PATH)
print(f"Loaded {CONFIG_PATH}")

period = config.evidence.expectation
study_area = resolve_study_area(config.study_area)
band = config.reduction.band


def _per_sensor_evidence(sensor_code, sensor_cfg):
    if sensor_code in _LANDSAT_COLLECTION_ID:
        return _landsat_evidence(sensor_code, sensor_cfg, study_area, band)
    if sensor_code == "S2":
        return _s2_evidence(sensor_cfg, study_area, band)
    raise NotImplementedError(sensor_code)


fixed_collections = []
old_buggy_collections = []
for sensor_code, sensor_cfg in period.sensors.items():
    if not sensor_cfg.enabled:
        continue
    evidence = _per_sensor_evidence(sensor_code, sensor_cfg)
    fixed_collections.append(evidence)
    # Reconstructs pre-fix behavior: the removed filter, reapplied.
    old_buggy_collections.append(
        evidence.filter(
            ee.Filter.calendarRange(sensor_cfg.first_doy, sensor_cfg.last_doy, "day_of_year")
        )
    )


def _merge(collections):
    merged = collections[0]
    for other in collections[1:]:
        merged = merged.merge(other)
    return merged.map(lambda img: img.toFloat()).sort("system:time_start")


fixed_merged = _merge(fixed_collections)
old_merged = _merge(old_buggy_collections)

first_year, last_year, first_doy, last_doy = _evidence_date_and_doy_bounds(period)
day_step_size = config.evidence.day_step_size
day_step_millis = day_step_size * 24 * 60 * 60 * 1000


def _bin_starts_for_year(year):
    start = ee.Date.fromYMD(year, 1, 1).advance(ee.Number(first_doy).subtract(1), "day").millis()
    end = ee.Date.fromYMD(year, 1, 1).advance(ee.Number(last_doy).subtract(1), "day").millis()
    return ee.List.sequence(start, end, day_step_millis)


years = ee.List.sequence(first_year, last_year)
bin_starts = ee.List(years.map(_bin_starts_for_year)).flatten()


def _bin_feature(bin_start_millis):
    start = ee.Date(bin_start_millis)
    end = start.advance(day_step_size, "day")
    return ee.Feature(None, {"start": start.millis(), "end": end.millis()})


bins = ee.FeatureCollection(bin_starts.map(_bin_feature))
time_filter = ee.Filter.And(
    ee.Filter.lessThanOrEquals(leftField="start", rightField="system:time_start"),
    ee.Filter.greaterThan(leftField="end", rightField="system:time_start"),
)


def _per_bin_image_counts(collection):
    joined = ee.Join.saveAll(matchesKey="images", outer=True).apply(bins, collection, time_filter)

    def _count(feature):
        feature = ee.Feature(feature)
        return feature.set("n", ee.List(feature.get("images")).size())

    return joined.map(_count).aggregate_array("n").getInfo()


fixed_counts = _per_bin_image_counts(fixed_merged)
old_counts = _per_bin_image_counts(old_merged)

print(f"Total bins: {len(fixed_counts)} (fixed) vs {len(old_counts)} (old-buggy)")

diffs = [
    (i, f, o) for i, (f, o) in enumerate(zip(fixed_counts, old_counts)) if f != o
]

if not diffs:
    print(
        "\nNo bin has a different raw-image count between the fixed and "
        "reconstructed-old-buggy evidence collections. The DOY-filter bug "
        "had ZERO effect on the expectation period for this config (cell "
        "8C, 2024, DOY 74-288, day_step_size=3) - no real image happened "
        "to fall in the narrow trailing-gap window that year. The fit "
        "(coefficients/r2/residual_stddev) is therefore byte-identical "
        "before and after the fix; no further comparison needed."
    )
else:
    print(f"\n{len(diffs)} bin(s) differ in raw-image count:")
    for i, f, o in diffs:
        print(f"  bin {i}: fixed={f} images, old-buggy={o} images")
    print(
        "\nThese bins' median composite - and therefore the harmonic "
        "expectation fit - differ between the two versions. Re-run with a "
        "fit comparison (see the target-period precedent in "
        "docs/findings.md) to quantify the impact."
    )
