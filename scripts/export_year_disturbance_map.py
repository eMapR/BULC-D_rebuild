"""Exports a "disturbance in year Y" map for one study-area grid cell to
the user's own GEE assets - a REAL Export.image.toAsset() batch task
(bulcd/export.py, new 2026-07-30), not a getThumbURL() preview like every
other scripts/debug_*.py script so far.

Produces a 2-band image, one band per "was this pixel abnormal in year Y"
question identified in CLAUDE.md "Year of change" (see also
bulcd/interpret.py's module docstring):
  - "zscore_anomaly": FAST layer. Straight from organize_inputs()'s
    per-image z-score stream - no Bayesian accumulation, no lag, but no
    noise-robustness either (a single bad scene can trigger it).
  - "bulc_classification": ROBUST layer. The actual BULC-D sequential
    classification's answer - noise-robust by design, but potentially
    badly lagged for a year this recent. VALIDATED FINDING (known B&B
    Complex Fire test): at default recency_factor=1.0, this lagged a real
    disturbance by 12 YEARS. For a target year as recent as 2025, this
    band is very likely to come back mostly/entirely empty at the
    default - that's expected pipeline behavior given how little
    post-2025 evidence exists yet, not a bug in this script.

AOI: same grid-cell lookup as scripts/debug_grid_cell_map.py
(clipped_grid_35000m, filtered by grid_id). Evidence config's L8 sensor
window is extended to last_year=2026 (vs. other scripts' 2024) - the
_date_bounds() end-year is EXCLUSIVE, so 2026 is required to include all
of calendar year 2025.

Usage:
    conda run -n bulcd python scripts/export_year_disturbance_map.py \\
        CELL_ID YEAR ASSET_ID [RECENCY_FACTOR] [ZSCORE_THRESHOLD]
    e.g. conda run -n bulcd python scripts/export_year_disturbance_map.py \\
        2F 2025 projects/bulcd-python-rebuild/assets/disturbance_2025

Starts the export and returns immediately - does not wait for completion.
Check progress via `earthengine task info <id>` or the GEE Code Editor's
Tasks tab.
"""

import sys

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd import engine, export, interpret
from bulcd.config.schema import (
    BULCAdvancedParams,
    BULCDConfig,
    EvidenceConfig,
    ModalityConfig,
    ReductionConfig,
    SensitivityConfig,
    SensorEvidenceConfig,
    StudyAreaConfig,
)
from bulcd.inputs import organize_inputs

GRID_ASSET = "projects/eastern-cascades-bugnet/assets/clipped_grid_35000m"

CELL_ID = sys.argv[1] if len(sys.argv) > 1 else "2F"
TARGET_YEAR = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
ASSET_ID = (
    sys.argv[3] if len(sys.argv) > 3 else "projects/bulcd-python-rebuild/assets/disturbance_2025"
)
RECENCY_FACTOR = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
ZSCORE_THRESHOLD = float(sys.argv[5]) if len(sys.argv) > 5 else -2.0

grid = ee.FeatureCollection(GRID_ASSET)
cell = grid.filter(ee.Filter.eq("grid_id", CELL_ID)).first()
if cell is None:
    raise SystemExit(f"No cell with grid_id={CELL_ID!r} in {GRID_ASSET}")

cell_geom_info = cell.geometry().getInfo()
if cell_geom_info["type"] != "Polygon":
    raise SystemExit(
        f"Cell {CELL_ID!r} geometry is {cell_geom_info['type']!r}, not Polygon - "
        "script only handles a single-ring polygon AOI."
    )
AOI = cell_geom_info["coordinates"][0]

# Willis (2022)'s worked NBR12 transition matrix (see CLAUDE.md "Reference
# papers") - this study's example, not a verified production default.
NBR12_TRANSITION_MATRIX = [
    [0.16, 0.11, 0.02],
    [0.14, 0.07, 0.02],
    [0.07, 0.12, 0.02],
    [0.03, 0.16, 0.02],
    [0.015, 0.2, 0.01],
    [0.015, 0.195, 0.025],
    [0.02, 0.1255, 0.07],
    [0.02, 0.07, 0.11],
    [0.02, 0.05, 0.12],
    [0.02, 0.02, 0.08],
]

config = BULCDConfig(
    study_area=StudyAreaConfig(aoi_coordinates=AOI),  # mask_water defaults True
    evidence=EvidenceConfig(
        sensors={
            "L5": SensorEvidenceConfig(
                enabled=True,
                first_year=2000,
                last_year=2012,
                first_doy=152,  # June 1
                last_doy=243,  # Aug 31 - narrowed from 273 (Sept 30) per CLAUDE.md snow discussion
                cloud_cover_threshold=40,
            ),
            "L8": SensorEvidenceConfig(
                enabled=True,
                first_year=2014,
                last_year=2026,  # exclusive end - required to include all of 2025
                first_doy=152,  # June 1
                last_doy=243,  # Aug 31 - narrowed from 273 (Sept 30) per CLAUDE.md snow discussion
                cloud_cover_threshold=40,
            ),
        },
        expectation_first_year=2000,
        expectation_last_year=2003,
    ),
    reduction=ReductionConfig(band="nbr"),
    modality=ModalityConfig(constant=True, unimodal=True),
    sensitivity=SensitivityConfig(),
    bulc_advanced_params=BULCAdvancedParams(
        custom_transition_matrix=NBR12_TRANSITION_MATRIX, recency_factor=RECENCY_FACTOR
    ),
)

organized = organize_inputs(config)
result = engine.run_bulcd(config)

zscore_mask = interpret.zscore_anomaly_mask_for_year(
    organized.lof_zscore, TARGET_YEAR, threshold=ZSCORE_THRESHOLD
)
bulc_mask = interpret.disturbance_mask_for_year(
    result.classification_stack, TARGET_YEAR, target_class_index=0
).rename("bulc_classification")

combined = ee.Image.cat([zscore_mask, bulc_mask]).toInt8()

# classification_stack/lof_zscore both bypass run_bulcd()'s automatic
# water/non-forest masking (that only ever touches final_probabilities) -
# apply it explicitly here. Fixes both the mountain-top/above-treeline
# false-"change" artifact (mask_non_forest, new 2026-07-30) and the fact
# this export previously had no water masking either.
study_area_mask = engine.study_area_mask(config)
if study_area_mask is not None:
    combined = combined.updateMask(study_area_mask)

region = ee.Geometry.Polygon([AOI])
task = export.export_image_to_asset(
    combined,
    asset_id=ASSET_ID,
    region=region,
    description=f"bulcd_disturbance_{CELL_ID}_{TARGET_YEAR}",
    scale=config.study_area.scale,
    crs=config.study_area.crs,
)

print(f"Export started: task id = {task.id}")
print(f"Cell: {CELL_ID}, year: {TARGET_YEAR}, recency_factor: {RECENCY_FACTOR}")
print(f"Asset destination: {ASSET_ID}")
print("Bands: zscore_anomaly (fast/noisy), bulc_classification (robust/laggy)")
print("Monitor via `earthengine task info <id>` or the GEE Code Editor Tasks tab.")
