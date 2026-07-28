"""Configuration schema for the BULC-D Python rebuild.

SKETCH / DRAFT — not wired to a loader or the engine yet.

Ports two things from the legacy implementation into one typed structure:
  - the GUI's ad-hoc parameter dict `D` in guiBULCD.rtf, built up over the
    script via repeated `helperFunctionsBULCD.updateParams(D, key, value)`
    calls (see line ~168 onward, and ~5930-5975 for the advanced-tuning
    keys: binCuts, modalityDictionary, sensitivityDictionary, verbose,
    plottingMeans);
  - the config-asset pattern in mckenzeBULCD.rtf, which points a `CFG`
    var at a GEE Table asset exposing aoi/startDate/endDate/forestMask/
    bulcdAssetFolder/exportCrs.

The legacy schema's `expectationCollectionParameters` /
`targetCollectionParameters` split (each carrying a per-sensor
`MOdictionary` with yearsList/firstDOY/lastDOY/CloudCoverThreshold) is
intentionally NOT reproduced here — replacing that discrete two-period
comparison with continuous full-archive evidence is the modernization's
primary goal, so `TemporalConfig` below models one continuous window
instead of two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Sensor = Literal[
    "landsat5", "landsat7", "landsat8", "landsat9",
    "sentinel1", "sentinel2", "modis",
]

ReductionBand = Literal["nbr", "swir", "ndvi"]


@dataclass
class StudyAreaConfig:
    aoi_asset: str  # GEE asset path to a Table/Geometry, e.g. "users/.../my_site"
    crs: str = "EPSG:4326"  # legacy exportCrs
    scale: int = 30  # export resolution, meters
    forest_mask_asset: str | None = None  # optional mask asset (mckenzeBULCD's forestMask)


@dataclass
class SensorConfig:
    name: Sensor
    cloud_cover_threshold: float = 20.0
    enabled: bool = True


@dataclass
class TemporalConfig:
    """Continuous-archive evidence window.

    Replaces the legacy expectation-period/target-period split
    (firstExpectationYear / firstTargetYear in guiBULCD.rtf) with a
    single continuous range that BULC updates through recursively.
    """

    start_date: str  # "YYYY-MM-DD" — e.g. earliest usable Landsat coverage
    end_date: str  # "YYYY-MM-DD" — most recent available date
    doy_window: tuple[int, int] = (1, 365)  # seasonal window sampled within each year
    day_step_size: int | None = None  # optional sub-annual sampling cadence


@dataclass
class ReductionConfig:
    band: ReductionBand = "nbr"  # legacy whichReduction / bandName_reduction


@dataclass
class BULCAdvancedParams:
    """Rarely-touched engine tuning — ports 6003.3c-BULC-AdvancedParameters.

    Defaults should reproduce the legacy engine's behavior; override only
    for deliberate experimentation, same caveat as the legacy comment.
    """

    bin_cuts: list[float] = field(
        default_factory=lambda: [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]
    )
    modality_dictionary: dict = field(default_factory=dict)
    sensitivity_dictionary: dict = field(default_factory=dict)
    plotting_means: bool = False
    verbose: bool = False


@dataclass
class ExportConfig:
    destination: Literal["asset", "drive"] = "asset"
    asset_folder: str | None = None  # legacy bulcdAssetFolder
    drive_folder: str | None = None
    max_pixels: int = int(1e13)
    description_prefix: str = "bulcd"


@dataclass
class BULCDConfig:
    study_area: StudyAreaConfig
    sensors: list[SensorConfig]
    temporal: TemporalConfig
    schema_version: str = "1"
    reduction: ReductionConfig = field(default_factory=ReductionConfig)
    bulc_params: BULCAdvancedParams = field(default_factory=BULCAdvancedParams)
    export: ExportConfig = field(default_factory=ExportConfig)
