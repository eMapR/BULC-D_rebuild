from pathlib import Path

import pytest

from bulcd.config.loader import ConfigError, load_config
from bulcd.config.schema import BULCAdvancedParams

EXAMPLE_CONFIG = Path(__file__).parent.parent / "configs" / "example.yaml"


def test_loads_example_config():
    config = load_config(EXAMPLE_CONFIG)

    assert config.study_area.aoi_asset == "users/example-user/example-project:sites/example_site"
    assert config.study_area.scale == 30
    assert config.study_area.forest_mask_asset is None

    assert [s.name for s in config.sensors] == ["landsat8", "landsat9", "sentinel2"]
    assert all(s.cloud_cover_threshold == 20 for s in config.sensors)

    assert config.temporal.start_date == "1984-01-01"
    assert config.temporal.end_date == "2026-07-28"
    assert config.temporal.doy_window == (152, 273)

    assert config.reduction.band == "nbr"
    assert config.export.destination == "asset"
    assert config.export.asset_folder == "users/example-user/example-project:bulcd_outputs/"


def test_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/path.yaml")


def test_missing_required_section_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("sensors:\n  - name: landsat8\n")
    with pytest.raises(ConfigError, match="study_area"):
        load_config(bad_config)


def test_missing_required_field_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  crs: EPSG:4326\n"
        "sensors:\n"
        "  - name: landsat8\n"
        "temporal:\n"
        "  start_date: '1984-01-01'\n"
        "  end_date: '2026-07-28'\n"
    )
    with pytest.raises(ConfigError, match="study_area.aoi_asset"):
        load_config(bad_config)


def test_invalid_sensor_name_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "sensors:\n"
        "  - name: landsat99\n"
        "temporal:\n"
        "  start_date: '1984-01-01'\n"
        "  end_date: '2026-07-28'\n"
    )
    with pytest.raises(ConfigError, match="landsat99"):
        load_config(bad_config)


def test_empty_sensors_list_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "sensors: []\n"
        "temporal:\n"
        "  start_date: '1984-01-01'\n"
        "  end_date: '2026-07-28'\n"
    )
    with pytest.raises(ConfigError, match="non-empty list"):
        load_config(bad_config)


def test_asset_destination_requires_asset_folder(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "sensors:\n"
        "  - name: landsat8\n"
        "temporal:\n"
        "  start_date: '1984-01-01'\n"
        "  end_date: '2026-07-28'\n"
        "export:\n"
        "  destination: asset\n"
    )
    with pytest.raises(ConfigError, match="asset_folder"):
        load_config(bad_config)


def test_bulc_params_partial_override_keeps_other_defaults(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "sensors:\n"
        "  - name: landsat8\n"
        "temporal:\n"
        "  start_date: '1984-01-01'\n"
        "  end_date: '2026-07-28'\n"
        "bulc_params:\n"
        "  verbose: true\n"
        "export:\n"
        "  destination: asset\n"
        "  asset_folder: users/x/y:out/\n"
    )
    config = load_config(cfg_path)
    assert config.bulc_params.verbose is True
    assert config.bulc_params.bin_cuts == BULCAdvancedParams().bin_cuts
