"""Exports cell 8C's real BULC-D `final_probabilities` result to a GEE
asset - a real `ee.batch.Export.image.toAsset()` batch task
(`bulcd/export.py`), not a `getThumbURL()` preview like
`scripts/run_cell_8c_comparison.py`.

Loads `configs/cell_8c_comparison.yaml` (the real parameter-matched
config against the legacy GUI, now under the restored expectation/target
period split - see that file's own header comments and
`docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md`),
runs the full BULC-D pipeline, and exports the 3-band
(decrease/unchanged/increase) `final_probabilities` image to
`config.export.asset_folder` - so it can be compared directly against
the GUI's own rendered output in the Code Editor, not just a thumbnail
preview.

KNOWN, DELIBERATE APPROXIMATION (same caveat as
`scripts/run_cell_8c_comparison.py`): `bulc_advanced_params.dampening_factor`
in that config is still `bulc.py`'s single-scalar placeholder, not
production's real three-leveler mechanism.

Usage:
    conda run -n bulcd python scripts/export_cell_8c_comparison.py

Starts the export and returns immediately - does not wait for
completion. Check progress via `earthengine task info <id>` or the GEE
Code Editor's Tasks tab.
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd import engine, export
from bulcd.config.loader import load_config

CONFIG_PATH = "configs/cell_8c_comparison.yaml"
ASSET_ID = "projects/bulcd-python-rebuild/assets/bulcd_cell8c_comparison_final_probabilities"

config = load_config(CONFIG_PATH)
print(f"Loaded {CONFIG_PATH}")
print(
    "NOTE: dampening_factor is a known placeholder "
    f"({config.bulc_advanced_params.dampening_factor}) - not yet matched "
    "to production's real leveler mechanism. See CLAUDE.md."
)

result = engine.run_bulcd(config)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])

task = export.export_image_to_asset(
    result.final_probabilities.select(["decrease", "unchanged", "increase"]),
    asset_id=ASSET_ID,
    region=region,
    description=f"{config.export.description_prefix}_final_probabilities",
    scale=config.study_area.scale,
    crs=config.study_area.crs,
    max_pixels=config.export.max_pixels,
)

print(f"Export started: task id = {task.id}")
print(f"Asset destination: {ASSET_ID}")
print("Monitor via `earthengine task info <id>` or the GEE Code Editor Tasks tab.")
