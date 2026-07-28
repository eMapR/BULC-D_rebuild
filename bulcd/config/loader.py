"""Loads a BULCDConfig from a YAML parameter file.

A misconfigured run is expensive — it kicks off a real Earth Engine
export — so this validates explicitly and fails loudly on anything
missing or malformed rather than silently falling back to a default
that might not be what the user intended.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bulcd.config.schema import (
    BULCAdvancedParams,
    BULCDConfig,
    ExportConfig,
    ReductionConfig,
    SensorConfig,
    StudyAreaConfig,
    TemporalConfig,
)

_VALID_SENSORS = {
    "landsat5", "landsat7", "landsat8", "landsat9",
    "sentinel1", "sentinel2", "modis",
}
_VALID_REDUCTION_BANDS = {"nbr", "swir", "ndvi"}
_VALID_EXPORT_DESTINATIONS = {"asset", "drive"}


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

    return BULCDConfig(
        study_area=_build_study_area(_require_section(raw, "study_area", path)),
        sensors=_build_sensors(_require_section(raw, "sensors", path)),
        temporal=_build_temporal(_require_section(raw, "temporal", path)),
        schema_version=str(raw.get("schema_version", "1")),
        reduction=_build_reduction(raw.get("reduction", {})),
        bulc_params=_build_bulc_params(raw.get("bulc_params", {})),
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
    return StudyAreaConfig(
        aoi_asset=_require_field(section, "aoi_asset", "study_area"),
        crs=section.get("crs", "EPSG:4326"),
        scale=section.get("scale", 30),
        forest_mask_asset=section.get("forest_mask_asset"),
    )


def _build_sensors(section: Any) -> list[SensorConfig]:
    if not isinstance(section, list) or not section:
        raise ConfigError("'sensors' must be a non-empty list")

    sensors = []
    for i, entry in enumerate(section):
        name = _require_field(entry, "name", f"sensors[{i}]")
        if name not in _VALID_SENSORS:
            raise ConfigError(
                f"sensors[{i}].name '{name}' is not one of {sorted(_VALID_SENSORS)}"
            )
        sensors.append(
            SensorConfig(
                name=name,
                cloud_cover_threshold=entry.get("cloud_cover_threshold", 20.0),
                enabled=entry.get("enabled", True),
            )
        )
    return sensors


def _build_temporal(section: dict[str, Any]) -> TemporalConfig:
    start_date = _require_field(section, "start_date", "temporal")
    end_date = _require_field(section, "end_date", "temporal")
    doy_window = tuple(section.get("doy_window", (1, 365)))
    if len(doy_window) != 2:
        raise ConfigError(
            "temporal.doy_window must have exactly 2 values [first_doy, last_doy]"
        )
    return TemporalConfig(
        start_date=start_date,
        end_date=end_date,
        doy_window=doy_window,
        day_step_size=section.get("day_step_size"),
    )


def _build_reduction(section: dict[str, Any]) -> ReductionConfig:
    band = section.get("band", "nbr")
    if band not in _VALID_REDUCTION_BANDS:
        raise ConfigError(
            f"reduction.band '{band}' is not one of {sorted(_VALID_REDUCTION_BANDS)}"
        )
    return ReductionConfig(band=band)


def _build_bulc_params(section: dict[str, Any]) -> BULCAdvancedParams:
    defaults = BULCAdvancedParams()
    return BULCAdvancedParams(
        bin_cuts=section.get("bin_cuts", defaults.bin_cuts),
        modality_dictionary=section.get("modality_dictionary", defaults.modality_dictionary),
        sensitivity_dictionary=section.get(
            "sensitivity_dictionary", defaults.sensitivity_dictionary
        ),
        plotting_means=section.get("plotting_means", defaults.plotting_means),
        verbose=section.get("verbose", defaults.verbose),
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
