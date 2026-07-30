"""Debug run against a real, known-burned pixel: the 2003 B&B Complex Fire
(central Oregon Cascades, ignited Aug 15, 2003) - the strongest end-to-end
validation the pipeline has had so far (see CLAUDE.md "Known-burn
validation"). Companion to scripts/debug_run.py, which only exercises an
"unchanged" (never-burned) pixel.

Because the fire predates Landsat 8 (2013+) entirely, this uses Landsat 5
for the pre-fire baseline - an L8-only evidence window can only see the
tail end of post-fire recovery, never the actual transition. This is the
first real exercise of "use the full Landsat archive," not just L8.

Usage:
    conda run -n bulcd python scripts/debug_bb_complex_fire.py
"""

import datetime

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd import engine
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

LON, LAT = -121.90249210117729, 44.53142096854933
_HALF_WIDTH_DEGREES = 0.01
SMALL_AOI = [
    [LON - _HALF_WIDTH_DEGREES, LAT - _HALF_WIDTH_DEGREES],
    [LON - _HALF_WIDTH_DEGREES, LAT + _HALF_WIDTH_DEGREES],
    [LON + _HALF_WIDTH_DEGREES, LAT + _HALF_WIDTH_DEGREES],
    [LON + _HALF_WIDTH_DEGREES, LAT - _HALF_WIDTH_DEGREES],
]
POINT = ee.Geometry.Point([LON, LAT])

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
    study_area=StudyAreaConfig(aoi_coordinates=SMALL_AOI),
    evidence=EvidenceConfig(
        sensors={
            "L5": SensorEvidenceConfig(
                enabled=True,
                first_year=2000,
                last_year=2012,
                first_doy=152,
                last_doy=273,  # growing season only - avoids winter snow contamination
                cloud_cover_threshold=40,
            ),
            "L8": SensorEvidenceConfig(
                enabled=True,
                first_year=2014,
                last_year=2024,
                first_doy=152,
                last_doy=273,
                cloud_cover_threshold=40,
            ),
        },
        # Pre-fire baseline only - expectation_last_year=2003 is an
        # EXCLUSIVE upper bound (see organize_inputs()), so this correctly
        # excludes the fire year itself, not just years strictly before it.
        expectation_first_year=2000,
        expectation_last_year=2003,
    ),
    reduction=ReductionConfig(band="nbr"),
    modality=ModalityConfig(constant=True, unimodal=True),
    sensitivity=SensitivityConfig(),
    bulc_advanced_params=BULCAdvancedParams(custom_transition_matrix=NBR12_TRANSITION_MATRIX),
)

print("=== organize_inputs ===")
organized = organize_inputs(config)
print("evidence count:", organized.evidence_collection.size().getInfo())
r2 = organized.expectation_r2.reduceRegion(ee.Reducer.first(), POINT, 30).getInfo()
print("expectation_r2 at point:", r2)

print("=== z-score time series at point ===")
region_data = organized.lof_zscore.getRegion(POINT, 30).getInfo()
header, rows = region_data[0], region_data[1:]
zscore_idx = header.index("zscore")
time_idx = header.index("time")
for row in rows:
    if row[zscore_idx] is None:
        continue
    ts = datetime.datetime.utcfromtimestamp(row[time_idx] / 1000).strftime("%Y-%m-%d")
    print(f"{ts}  zscore={row[zscore_idx]:.3f}")

print("=== engine.run_bulcd ===")
result = engine.run_bulcd(config)
final_probs = result.final_probabilities.reduceRegion(
    reducer=ee.Reducer.first(), geometry=POINT, scale=30
).getInfo()
print("final_probabilities at point:", final_probs)
