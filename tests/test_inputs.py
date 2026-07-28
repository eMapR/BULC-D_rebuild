"""Tests for the parts of bulcd.inputs that don't require ee.Initialize().

Full evidence-assembly testing needs a real GEE Cloud project (ee.Image/
ee.ImageCollection construction raises "Earth Engine client library not
initialized" otherwise) - not set up yet, see CLAUDE.md. These tests cover
the pure-Python date math and the NotImplementedError stubs' contracts.
"""

import datetime

import pytest

from bulcd.config.schema import SensorEvidenceConfig
from bulcd.inputs import _date_bounds


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


def test_organize_inputs_is_an_explicit_stub():
    from bulcd.inputs import organize_inputs

    with pytest.raises(NotImplementedError, match="organizeBULCD_Inputs"):
        organize_inputs(config=None)
