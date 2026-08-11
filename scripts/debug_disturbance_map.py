"""Generates a cheap preview (not a billed export) of a full-AOI
disturbance map: engine.run_bulcd()'s final_probabilities image, 3 bands
(decrease/unchanged/increase) visualized directly as an RGB composite -
the same convention the legacy caller script used
(`Map.addLayer(finalBulcProbs, {}, "Final BULC Probabilities RGB")`).

AOI: the 2003 B&B Complex Fire area (see scripts/debug_bb_complex_fire.py
and CLAUDE.md "Known-burn validation"), widened to ~13km to show the
fire's actual spatial extent rather than one pixel. First run of this
(2026-07-30) produced a coherent, irregular red (decrease/burn) region
matching a realistic fire-perimeter shape - the strongest visual
validation the pipeline has had - but also revealed scattered blue
("increase") specks at water bodies, since water's reflectance behaves
nothing like the forest-tuned harmonic model. That's what
`bulcd/engine.py`'s `_water_mask()` (StudyAreaConfig.mask_water, default
True) now fixes - see CLAUDE.md "Disturbance map".

Uses ee.Image.getThumbURL() - a synchronous preview render, NOT
Export.image.toAsset/toDrive. Fine for sanity-checking a few-km area;
NOT how a production-scale map should be generated (bulcd/export.py
doesn't exist yet - see CLAUDE.md "Current code state").

Usage:
    conda run -n bulcd python scripts/debug_disturbance_map.py
Prints a URL; fetching it requires an authenticated request (see the
google.auth.transport.requests pattern used to build this script).
"""

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

LON, LAT = -121.90249210117729, 44.53142096854933
_HALF_WIDTH_DEGREES = 0.06  # ~13km box - wide enough to show the fire's spatial extent
AOI = [
    [LON - _HALF_WIDTH_DEGREES, LAT - _HALF_WIDTH_DEGREES],
    [LON - _HALF_WIDTH_DEGREES, LAT + _HALF_WIDTH_DEGREES],
    [LON + _HALF_WIDTH_DEGREES, LAT + _HALF_WIDTH_DEGREES],
    [LON + _HALF_WIDTH_DEGREES, LAT - _HALF_WIDTH_DEGREES],
]

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
    # expectation = pre-fire baseline (L5), target = the first full
    # growing season after the fire (L5) - matches debug_bb_complex_fire.py.
    evidence=EvidenceConfig(
        expectation=EvidencePeriodConfig(
            sensors={
                "L5": SensorEvidenceConfig(
                    enabled=True,
                    first_year=2000,
                    last_year=2003,
                    first_doy=152,
                    last_doy=273,
                    cloud_cover_threshold=40,
                ),
            }
        ),
        target=EvidencePeriodConfig(
            sensors={
                "L5": SensorEvidenceConfig(
                    enabled=True,
                    first_year=2004,
                    last_year=2005,
                    first_doy=152,
                    last_doy=273,
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
print(url)
