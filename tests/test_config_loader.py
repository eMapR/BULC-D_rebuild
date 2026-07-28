from pathlib import Path

import pytest

from bulcd.config.loader import ConfigError, load_config
from bulcd.config.schema import ModalityConfig, SensitivityConfig

EXAMPLE_CONFIG = Path(__file__).parent.parent / "configs" / "example.yaml"

MINIMAL_YAML = """
study_area:
  aoi_asset: users/x/y
evidence:
  sensors:
    L8:
      enabled: true
export:
  destination: asset
  asset_folder: users/x/y:out/
"""


def test_loads_example_config():
    config = load_config(EXAMPLE_CONFIG)

    assert config.study_area.aoi_asset is None
    assert config.study_area.aoi_coordinates == [
        [-126.04, 49.59], [-126.04, 40.76], [-118.93, 40.76], [-118.93, 49.59]
    ]
    assert config.study_area.scale == 30

    assert set(config.evidence.sensors) == {"L8", "L9", "S2", "S1"}
    assert config.evidence.sensors["L8"].enabled is True
    assert config.evidence.sensors["L8"].first_year == 2013
    assert config.evidence.sensors["L8"].last_year is None
    assert config.evidence.sensors["S2"].s2_cloud_mask.cld_prb_thresh == 50
    assert config.evidence.sensors["S1"].sar_polarization == "HV"

    assert config.reduction.band == "swir"
    assert config.modality.constant is True
    assert config.modality.unimodal is True
    assert config.sensitivity.z_score_numerator_factor == 1
    assert config.bin_cuts == [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]
    assert config.plotting_means is True

    assert config.export.destination == "asset"
    assert config.export.asset_folder == "users/example-user/example-project:bulcd_outputs/"


def test_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/path.yaml")


def test_missing_required_section_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("study_area:\n  aoi_asset: users/x/y\n")
    with pytest.raises(ConfigError, match="evidence"):
        load_config(bad_config)


def test_study_area_requires_exactly_one_aoi_source(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "  aoi_coordinates: [[0, 0], [0, 1], [1, 1]]\n"
        "evidence:\n"
        "  sensors:\n"
        "    L8:\n"
        "      enabled: true\n"
    )
    with pytest.raises(ConfigError, match="exactly one"):
        load_config(bad_config)

    bad_config.write_text(
        "study_area: {}\n"
        "evidence:\n"
        "  sensors:\n"
        "    L8:\n"
        "      enabled: true\n"
    )
    with pytest.raises(ConfigError, match="exactly one"):
        load_config(bad_config)


def test_invalid_sensor_code_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  sensors:\n"
        "    L99:\n"
        "      enabled: true\n"
    )
    with pytest.raises(ConfigError, match="L99"):
        load_config(bad_config)


def test_no_enabled_sensors_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  sensors:\n"
        "    L8:\n"
        "      enabled: false\n"
    )
    with pytest.raises(ConfigError, match="at least one sensor"):
        load_config(bad_config)


def test_sar_polarization_rejected_for_non_sar_sensor(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  sensors:\n"
        "    L8:\n"
        "      enabled: true\n"
        "      sar_polarization: HV\n"
    )
    with pytest.raises(ConfigError, match="sar_polarization"):
        load_config(bad_config)


def test_s2_cloud_mask_rejected_for_non_s2_sensor(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  sensors:\n"
        "    L8:\n"
        "      enabled: true\n"
        "      s2_cloud_mask: {}\n"
    )
    with pytest.raises(ConfigError, match="s2_cloud_mask"):
        load_config(bad_config)


def test_asset_destination_requires_asset_folder(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  sensors:\n"
        "    L8:\n"
        "      enabled: true\n"
        "export:\n"
        "  destination: asset\n"
    )
    with pytest.raises(ConfigError, match="asset_folder"):
        load_config(bad_config)


def test_modality_partial_override_keeps_other_defaults(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML + "modality:\n  unimodal: true\n")
    config = load_config(cfg_path)
    assert config.modality.unimodal is True
    assert config.modality.constant == ModalityConfig().constant
    assert config.modality.bimodal == ModalityConfig().bimodal


def test_sensitivity_partial_override_keeps_other_defaults(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML + "sensitivity:\n  z_score_numerator_factor: 2\n")
    config = load_config(cfg_path)
    assert config.sensitivity.z_score_numerator_factor == 2
    assert (
        config.sensitivity.z_score_denominator_factor
        == SensitivityConfig().z_score_denominator_factor
    )


def test_minimal_config_uses_defaults(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML)
    config = load_config(cfg_path)
    assert config.reduction.band == "nbr"
    assert config.bin_cuts == [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]
    assert config.evidence.day_step_size == 4
    assert config.evidence.sensors["L8"].first_doy == 1
    assert config.evidence.sensors["L8"].last_doy == 365
