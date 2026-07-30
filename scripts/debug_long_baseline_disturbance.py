"""Debug run demonstrating a major finding: a long, stable pre-disturbance
baseline can make a genuine later disturbance nearly undetectable at the
default dampening_factor. See CLAUDE.md "Major finding: long stable
baselines can mask real disturbance" for full context - this is not a
bug, it's a real structural property of sequential Bayesian updating
(Cardille & Fortin 2016 Eq. 2) that's directly in tension with this
project's "use the full Landsat archive as continuous evidence" goal.

Point (user-supplied, picked via LandTrendr for a high-magnitude
disturbance): -122.0582, 44.4823, central Oregon Cascades. Z-scores sit
near zero for 14 years (2000-2014), then crash to -6.9 in June 2015 and
stay between -5 and -10.9 for the following 9 years - about as
unambiguous a disturbance signal as this pipeline will ever see. Despite
that, at dampening_factor=0.5 the final classification is
unchanged=0.9999999999994. This script prints the full z-score time
series plus a dampening-factor sweep showing how much dampening it
actually takes for "decrease" to become competitive.

Usage:
    conda run -n bulcd python scripts/debug_long_baseline_disturbance.py
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

LON, LAT = -122.0582, 44.4823
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


def make_config(dampening_factor: float) -> BULCDConfig:
    return BULCDConfig(
        study_area=StudyAreaConfig(aoi_coordinates=SMALL_AOI),
        evidence=EvidenceConfig(
            sensors={
                "L5": SensorEvidenceConfig(
                    enabled=True,
                    first_year=2000,
                    last_year=2012,
                    first_doy=152,
                    last_doy=273,  # growing season only
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
            expectation_first_year=2000,
            expectation_last_year=2003,
        ),
        reduction=ReductionConfig(band="nbr"),
        modality=ModalityConfig(constant=True, unimodal=True),
        sensitivity=SensitivityConfig(),
        bulc_advanced_params=BULCAdvancedParams(
            custom_transition_matrix=NBR12_TRANSITION_MATRIX,
            dampening_factor=dampening_factor,
        ),
    )


config = make_config(dampening_factor=0.5)

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

print("=== dampening_factor sweep ===")
for d in [0.5, 0.2, 0.1, 0.05, 0.02]:
    result = engine.run_bulcd(make_config(dampening_factor=d))
    probs = result.final_probabilities.reduceRegion(
        reducer=ee.Reducer.first(), geometry=POINT, scale=30
    ).getInfo()
    print(f"d={d}: {probs}")
