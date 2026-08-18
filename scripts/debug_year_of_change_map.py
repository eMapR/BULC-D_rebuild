"""Generates a cheap preview (not a billed export) of a "disturbance in
year Y" map for one cell of the study-area grid - the year-specific query
this project's users actually want ("if I'm looking for disturbance in
2025, tell the program that, get back a disturbance map"), as opposed to
scripts/debug_grid_cell_map.py's "current accumulated state" map.

Built on bulcd/interpret.py's disturbance_mask_for_year() (reworked
2026-08-18 for docs/decisions/0010's restored expectation/target split,
and in the process corrected against the real, fetched
afn_interpretBULCDResult source - see that module's docstring for the
full rationale). TARGET_YEAR below picks which year's target period to
build (i.e. which year's evidence feeds `probability_stack`); it's also
passed straight through to disturbance_mask_for_year()'s own `year`
argument, since the real source's "first threshold crossing" logic
answers "when," not just "whether."

CHANGE_THRESHOLD (new argument, no confirmed production default - see
interpret.py's module docstring on the still-missing
BULCD-AnalysisParameters-v5) is the raw "decrease" probability a
target-period Event must exceed to count as a crossing.

HISTORICAL NOTE: this script used to be built on the old
`year_of_change()`/`disturbance_mask_for_year()`, which searched a long,
CONTINUOUS multi-decade evidence stream (docs/decisions/0003, superseded)
for a PERSISTENT run's start year, reading `classification_stack`'s
argmax rather than the raw probability - at recency_factor=1.0 that
approach lagged a true disturbance by OVER A DECADE (2015 detected vs.
2003 actual, the B&B Complex Fire test). The real
afn_interpretBULCDResult source (fetched 2026-08-10, read closely
2026-08-18) confirmed production never asked that persistent-run question
at all - it thresholds the raw probability stack and takes the FIRST
crossing, no persistence required - which interpret.py's
first_change_year()/disturbance_mask_for_year() now do directly.

AOI source: same grid-cell lookup as debug_grid_cell_map.py
(`projects/eastern-cascades-bugnet/assets/clipped_grid_35000m`, filtered
by `grid_id`).

Usage:
    conda run -n bulcd python scripts/debug_year_of_change_map.py CELL_ID YEAR [RECENCY_FACTOR] [CHANGE_THRESHOLD]
    e.g. conda run -n bulcd python scripts/debug_year_of_change_map.py 2F 2015
         conda run -n bulcd python scripts/debug_year_of_change_map.py 2F 2007 0.98
    (CELL_ID defaults to "11A", YEAR defaults to 2020, RECENCY_FACTOR defaults
    to 1.0/off, CHANGE_THRESHOLD defaults to 0.5 - see module docstring caveat)
Prints a URL; fetching it requires an authenticated request (see
ee.data.get_persistent_credentials() + google.auth.transport.requests,
used to build/fetch this script's thumbnails so far).
"""

import sys

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd import engine, interpret
from bulcd.config.schema import (
    BULCAdvancedParams,
    BULCDConfig,
    EvidenceConfig,
    EvidencePeriodConfig,
    ModalityConfig,
    ReductionConfig,
    SensitivityConfig,
    SensorEvidenceConfig,
    StudyAreaConfig,
)

GRID_ASSET = "projects/eastern-cascades-bugnet/assets/clipped_grid_35000m"
CELL_ID = sys.argv[1] if len(sys.argv) > 1 else "11A"
TARGET_YEAR = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
RECENCY_FACTOR = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
CHANGE_THRESHOLD = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5

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

_TARGET_SENSOR = "L5" if TARGET_YEAR < 2014 else "L8"

config = BULCDConfig(
    study_area=StudyAreaConfig(aoi_coordinates=AOI),  # mask_water defaults True
    # Restored expectation/target period split (docs/decisions/0010):
    # expectation = the same 2000-2003 baseline as debug_grid_cell_map.py;
    # target = the single queried YEAR (see module docstring above).
    evidence=EvidenceConfig(
        expectation=EvidencePeriodConfig(
            sensors={
                "L5": SensorEvidenceConfig(
                    enabled=True,
                    first_year=2000,
                    last_year=2003,
                    first_doy=152,  # June 1
                    last_doy=243,  # Aug 31 - narrowed from 273 (Sept 30) per CLAUDE.md snow discussion
                    cloud_cover_threshold=40,
                ),
            }
        ),
        target=EvidencePeriodConfig(
            sensors={
                _TARGET_SENSOR: SensorEvidenceConfig(
                    enabled=True,
                    first_year=TARGET_YEAR,
                    last_year=TARGET_YEAR + 1,
                    first_doy=152,  # June 1
                    last_doy=243,  # Aug 31 - narrowed from 273 (Sept 30) per CLAUDE.md snow discussion
                    cloud_cover_threshold=40,
                ),
            }
        ),
    ),
    reduction=ReductionConfig(band="nbr"),
    modality=ModalityConfig(constant=True, unimodal=True),
    sensitivity=SensitivityConfig(),
    bulc_advanced_params=BULCAdvancedParams(
        custom_transition_matrix=NBR12_TRANSITION_MATRIX, recency_factor=RECENCY_FACTOR
    ),
)

result = engine.run_bulcd(config)
region = ee.Geometry.Polygon([AOI])

disturbance_mask = interpret.disturbance_mask_for_year(
    result.probability_stack,
    TARGET_YEAR,
    class_name="decrease",
    threshold=CHANGE_THRESHOLD,
    comparison="gt",
)

# dimensions=512 (debug_disturbance_map.py's value) hits "User memory
# limit exceeded" here - first_change_year() (called internally) still
# materializes a full per-pixel time-array, same as the function it
# replaced - 128 is confirmed to work at this AOI's ~13km scale; a real
# full-resolution/full-cell map needs an actual batch export
# (Export.image.toAsset/toDrive - see bulcd/export.py), not this
# synchronous preview path.
url = disturbance_mask.selfMask().getThumbURL(
    {"region": region, "dimensions": 128, "palette": ["red"], "min": 0, "max": 1}
)
print(
    f"Cell {CELL_ID}, disturbance in {TARGET_YEAR} "
    f"(recency_factor={RECENCY_FACTOR}, decrease-probability threshold={CHANGE_THRESHOLD}):"
)
print(url)
