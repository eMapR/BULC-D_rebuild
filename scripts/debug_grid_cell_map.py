"""Generates a cheap preview (not a billed export) of a BULC-D disturbance
map for one cell of the study-area grid, rather than a hand-picked box.

AOI source: `projects/eastern-cascades-bugnet/assets/clipped_grid_35000m`
(the GeoTimeSeries sibling project's route-corridor grid — see that
project's CLAUDE.md), filtered to a single cell by its `grid_id` property
(row+column-letter, e.g. "11A"). Cells are clipped to the corridor
buffer, so they're irregular polygons, not clean squares.

Config (sensors, DOY window, expectation baseline, Willis (2022) NBR12
transition matrix, dampening_factor default) is copied as-is from the
validated scripts/debug_disturbance_map.py run — see CLAUDE.md
"Disturbance map" / "Major finding" sections. The 2000-2003 baseline
window was originally chosen for the B&B Complex Fire test's known
pre-fire history; here it's reused as a general "earliest available
stable-looking window" default since arbitrary grid cells have no
known disturbance history to tune against. Revisit per-cell if a
specific cell's baseline turns out not to be disturbance-free.

Uses ee.Image.getThumbURL() - a synchronous preview render, NOT
Export.image.toAsset/toDrive - fine for sanity-checking, not how a
production-scale map should be generated (bulcd/export.py doesn't
exist yet).

Usage:
    conda run -n bulcd python scripts/debug_grid_cell_map.py [CELL_ID]
    (defaults to "11A" if no argument given)
Prints a URL; fetching it requires an authenticated request (see the
google.auth.transport.requests pattern used to build this script).
"""

import sys

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd import engine
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
    # Restored expectation/target period split (docs/decisions/0010):
    # expectation = the same "earliest available stable-looking window"
    # baseline as before (L5, 2000-2003); target = the most recent
    # available full growing season (L8, 2023-2024) - "is this cell
    # currently different from its historical baseline," a single
    # comparison rather than an indefinite continuous stream.
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
                "L8": SensorEvidenceConfig(
                    enabled=True,
                    first_year=2023,
                    last_year=2024,
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
    bulc_advanced_params=BULCAdvancedParams(custom_transition_matrix=NBR12_TRANSITION_MATRIX),
)

result = engine.run_bulcd(config)
region = ee.Geometry.Polygon([AOI])

url = result.final_probabilities.select(["decrease", "unchanged", "increase"]).getThumbURL(
    {"region": region, "dimensions": 512, "min": 0, "max": 1}
)
print(f"Cell {CELL_ID}:")
print(url)
