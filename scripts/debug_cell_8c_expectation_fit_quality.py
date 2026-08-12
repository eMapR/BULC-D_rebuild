"""Diagnostic for the 2026-08-11 GUI-vs-rebuild diff investigation (see
docs/decisions/0010's "Revalidated 2026-08-11..." entry and
docs/findings.md's matching entry): checks whether cell 8C's large-scale,
roughly diagonal GUI-vs-rebuild difference (GUI scores higher `decrease`
on the west side, higher `increase` on the east) lines up with (A) a
spatial gradient in the rebuild's OWN expectation-model fit quality or
z-score bias, or (B) terrain (elevation/aspect) - hypothesis (b)/(c)/(d)
territory, distinct from hypothesis (a) (per-sensor coverage boundary),
which scripts/debug_cell_8c_sensor_coverage.py already ruled out.

cell_8c_comparison.yaml's expectation period is a single year (2024,
DOY 74-288 only, not a full calendar year) with day_step_size=3 -
fitting a full 3-term harmonic (constant+cos+sin) against one partial,
un-replicated seasonal arc is inherently more sensitive to per-pixel
noise (e.g. elevation-linked snow/cloud contamination) than a
multi-year baseline would be, and that sensitivity could vary spatially
even though the config itself is spatially uniform.

organize_inputs() already computes and returns expectation_r2 and
expectation_residual_stddev as ee.Image - this script just calls it
(real, public, unchanged) and renders those bands, plus the target
period's mean z-score (tests for a systematic BIAS in the fit, not just
noisiness - more directly explains "more decrease west / more increase
east" than fit-quality alone would).

Also splits the AOI into a west half and an east half (by longitude
median of cell_8c_comparison.yaml's own aoi_coordinates) and prints
reduceRegion means for each - a numeric west-vs-east comparison to
back up the visual thumbnails.

Usage:
    conda run -n bulcd python scripts/debug_cell_8c_expectation_fit_quality.py
Prints URLs; fetching them requires an authenticated request (see other
scripts/debug_*.py docstrings for the pattern).
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd.config.loader import load_config
from bulcd.inputs import organize_inputs

CONFIG_PATH = "configs/cell_8c_comparison.yaml"

config = load_config(CONFIG_PATH)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])

# Split the cell's own AOI into a west half / east half by longitude
# median of its vertices - a simple proxy for the diagonal split seen in
# the GUI-vs-rebuild diff image (the cell itself is a tilted quadrilateral,
# not a rectangle, so this is an approximation, not an exact match to the
# diff's own diagonal).
lons = sorted(pt[0] for pt in config.study_area.aoi_coordinates)
mid_lon = lons[len(lons) // 2]
bounds_coords = region.bounds().getInfo()["coordinates"][0]
min_lon, min_lat = bounds_coords[0]
max_lon, max_lat = bounds_coords[2]
west_half = ee.Geometry.Rectangle([min_lon, min_lat, mid_lon, max_lat]).intersection(region, 1)
east_half = ee.Geometry.Rectangle([mid_lon, min_lat, max_lon, max_lat]).intersection(region, 1)

print(f"Loaded {CONFIG_PATH}")
print(f"AOI longitude median split at {mid_lon}")

organized = organize_inputs(config)

r2 = organized.expectation_r2
residual_stddev = organized.expectation_residual_stddev
mean_zscore = organized.lof_zscore.reduce(ee.Reducer.mean()).rename("mean_zscore")

for name, image, viz in [
    ("expectation_r2", r2, {"min": 0, "max": 1, "palette": ["000000", "ffffff"]}),
    (
        "expectation_residual_stddev",
        residual_stddev,
        {"min": 0, "max": 0.2, "palette": ["000000", "ffffff"]},
    ),
    (
        "mean_zscore",
        mean_zscore,
        {"min": -2, "max": 2, "palette": ["0000ff", "ffffff", "ff0000"]},
    ),
]:
    url = image.getThumbURL({"region": region, "dimensions": 512, **viz})
    print(f"{name} thumbnail: {url}")

    stats = {}
    for half_name, half_geom in [("west_half", west_half), ("east_half", east_half)]:
        result = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=half_geom, scale=30, maxPixels=1e9
        ).getInfo()
        stats[half_name] = result
    print(f"{name} west_half mean: {stats['west_half']}")
    print(f"{name} east_half mean: {stats['east_half']}")
    print()

# --- Diagnostic B: terrain correlation (hypothesis (c): snow/phenology
# contamination correlated with elevation) - same region/dimensions as
# the fit-quality thumbnails above so they're visually comparable.
dem = ee.Image("USGS/SRTMGL1_003")
elevation = dem.select("elevation")
aspect = ee.Terrain.aspect(dem)

for name, image, viz in [
    ("elevation", elevation, {"min": 800, "max": 2500, "palette": ["000000", "ffffff"]}),
    ("aspect", aspect, {"min": 0, "max": 360, "palette": ["000000", "ffffff"]}),
]:
    url = image.getThumbURL({"region": region, "dimensions": 512, **viz})
    print(f"{name} thumbnail: {url}")

    stats = {}
    for half_name, half_geom in [("west_half", west_half), ("east_half", east_half)]:
        result = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=half_geom, scale=30, maxPixels=1e9
        ).getInfo()
        stats[half_name] = result
    print(f"{name} west_half mean: {stats['west_half']}")
    print(f"{name} east_half mean: {stats['east_half']}")
    print()
