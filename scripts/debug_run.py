"""Ad hoc debug run of bulcd's Bayesian core against real Earth Engine.

NOT a production entry point - bulcd/cli.py (config-file-driven, proper
argument parsing) is still unwritten (see CLAUDE.md "Current code
state"). This script hardcodes a small test AOI/config so you can
sanity-check the pipeline cheaply via .getInfo() at a single point,
without kicking off a real (billed) export.

Usage:
    conda run -n bulcd python scripts/debug_run.py

Edit SMALL_AOI / POINT / the BULCDConfig below to point at a different
place or time range. See CLAUDE.md "First live-EE verification" for the
run this script is based on and what its output meant.
"""

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
from bulcd.inputs import assemble_evidence_collection, organize_inputs

# Small AOI in the eastern Cascades (WA), ~a couple km across - cheap to
# evaluate, real Landsat coverage. Edit these to test somewhere else.
SMALL_AOI = [
    [-120.60, 47.50],
    [-120.60, 47.52],
    [-120.55, 47.52],
    [-120.55, 47.50],
]
POINT = ee.Geometry.Point([-120.575, 47.51])

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
            "L8": SensorEvidenceConfig(
                enabled=True,
                first_year=2014,
                last_year=2021,
                first_doy=152,
                last_doy=273,
                cloud_cover_threshold=40,
            )
        },
        expectation_first_year=2014,
        expectation_last_year=2016,
    ),
    reduction=ReductionConfig(band="nbr"),
    modality=ModalityConfig(constant=True, unimodal=True),
    sensitivity=SensitivityConfig(),
    bulc_advanced_params=BULCAdvancedParams(
        custom_transition_matrix=NBR12_TRANSITION_MATRIX,
        # dampening_factor defaults to 0.5 - see CLAUDE.md "First live-EE
        # verification" for why 1.0 (no dampening) was a bad default.
    ),
)

print("=== Step 1: assemble_evidence_collection ===")
evidence = assemble_evidence_collection(config)
print("evidence count:", evidence.size().getInfo())

print("=== Step 2: organize_inputs ===")
organized = organize_inputs(config)
print("lof_zscore count:", organized.lof_zscore.size().getInfo())

r2_value = organized.expectation_r2.reduceRegion(
    reducer=ee.Reducer.first(), geometry=POINT, scale=30
).getInfo()
print("expectation_r2 at point:", r2_value)

first_zscore = organized.lof_zscore.first().reduceRegion(
    reducer=ee.Reducer.first(), geometry=POINT, scale=30
).getInfo()
print("first zscore image at point:", first_zscore)

print("=== Step 3: engine.run_bulcd ===")
result = engine.run_bulcd(config)
final_probs = result.final_probabilities.reduceRegion(
    reducer=ee.Reducer.first(), geometry=POINT, scale=30
).getInfo()
print("final_probabilities at point:", final_probs)

print("ALL STEPS COMPLETED")
