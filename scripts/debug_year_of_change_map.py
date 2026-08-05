"""Generates a cheap preview (not a billed export) of a "disturbance in
year Y" map for one cell of the study-area grid - the year-specific query
this project's users actually want ("if I'm looking for disturbance in
2025, tell the program that, get back a disturbance map"), as opposed to
scripts/debug_grid_cell_map.py's "current accumulated state" map.

Built on bulcd/interpret.py's year_of_change()/disturbance_mask_for_year()
(added 2026-07-30 - see CLAUDE.md "Year of change"), which read
classification_stack's per-Event dates (only present since bulc.py/
engine.py started threading system:time_start through - an older
classification_stack won't work here) to find, per pixel, the calendar
year its classification persistently flipped to "decrease."

IMPORTANT CAVEAT validated 2026-07-30 against the known 2003 B&B Complex
Fire point: at recency_factor=1.0 (the classic-method default, off), the
detected change year can lag the true disturbance by OVER A DECADE (2015
detected vs. 2003 actual) - the running Bayesian argmax classification
takes that long to flip even though the underlying z-score jumped
immediately. Lowering recency_factor pulls the detected year closer to
the truth (0.99->2009, 0.98->2007, 0.95->2006 at that same test point)
but didn't reach the true year even at 0.95. This script exposes
recency_factor as a parameter rather than hardcoding it - there's no
known value that eliminates the lag, only reduces it. See CLAUDE.md
"Year of change" for the full sweep and discussion before trusting a
specific year's map at face value.

AOI source: same grid-cell lookup as debug_grid_cell_map.py
(`projects/eastern-cascades-bugnet/assets/clipped_grid_35000m`, filtered
by `grid_id`).

Usage:
    conda run -n bulcd python scripts/debug_year_of_change_map.py CELL_ID YEAR [RECENCY_FACTOR]
    e.g. conda run -n bulcd python scripts/debug_year_of_change_map.py 2F 2015
         conda run -n bulcd python scripts/debug_year_of_change_map.py 2F 2007 0.98
    (CELL_ID defaults to "11A", YEAR defaults to 2020, RECENCY_FACTOR defaults to 1.0/off)
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
                last_year=2024,
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

result = engine.run_bulcd(config)
region = ee.Geometry.Polygon([AOI])

disturbance_mask = interpret.disturbance_mask_for_year(
    result.classification_stack, TARGET_YEAR, target_class_index=0
)

# dimensions=512 (debug_disturbance_map.py's value) hits "User memory
# limit exceeded" here - year_of_change() materializes a full per-pixel
# time-array (one value per Event, ~200+ for a multi-decade config),
# much heavier per-pixel than final_probabilities' simple 3-band image.
# 128 is confirmed to work at this AOI's ~13km scale; a real full-
# resolution/full-cell map needs an actual batch export
# (Export.image.toAsset/toDrive - bulcd/export.py doesn't exist yet),
# not this synchronous preview path.
url = disturbance_mask.selfMask().getThumbURL(
    {"region": region, "dimensions": 128, "palette": ["red"], "min": 0, "max": 1}
)
print(f"Cell {CELL_ID}, disturbance in {TARGET_YEAR} (recency_factor={RECENCY_FACTOR}):")
print(url)
