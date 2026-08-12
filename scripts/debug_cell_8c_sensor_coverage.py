"""Diagnostic for the 2026-08-11 GUI-vs-rebuild diff investigation
(see docs/decisions/0010's "Revalidated 2026-08-11..." entry and
docs/findings.md's matching entry): checks whether cell 8C's large-scale,
roughly diagonal GUI-vs-rebuild difference (GUI scores higher `decrease`
on the west side, higher `increase` on the east) lines up with a
per-sensor coverage boundary - hypothesis (1) from that discussion
(L8/L9 use WRS-2 path/row tiling, S2 uses MGRS/UTM tiling; a scene/tile
edge cutting across a rotated AOI like this cell could look diagonal).

For each of L8/L9/S2, builds a target-period-only EvidencePeriodConfig
containing just that sensor (reusing the real, public
`assemble_evidence_collection()` - not a separate ad hoc query), then
counts valid (cloud-masked, non-placeholder) day_step_size-bin
observations per pixel over the target period. Renders:
  - three individual per-sensor count thumbnails (grayscale, same
    min/max so they're visually comparable)
  - one RGB composite (R=L8 count, G=L9 count, B=S2 count) to show
    which sensor dominates where in a single image

Usage:
    conda run -n bulcd python scripts/debug_cell_8c_sensor_coverage.py
Prints URLs; fetching them requires an authenticated request (see other
scripts/debug_*.py docstrings for the pattern).
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd.config.loader import load_config
from bulcd.config.schema import EvidencePeriodConfig
from bulcd.inputs import assemble_evidence_collection, resolve_study_area

CONFIG_PATH = "configs/cell_8c_comparison.yaml"
_COUNT_MAX = 15  # visual stretch ceiling - adjust if outputs look uniformly saturated/blank

config = load_config(CONFIG_PATH)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])
band = config.reduction.band

counts = {}
for sensor_code in ["L8", "L9", "S2"]:
    sensor_cfg = config.evidence.target.sensors.get(sensor_code)
    if sensor_cfg is None or not sensor_cfg.enabled:
        print(f"{sensor_code}: not enabled in target period, skipping")
        continue
    isolated_period = EvidencePeriodConfig(sensors={sensor_code: sensor_cfg})
    collection = assemble_evidence_collection(config, isolated_period)
    count_image = collection.select(band).count().rename(sensor_code)
    counts[sensor_code] = count_image

    url = count_image.getThumbURL(
        {"region": region, "dimensions": 512, "min": 0, "max": _COUNT_MAX, "palette": ["000000", "ffffff"]}
    )
    mean_count = count_image.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region, scale=90, maxPixels=1e9
    ).getInfo()
    print(f"{sensor_code}: mean valid-bin count over target period = {mean_count}")
    print(f"{sensor_code} coverage thumbnail: {url}")

if len(counts) == 3:
    composite = ee.Image.cat([counts["L8"], counts["L9"], counts["S2"]])
    composite_url = composite.getThumbURL(
        {"region": region, "dimensions": 512, "min": 0, "max": _COUNT_MAX}
    )
    print("RGB composite (R=L8, G=L9, B=S2 valid-bin counts):")
    print(composite_url)
