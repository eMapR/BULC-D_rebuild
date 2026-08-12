"""Diagnostic for the cell 8C GUI-vs-rebuild diff investigation (see
docs/decisions/0010's "Revalidated 2026-08-11..." entry and
docs/findings.md's matching entry): tests hypothesis (b) - a real
geographic/land-management gradient (e.g. the Mount Rainier NP boundary
near Longmire vs. more actively managed land to the west/south) that
both GUI and rebuild detect but weight differently, not a bug.

Two independent checks, both rendered over the identical cell 8C
region/dimensions as prior diagnostics so they're visually comparable
against the existing GUI-minus-rebuild diff image:

1. Protected-area boundary: WCMC/WDPA/current/polygons (World Database
   on Protected Areas, a standard EE public dataset), filtered to
   features intersecting the cell - not hardcoded to "Rainier" by name,
   so it also catches any other protected/managed-area boundary that
   happens to cross the cell. Rendered as a binary inside/outside mask.
2. Historical logging/harvest signature: UMD/hansen/global_forest_change_2023_v1_11's
   `lossyear` band (real, well-established annual forest-loss detection,
   2001-2023) - actively managed/harvested land typically shows a
   scattered, decades-spanning clearcut pattern; protected old-growth
   typically shows little to none. This is a proxy for "is this pixel's
   surrounding landscape under active timber management," independent
   of BULC-D's own recent target-period signal entirely.

Both are compared west-half vs. east-half (same longitude-median split
as scripts/debug_cell_8c_expectation_fit_quality.py, for consistency)
via reduceRegion means, plus thumbnails for visual inspection against
the diff's diagonal shape.

Usage:
    conda run -n bulcd python scripts/debug_cell_8c_land_management_gradient.py
Prints URLs; fetching them requires an authenticated request (see other
scripts/debug_*.py docstrings for the pattern).
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd.config.loader import load_config

CONFIG_PATH = "configs/cell_8c_comparison.yaml"

config = load_config(CONFIG_PATH)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])

lons = sorted(pt[0] for pt in config.study_area.aoi_coordinates)
mid_lon = lons[len(lons) // 2]
bounds_coords = region.bounds().getInfo()["coordinates"][0]
min_lon, min_lat = bounds_coords[0]
max_lon, max_lat = bounds_coords[2]
west_half = ee.Geometry.Rectangle([min_lon, min_lat, mid_lon, max_lat]).intersection(region, 1)
east_half = ee.Geometry.Rectangle([mid_lon, min_lat, max_lon, max_lat]).intersection(region, 1)

print(f"Loaded {CONFIG_PATH}")
print(f"AOI longitude median split at {mid_lon}")

# --- Check 1: protected-area boundary (WDPA) ---
wdpa = ee.FeatureCollection("WCMC/WDPA/current/polygons").filterBounds(region)
names = wdpa.aggregate_array("NAME").getInfo()
print(f"WDPA features intersecting cell 8C: {names}")

protected_mask = ee.Image(0).byte().paint(wdpa, 1).rename("protected").selfMask().unmask(0)
protected_url = protected_mask.getThumbURL(
    {"region": region, "dimensions": 512, "min": 0, "max": 1, "palette": ["000000", "00ff00"]}
)
print(f"protected-area mask thumbnail: {protected_url}")

for half_name, half_geom in [("west_half", west_half), ("east_half", east_half)]:
    frac = protected_mask.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=half_geom, scale=30, maxPixels=1e9
    ).getInfo()
    print(f"protected-area fraction, {half_name}: {frac}")
print()

# --- Check 2: historical forest-loss (logging/harvest) signature ---
hansen = ee.Image("UMD/hansen/global_forest_change_2023_v1_11")
lossyear = hansen.select("lossyear").selfMask()
loss_count = lossyear.gt(0).unmask(0).rename("loss_count")  # binary: any loss 2001-2023

loss_url = lossyear.getThumbURL(
    {"region": region, "dimensions": 512, "min": 1, "max": 23, "palette": ["ffff00", "ff0000", "800080"]}
)
print(f"Hansen lossyear thumbnail (any-loss pixels, yellow=early/2001, purple=recent/2023): {loss_url}")

for half_name, half_geom in [("west_half", west_half), ("east_half", east_half)]:
    frac = loss_count.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=half_geom, scale=30, maxPixels=1e9
    ).getInfo()
    print(f"any-forest-loss-2001-2023 fraction, {half_name}: {frac}")
print()
