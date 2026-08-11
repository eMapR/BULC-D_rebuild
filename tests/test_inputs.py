"""Tests for the parts of bulcd.inputs that don't require ee.Initialize().

Full evidence-assembly/regression-fit testing needs a real GEE Cloud
project (constructing an ee.Image/ee.ImageCollection raises "Earth Engine
client library not initialized" otherwise) - not set up yet, see
CLAUDE.md. These tests cover the pure-Python date math and the modality-
resolution logic - honestly testable without a live session, unlike the
regression/z-score graph-construction code itself.
"""

import datetime

from bulcd.config.schema import ModalityConfig, SensorEvidenceConfig
from bulcd.inputs import _date_bounds, _select_modality_regressors


def test_date_bounds_uses_launch_year_when_first_year_unset():
    cfg = SensorEvidenceConfig(enabled=True, first_year=None, last_year=2020)
    start, end = _date_bounds("L8", cfg)
    assert start == "2013-01-01"  # Landsat 8 launch year
    assert end == "2020-01-01"


def test_date_bounds_uses_today_when_last_year_unset():
    cfg = SensorEvidenceConfig(enabled=True, first_year=2015, last_year=None)
    start, end = _date_bounds("L9", cfg)
    assert start == "2015-01-01"
    assert end == f"{datetime.date.today().year + 1}-01-01"


def test_date_bounds_explicit_range():
    cfg = SensorEvidenceConfig(enabled=True, first_year=2018, last_year=2022)
    start, end = _date_bounds("L5", cfg)
    assert start == "2018-01-01"
    assert end == "2022-01-01"


def test_select_modality_regressors_multiple_flags_are_additive():
    # CONFIRMED 2026-08-10 against the real
    # afn_determineHarmonicIndependentsViaModalityDictionary source
    # (legacy/502.7-1h5-HarmonicFunctions.txt): every true flag's terms
    # concatenate onto the list - NOT "richest shape wins," this
    # function's earlier, incorrect assumption. unimodal+trimodal true
    # together yields BOTH sets of terms, not just trimodal's.
    modality = ModalityConfig(constant=True, unimodal=True, trimodal=True)
    assert _select_modality_regressors(modality) == [
        "constant", "cos", "sin", "cos3", "sin3"
    ]


def test_select_modality_regressors_bimodal():
    modality = ModalityConfig(bimodal=True)
    assert _select_modality_regressors(modality) == ["constant", "cos2", "sin2"]


def test_select_modality_regressors_unimodal_uses_full_first_order_harmonic():
    # Confirmed 2026-08-10 against a real GUI run's Console output
    # (production's own `harrrmonic names (Optical)` was
    # ["constant","cos","sin"]) - overrides the earlier Willis (2022)
    # eq. 6 simplified-2-term assumption. See CLAUDE.md "Legacy-GUI
    # parameter matching".
    modality = ModalityConfig(constant=True, unimodal=True)
    assert _select_modality_regressors(modality) == ["constant", "cos", "sin"]


def test_select_modality_regressors_linear():
    modality = ModalityConfig(constant=False, linear=True)
    assert _select_modality_regressors(modality) == ["constant", "t"]


def test_select_modality_regressors_defaults_to_constant():
    modality = ModalityConfig(constant=False, linear=False, unimodal=False)
    assert _select_modality_regressors(modality) == ["constant"]
