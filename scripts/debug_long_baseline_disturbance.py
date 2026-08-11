"""Debug run originally demonstrating a major finding: a long, stable
pre-disturbance baseline can make a genuine later disturbance nearly
undetectable at the default dampening_factor. See CLAUDE.md "Major
finding: long stable baselines can mask real disturbance" for full
context - a real structural property of sequential Bayesian updating
over an indefinite CONTINUOUS evidence stream (Cardille & Fortin 2016
Eq. 2), which was this project's design at the time (docs/decisions/0003).

STRUCTURALLY MOOT AS OF docs/decisions/0010 (2026-08-11): with the
expectation/target period split restored, a run only ever folds through
the target period's short Event sequence, not 14+ years of intervening
"confirm normal" evidence - the specific compounding failure mode this
script existed to demonstrate mostly can't occur anymore for a
reasonably short target window. Adapted below to instead directly test
"does a one-shot baseline-vs-target comparison spanning the known 2015
disturbance detect it" - a more direct question under the restored
design, and a genuinely different test than what this script used to run.
The dampening/recency_factor sweeps below are kept since they're still
meaningful knobs, just no longer motivated by the original long-stream
failure case.

Point (user-supplied, picked via LandTrendr for a high-magnitude
disturbance): -122.0582, 44.4823, central Oregon Cascades. Z-scores
crashed to -6.9 in June 2015 in the original continuous-stream run.

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
    EvidencePeriodConfig,
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


def make_config(dampening_factor: float, recency_factor: float = 1.0) -> BULCDConfig:
    return BULCDConfig(
        study_area=StudyAreaConfig(aoi_coordinates=SMALL_AOI),
        # Restored expectation/target period split (docs/decisions/0010):
        # expectation = pre-disturbance baseline (L5, 2000-2003); target =
        # the first full growing season spanning the known June 2015
        # disturbance onset (L8).
        evidence=EvidenceConfig(
            expectation=EvidencePeriodConfig(
                sensors={
                    "L5": SensorEvidenceConfig(
                        enabled=True,
                        first_year=2000,
                        last_year=2003,
                        first_doy=152,
                        last_doy=273,  # growing season only
                        cloud_cover_threshold=40,
                    ),
                }
            ),
            target=EvidencePeriodConfig(
                sensors={
                    "L8": SensorEvidenceConfig(
                        enabled=True,
                        first_year=2015,
                        last_year=2016,
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
        bulc_advanced_params=BULCAdvancedParams(
            custom_transition_matrix=NBR12_TRANSITION_MATRIX,
            dampening_factor=dampening_factor,
            recency_factor=recency_factor,
        ),
    )


config = make_config(dampening_factor=0.5)

print("=== organize_inputs ===")
organized = organize_inputs(config)
print("target evidence count:", organized.target_collection.size().getInfo())
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

print("=== dampening_factor sweep (recency_factor off) ===")
for d in [0.5, 0.2, 0.1, 0.05, 0.02]:
    result = engine.run_bulcd(make_config(dampening_factor=d))
    probs = result.final_probabilities.reduceRegion(
        reducer=ee.Reducer.first(), geometry=POINT, scale=30
    ).getInfo()
    print(f"d={d}: {probs}")

print("=== recency_factor sweep (dampening_factor=0.5) ===")
print("(0.98 fixes it; dampening alone never does, even at d=0.02 above)")
for gamma in [1.0, 0.99, 0.98, 0.95]:
    result = engine.run_bulcd(make_config(dampening_factor=0.5, recency_factor=gamma))
    probs = result.final_probabilities.reduceRegion(
        reducer=ee.Reducer.first(), geometry=POINT, scale=30
    ).getInfo()
    print(f"recency_factor={gamma}: {probs}")
