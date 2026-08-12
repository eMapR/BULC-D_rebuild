"""Diagnostic for the cell 8C GUI-vs-rebuild diff investigation (see
docs/decisions/0010's "Revalidated 2026-08-11..." entry and
docs/findings.md's matching entry): tests a variant of hypothesis (d) -
not a per-sensor tiling boundary (already ruled out,
scripts/debug_cell_8c_sensor_coverage.py checked each sensor in
isolation) but whether the COMBINED, cross-sensor target-period Event
density (how many of the ~72 day_step_size=3 bins actually got a real
observation from ANY enabled sensor, after cloud masking) is lower on
the west side than the east.

This matters because of initializing_leveler=0.7 (configs/cell_8c_comparison.yaml):
the starting prior is [0.1, 0.8, 0.1] (decrease/unchanged/increase), NOT
flat uniform - biased toward "unchanged" before any evidence is folded
in. A pixel with fewer real target-period Events has fewer chances for
posterior_leveler-dampened Bayes updates to pull it away from that
"unchanged"-biased prior, REGARDLESS of how extreme its individual
z-scores are when they do occur - a pure evidence-density explanation,
distinct from the elevation-correlated z-score BIAS already found to
explain the east side.

Reuses assemble_evidence_collection() directly (real, unchanged) on the
same config.evidence.target period, so this counts exactly the Event
stream organize_inputs()/run_bulcd() actually fold through the Bayesian
engine - not a proxy.

Usage:
    conda run -n bulcd python scripts/debug_cell_8c_target_event_density.py
Prints URLs; fetching them requires an authenticated request (see other
scripts/debug_*.py docstrings for the pattern).
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd.config.loader import load_config
from bulcd.inputs import assemble_evidence_collection

CONFIG_PATH = "configs/cell_8c_comparison.yaml"

config = load_config(CONFIG_PATH)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])
band = config.reduction.band

lons = sorted(pt[0] for pt in config.study_area.aoi_coordinates)
mid_lon = lons[len(lons) // 2]
bounds_coords = region.bounds().getInfo()["coordinates"][0]
min_lon, min_lat = bounds_coords[0]
max_lon, max_lat = bounds_coords[2]
west_half = ee.Geometry.Rectangle([min_lon, min_lat, mid_lon, max_lat]).intersection(region, 1)
east_half = ee.Geometry.Rectangle([mid_lon, min_lat, max_lon, max_lat]).intersection(region, 1)

print(f"Loaded {CONFIG_PATH}")
print(f"AOI longitude median split at {mid_lon}")

target_collection = assemble_evidence_collection(config, config.evidence.target)
valid_count = target_collection.select(band).count().rename("valid_events")

total_bins = target_collection.size().getInfo()
print(f"Total day_step_size bins in target period: {total_bins}")

url = valid_count.getThumbURL(
    {"region": region, "dimensions": 512, "min": 0, "max": total_bins, "palette": ["000000", "ffffff"]}
)
print(f"valid target-period event count thumbnail: {url}")

for half_name, half_geom in [("west_half", west_half), ("east_half", east_half)]:
    result = valid_count.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=half_geom, scale=30, maxPixels=1e9
    ).getInfo()
    print(f"valid_events mean, {half_name}: {result}")
