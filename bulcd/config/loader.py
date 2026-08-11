"""Loads a BULCDConfig from a YAML parameter file.

A misconfigured run is expensive — it kicks off a real Earth Engine
export — so this validates explicitly and fails loudly on anything
missing or malformed rather than silently falling back to a default
that might not be what the user intended. See bulcd/config/schema.py's
module docstring for where each field comes from in the legacy schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bulcd.config.schema import (
    BULCAdvancedParams,
    BULCDConfig,
    EvidenceConfig,
    EvidencePeriodConfig,
    ExportConfig,
    ModalityConfig,
    ReductionConfig,
    SensitivityConfig,
    SensorEvidenceConfig,
    StudyAreaConfig,
)

_VALID_SENSOR_CODES = {"L5", "L7", "L8", "L9", "MO", "S2", "S1", "AL", "NI", "DW"}
_SAR_SENSOR_CODES = {"S1", "AL"}
_VALID_REDUCTION_BANDS = {"nbr", "swir", "ndvi"}
_VALID_EXPORT_DESTINATIONS = {"asset", "drive"}
_VALID_SAR_POLARIZATIONS = {"HH", "HV", "VH", "VV"}


class ConfigError(ValueError):
    """Raised when a parameter file is missing or malformed."""


def load_config(path: str | Path) -> BULCDConfig:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    with path.open() as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ConfigError(
            f"{path}: top-level YAML must be a mapping, got {type(raw).__name__}"
        )

    bin_cuts = raw.get("bin_cuts", [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2])
    bulc_advanced_params = _build_bulc_advanced_params(raw.get("bulc_advanced_params", {}))

    if bulc_advanced_params.custom_transition_matrix is not None and len(bin_cuts) + 1 != len(
        bulc_advanced_params.custom_transition_matrix
    ):
        raise ConfigError(
            f"bin_cuts has {len(bin_cuts)} cut points (implying {len(bin_cuts) + 1} bins) but "
            f"bulc_advanced_params.custom_transition_matrix has "
            f"{len(bulc_advanced_params.custom_transition_matrix)} rows - these must match"
        )

    return BULCDConfig(
        study_area=_build_study_area(_require_section(raw, "study_area", path)),
        evidence=_build_evidence(_require_section(raw, "evidence", path)),
        schema_version=str(raw.get("schema_version", "1")),
        reduction=_build_reduction(raw.get("reduction", {})),
        modality=_build_modality(raw.get("modality", {})),
        sensitivity=_build_sensitivity(raw.get("sensitivity", {})),
        bin_cuts=bin_cuts,
        harmonic_constant=raw.get("harmonic_constant", False),
        plotting_means=raw.get("plotting_means", False),
        verbose=raw.get("verbose", False),
        bulc_advanced_params=bulc_advanced_params,
        export=_build_export(raw.get("export", {})),
    )


def _require_section(raw: dict[str, Any], key: str, path: Path) -> Any:
    if key not in raw:
        raise ConfigError(f"{path}: missing required section '{key}'")
    return raw[key]


def _require_field(section: dict[str, Any], key: str, section_name: str) -> Any:
    if not isinstance(section, dict):
        raise ConfigError(f"{section_name} must be a mapping, got {type(section).__name__}")
    if section.get(key) is None:
        raise ConfigError(f"{section_name}.{key} is required")
    return section[key]


def _build_study_area(section: dict[str, Any]) -> StudyAreaConfig:
    aoi_asset = section.get("aoi_asset")
    aoi_coordinates = section.get("aoi_coordinates")
    if bool(aoi_asset) == bool(aoi_coordinates):
        raise ConfigError(
            "study_area: exactly one of 'aoi_asset' or 'aoi_coordinates' must be set"
        )
    return StudyAreaConfig(
        aoi_asset=aoi_asset,
        aoi_coordinates=aoi_coordinates,
        crs=section.get("crs", "EPSG:4326"),
        scale=section.get("scale", 30),
        forest_mask_asset=section.get("forest_mask_asset"),
        mask_water=section.get("mask_water", True),
        mask_non_forest=section.get("mask_non_forest", True),
    )


def _build_evidence(section: dict[str, Any]) -> EvidenceConfig:
    return EvidenceConfig(
        day_step_size=section.get("day_step_size", 4),
        expectation=_build_evidence_period(_require_field(section, "expectation", "evidence"), "expectation"),
        target=_build_evidence_period(_require_field(section, "target", "evidence"), "target"),
    )


def _build_evidence_period(section: dict[str, Any], period_name: str) -> EvidencePeriodConfig:
    if not isinstance(section, dict):
        raise ConfigError(f"evidence.{period_name} must be a mapping, got {type(section).__name__}")

    sensors_section = section.get("sensors")
    if not isinstance(sensors_section, dict) or not sensors_section:
        raise ConfigError(
            f"evidence.{period_name}.sensors must be a non-empty mapping of sensor code -> config"
        )

    sensors: dict[str, SensorEvidenceConfig] = {}
    for code, entry in sensors_section.items():
        if code not in _VALID_SENSOR_CODES:
            raise ConfigError(
                f"evidence.{period_name}.sensors key '{code}' is not one of "
                f"{sorted(_VALID_SENSOR_CODES)}"
            )
        sensors[code] = _build_sensor_evidence(entry, code, period_name)

    if not any(s.enabled for s in sensors.values()):
        raise ConfigError(
            f"evidence.{period_name}.sensors: at least one sensor must have enabled: true"
        )

    return EvidencePeriodConfig(sensors=sensors)


def _build_sensor_evidence(entry: dict[str, Any], code: str, period_name: str) -> SensorEvidenceConfig:
    prefix = f"evidence.{period_name}.sensors.{code}"
    if not isinstance(entry, dict):
        raise ConfigError(f"{prefix} must be a mapping, got {type(entry).__name__}")

    sar_polarization = entry.get("sar_polarization")
    if sar_polarization is not None:
        if code not in _SAR_SENSOR_CODES:
            raise ConfigError(
                f"{prefix}.sar_polarization is only valid for {sorted(_SAR_SENSOR_CODES)}"
            )
        if sar_polarization not in _VALID_SAR_POLARIZATIONS:
            raise ConfigError(
                f"{prefix}.sar_polarization '{sar_polarization}' is not one of "
                f"{sorted(_VALID_SAR_POLARIZATIONS)}"
            )

    return SensorEvidenceConfig(
        enabled=entry.get("enabled", False),
        first_year=entry.get("first_year"),
        last_year=entry.get("last_year"),
        first_doy=entry.get("first_doy", 1),
        last_doy=entry.get("last_doy", 365),
        cloud_cover_threshold=entry.get("cloud_cover_threshold", 20.0),
        sar_polarization=sar_polarization,
    )


def _build_reduction(section: dict[str, Any]) -> ReductionConfig:
    band = section.get("band", "nbr")
    if band not in _VALID_REDUCTION_BANDS:
        raise ConfigError(
            f"reduction.band '{band}' is not one of {sorted(_VALID_REDUCTION_BANDS)}"
        )
    return ReductionConfig(band=band)


def _build_modality(section: dict[str, Any]) -> ModalityConfig:
    defaults = ModalityConfig()
    return ModalityConfig(
        constant=section.get("constant", defaults.constant),
        linear=section.get("linear", defaults.linear),
        unimodal=section.get("unimodal", defaults.unimodal),
        bimodal=section.get("bimodal", defaults.bimodal),
        trimodal=section.get("trimodal", defaults.trimodal),
    )


def _build_sensitivity(section: dict[str, Any]) -> SensitivityConfig:
    defaults = SensitivityConfig()
    return SensitivityConfig(
        z_score_numerator_factor=section.get(
            "z_score_numerator_factor", defaults.z_score_numerator_factor
        ),
        z_score_denominator_factor=section.get(
            "z_score_denominator_factor", defaults.z_score_denominator_factor
        ),
    )


def _build_bulc_advanced_params(section: dict[str, Any]) -> BULCAdvancedParams:
    if not isinstance(section, dict):
        raise ConfigError(f"bulc_advanced_params must be a mapping, got {type(section).__name__}")

    custom_transition_matrix = section.get("custom_transition_matrix")
    if custom_transition_matrix is not None:
        if len(custom_transition_matrix) != 10 or any(
            len(row) != 3 for row in custom_transition_matrix
        ):
            raise ConfigError(
                "bulc_advanced_params.custom_transition_matrix must be a 10x3 matrix "
                "(10 z-score collection bins x 3 decision classes "
                "[decrease, unchanged, increase])"
            )

    dampening_factor = section.get("dampening_factor", 0.5)
    if not (0 < dampening_factor <= 1):
        raise ConfigError(
            f"bulc_advanced_params.dampening_factor ({dampening_factor}) must satisfy "
            "0 < d <= 1 (Cardille & Fortin 2016 section 4.6)"
        )

    recency_factor = section.get("recency_factor", 1.0)
    if not (0 < recency_factor <= 1):
        raise ConfigError(
            f"bulc_advanced_params.recency_factor ({recency_factor}) must satisfy "
            "0 < recency_factor <= 1 (see bulc.py's discount())"
        )

    posterior_leveler = section.get("posterior_leveler", 1.0)
    if not (0 < posterior_leveler <= 1):
        raise ConfigError(
            f"bulc_advanced_params.posterior_leveler ({posterior_leveler}) must satisfy "
            "0 < posterior_leveler <= 1 (see bulc.py's run_bulc()/BULC-Minimal-Module-107)"
        )

    initializing_leveler = section.get("initializing_leveler", 0.0)
    if not (0 <= initializing_leveler <= 1):
        raise ConfigError(
            f"bulc_advanced_params.initializing_leveler ({initializing_leveler}) must satisfy "
            "0 <= initializing_leveler <= 1 (0 = flat uniform start, this rebuild's prior "
            "default; see BULCAdvancedParams docstring)"
        )

    known_keys = {
        "custom_transition_matrix",
        "dampening_factor",
        "recency_factor",
        "posterior_leveler",
        "initializing_leveler",
    }
    raw = {k: v for k, v in section.items() if k not in known_keys}

    return BULCAdvancedParams(
        custom_transition_matrix=custom_transition_matrix,
        dampening_factor=dampening_factor,
        recency_factor=recency_factor,
        posterior_leveler=posterior_leveler,
        initializing_leveler=initializing_leveler,
        raw=raw,
    )


def _build_export(section: dict[str, Any]) -> ExportConfig:
    destination = section.get("destination", "asset")
    if destination not in _VALID_EXPORT_DESTINATIONS:
        raise ConfigError(
            f"export.destination '{destination}' is not one of "
            f"{sorted(_VALID_EXPORT_DESTINATIONS)}"
        )
    if destination == "asset" and not section.get("asset_folder"):
        raise ConfigError("export.asset_folder is required when export.destination is 'asset'")
    if destination == "drive" and not section.get("drive_folder"):
        raise ConfigError("export.drive_folder is required when export.destination is 'drive'")

    return ExportConfig(
        destination=destination,
        asset_folder=section.get("asset_folder"),
        drive_folder=section.get("drive_folder"),
        max_pixels=section.get("max_pixels", int(1e13)),
        description_prefix=section.get("description_prefix", "bulcd"),
    )
