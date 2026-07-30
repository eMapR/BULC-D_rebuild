"""Tests for the parts of bulcd.engine that don't require ee.Initialize().

run_bulcd()'s own upfront config guards (missing transition matrix,
mismatched bin_cuts/matrix row count) raise before ever calling
organize_inputs() or touching ee.* - see CLAUDE.md's standing caveat that
the rest of the pipeline (binning, transition-matrix lookup, the Bayesian
fold itself) needs a live GEE Cloud project to test meaningfully.
"""

import pytest

from bulcd.config.schema import (
    BULCAdvancedParams,
    BULCDConfig,
    EvidenceConfig,
    StudyAreaConfig,
)
from bulcd.engine import run_bulcd

_STUDY_AREA = StudyAreaConfig(aoi_coordinates=[[0, 0], [0, 1], [1, 1]])
_EVIDENCE = EvidenceConfig(sensors={}, expectation_first_year=2015, expectation_last_year=2017)


def test_run_bulcd_requires_transition_matrix():
    config = BULCDConfig(
        study_area=_STUDY_AREA,
        evidence=_EVIDENCE,
        bulc_advanced_params=BULCAdvancedParams(custom_transition_matrix=None),
    )
    with pytest.raises(ValueError, match="custom_transition_matrix"):
        run_bulcd(config)


def test_run_bulcd_requires_matching_bin_cuts_and_matrix_row_count():
    config = BULCDConfig(
        study_area=_STUDY_AREA,
        evidence=_EVIDENCE,
        bin_cuts=[-1, 0, 1],  # implies 4 bins
        bulc_advanced_params=BULCAdvancedParams(
            custom_transition_matrix=[[0.1, 0.1, 0.1] for _ in range(10)]  # 10 rows
        ),
    )
    with pytest.raises(ValueError, match="these must produce the same number of bins"):
        run_bulcd(config)
