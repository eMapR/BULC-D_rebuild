from pathlib import Path

import pytest

from bulcd.config.loader import ConfigError, load_config
from bulcd.config.schema import ModalityConfig, SensitivityConfig

EXAMPLE_CONFIG = Path(__file__).parent.parent / "configs" / "example.yaml"

MINIMAL_YAML = """
study_area:
  aoi_asset: users/x/y
evidence:
  expectation:
    sensors:
      L8:
        enabled: true
  target:
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

    assert set(config.evidence.expectation.sensors) == {"L8", "L9", "S2", "S1"}
    assert config.evidence.expectation.sensors["L8"].enabled is True
    assert config.evidence.expectation.sensors["L8"].first_year == 2015
    assert config.evidence.expectation.sensors["L8"].last_year == 2017
    assert config.evidence.target.sensors["L8"].first_year == 2017
    assert config.evidence.target.sensors["L8"].last_year == 2018
    assert config.evidence.expectation.sensors["S1"].sar_polarization == "HV"

    assert config.reduction.band == "swir"
    assert config.modality.constant is True
    assert config.modality.unimodal is True
    assert config.sensitivity.z_score_numerator_factor == 1
    assert config.bin_cuts == [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]
    assert config.plotting_means is True

    assert config.bulc_advanced_params.dampening_factor == 0.5
    assert config.bulc_advanced_params.recency_factor == 1.0
    assert len(config.bulc_advanced_params.custom_transition_matrix) == 10
    assert config.bulc_advanced_params.custom_transition_matrix[0] == [0.16, 0.11, 0.02]

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
        "  expectation:\n    sensors:\n      L8:\n        enabled: true\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="exactly one"):
        load_config(bad_config)

    bad_config.write_text(
        "study_area: {}\n"
        "evidence:\n"
        "  expectation:\n    sensors:\n      L8:\n        enabled: true\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="exactly one"):
        load_config(bad_config)


def test_invalid_sensor_code_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  expectation:\n    sensors:\n      L99:\n        enabled: true\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="L99"):
        load_config(bad_config)


def test_no_enabled_sensors_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  expectation:\n    sensors:\n      L8:\n        enabled: false\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="at least one sensor"):
        load_config(bad_config)


def test_missing_target_period_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  expectation:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="evidence.target"):
        load_config(bad_config)


def test_empty_expectation_sensors_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  expectation:\n    sensors: {}\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="evidence.expectation.sensors"):
        load_config(bad_config)


def test_sar_polarization_rejected_for_non_sar_sensor(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  expectation:\n"
        "    sensors:\n"
        "      L8:\n"
        "        enabled: true\n"
        "        sar_polarization: HV\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
    )
    with pytest.raises(ConfigError, match="sar_polarization"):
        load_config(bad_config)


def test_asset_destination_requires_asset_folder(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "evidence:\n"
        "  expectation:\n    sensors:\n      L8:\n        enabled: true\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
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
    assert config.evidence.expectation.sensors["L8"].first_doy == 1
    assert config.evidence.expectation.sensors["L8"].last_doy == 365
    assert config.bulc_advanced_params.custom_transition_matrix is None
    assert config.bulc_advanced_params.dampening_factor == 0.5
    assert config.study_area.mask_water is True


def test_mask_water_can_be_disabled(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "study_area:\n"
        "  aoi_asset: users/x/y\n"
        "  mask_water: false\n"
        "evidence:\n"
        "  expectation:\n    sensors:\n      L8:\n        enabled: true\n"
        "  target:\n    sensors:\n      L8:\n        enabled: true\n"
        "export:\n  destination: asset\n  asset_folder: users/x/y:out/\n"
    )
    config = load_config(cfg_path)
    assert config.study_area.mask_water is False


def test_custom_transition_matrix_shape_validated(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        MINIMAL_YAML + "bulc_advanced_params:\n"
        "  custom_transition_matrix:\n"
        "    - [0.1, 0.1, 0.1]\n"
        "    - [0.1, 0.1, 0.1]\n"
    )
    with pytest.raises(ConfigError, match="10x3"):
        load_config(cfg_path)


def test_dampening_factor_must_be_in_valid_range(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML + "bulc_advanced_params:\n  dampening_factor: 1.5\n")
    with pytest.raises(ConfigError, match="dampening_factor"):
        load_config(cfg_path)


def test_recency_factor_defaults_to_off(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML)
    config = load_config(cfg_path)
    assert config.bulc_advanced_params.recency_factor == 1.0


def test_posterior_leveler_defaults_to_off(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML)
    config = load_config(cfg_path)
    assert config.bulc_advanced_params.posterior_leveler == 1.0


def test_posterior_leveler_must_be_in_valid_range(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML + "bulc_advanced_params:\n  posterior_leveler: 0\n")
    with pytest.raises(ConfigError, match="posterior_leveler"):
        load_config(cfg_path)


def test_initializing_leveler_defaults_to_flat_uniform(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML)
    config = load_config(cfg_path)
    assert config.bulc_advanced_params.initializing_leveler == 0.0


def test_initializing_leveler_must_be_in_valid_range(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML + "bulc_advanced_params:\n  initializing_leveler: 1.5\n")
    with pytest.raises(ConfigError, match="initializing_leveler"):
        load_config(cfg_path)


def test_recency_factor_must_be_in_valid_range(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(MINIMAL_YAML + "bulc_advanced_params:\n  recency_factor: 1.5\n")
    with pytest.raises(ConfigError, match="recency_factor"):
        load_config(cfg_path)

    cfg_path.write_text(MINIMAL_YAML + "bulc_advanced_params:\n  recency_factor: 0\n")
    with pytest.raises(ConfigError, match="recency_factor"):
        load_config(cfg_path)


def test_bin_cuts_and_transition_matrix_row_count_must_match(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    ten_row_matrix = "\n".join("    - [0.1, 0.1, 0.1]" for _ in range(10))
    cfg_path.write_text(
        MINIMAL_YAML
        + "bin_cuts: [-1, 0, 1]\n"  # 4 bins
        + "bulc_advanced_params:\n"
        + "  custom_transition_matrix:\n"
        + ten_row_matrix
        + "\n"
    )
    with pytest.raises(ConfigError, match="these must match"):
        load_config(cfg_path)
