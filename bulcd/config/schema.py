"""Configuration schema for the BULC-D Python rebuild.

SKETCH / DRAFT — not wired to the engine yet (no engine exists).

This schema is a direct structural port of the legacy production
parameter file, adapted for one change: it replaces the legacy's
discrete "expectation period vs. target period" comparison with a
single continuous per-sensor evidence window, per the modernization's
primary goal (see CLAUDE.md "Modernization goals" — full Landsat
archive as continuous evidence, not a two-period comparison).

Provenance (see legacy/ for full source):

- `legacy/BULCD-Caller-Current.txt` — the current (V52a) production
  caller script. Shows the exact call shape:
  `afn_organizeBULCD_Inputs(inputParameters)` returns a `bulcD_input`
  object; `afn_BULCD({defaultStudyArea, binCuts, targetLOFAsZScore,
  BULCargumentDictionaryPlus})` returns `finalBULCprobs` etc.; a
  separate `afn_interpretBULCDResult(...)` does post-run analysis
  (drop/up/timing/wasItEver...). Requires span THREE separate GEE
  repos owned by `alemlakes`: `r-2903-Dev` (the BULC-D/BULC algorithm
  modules themselves), `r-2909-BULC-Releases` (the current parameter
  files this schema is based on), and `r-2902-Dev` (the result
  interpreter). This is a live discrepancy in the legacy codebase, not
  a mistake on our part — the "Releases" parameter files are current,
  but the algorithm modules they're paired with are still versioned
  under the old "Dev" repo path.

- `legacy/BULCD-InputParameters-v5.txt` — a real example input
  parameter file (`BULCD-Caller-Parameters/BULCD-InputParameters-v5`
  in `r-2909-BULC-Releases`). This is what fills in nearly every field
  below; see per-field notes.

Known gap: `BULCD-AdvancedParameters-v5` (transition matrices / more
detailed intermediate outputs, per the caller script's own comment)
has NOT been provided yet — `BULCAdvancedParams` below is a placeholder
until we have it.

Also known gap: the actual regression-fitting / R2 / residual / z-score
math lives inside `afn_organizeBULCD_Inputs` (module
`6002.A2b.3-BULCD-Module-organizeBULCD_Inputs` in `r-2903-Dev`), whose
source we don't have. This schema only captures the *parameters* that
feed that function, not its internals.

Intentionally dropped from the legacy schema: `centeringZoom` — only
used for `Map.centerObject()` in the interactive GUI, meaningless for a
headless/programmatic engine (this whole rebuild's point, per
CLAUDE.md's "Separate the algorithm from the GUI").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Legacy `datasetSelection` dict keys (BULCD-InputParameters-v5): L5/L7/L8/L9
# = Landsat 5/7/8/9, MO = MODIS, S2/S1 = Sentinel-2/Sentinel-1, AL = ALOS
# (SAR), NI = NICFI (Planet), DW = Dynamic World. AL/NI/DW appear in the
# legacy dict but aren't otherwise documented in our reference material —
# kept for fidelity, but expect them to need confirmation before use.
SensorCode = Literal["L5", "L7", "L8", "L9", "MO", "S2", "S1", "AL", "NI", "DW"]

# Legacy carries this as THREE fields that are always kept in sync:
# `whichReduction` (display case, e.g. "SWIR"), `bandName_reduction` and
# `bandNameToFit` (both lowercase, e.g. "swir"). We collapse all three into
# one field; derive the display-case form if something downstream needs it.
ReductionBand = Literal["nbr", "swir", "ndvi"]

SARPolarization = Literal["HH", "HV", "VH", "VV"]


@dataclass
class StudyAreaConfig:
    """Legacy `defaultStudyArea`.

    The legacy file builds this as an inline `ee.Geometry` from a
    coordinates string (BULCD-InputParameters-v5), but a commented-out
    line shows the alternative of pointing at an `ee.FeatureCollection`
    asset (also seen in mckenzeBULCD.rtf's `aoi`). We support both;
    exactly one of `aoi_asset` / `aoi_coordinates` must be set (enforced
    in loader.py, not here — dataclasses can't express an XOR).
    """

    aoi_asset: str | None = None
    aoi_coordinates: list[list[float]] | None = None  # one polygon ring: [[lon, lat], ...]
    crs: str = "EPSG:4326"  # legacy exportCrs (mckenzeBULCD.rtf)
    scale: int = 30  # export resolution, meters
    forest_mask_asset: str | None = None  # optional mask asset (mckenzeBULCD.rtf's forestMask)


@dataclass
class S2CloudMaskConfig:
    """Legacy Sentinel-2 `s2cloudless` block (BULCD-InputParameters-v5).

    Uses the community s2cloudless method:
    https://developers.google.com/earth-engine/tutorials/community/sentinel-2-s2cloudless

    The legacy dict repeats `CloudCoverThreshold` here (identical value to
    the sensor-level one) — consolidated to the single
    `SensorEvidenceConfig.cloud_cover_threshold` field instead of duplicating it.
    """

    cld_prb_thresh: float = 50.0  # cloud probability (%) above which a pixel is "cloud"
    nir_drk_thresh: float = 0.15  # NIR reflectance below which a pixel is potential cloud shadow
    cld_prj_dist: float = 3.0  # max distance (km) to search for cloud shadows from cloud edges
    buffer: float = 50.0  # distance (m) to dilate cloud-identified objects


@dataclass
class SensorEvidenceConfig:
    """One sensor's contribution to the continuous evidence stream.

    Mirrors one of the legacy per-sensor sub-dictionaries (`L5dictionary`,
    `L8dictionary`, `S2dictionary`, `S1dictionary`, etc. in
    BULCD-InputParameters-v5) — but collapsed onto ONE continuous year
    range instead of the legacy's separate expectation-period and
    target-period dictionaries. This IS the modernization's primary
    change: instead of picking a short "expectation" window and a short
    "target" window, one sensor config spans as much of its archive as
    you want treated as continuous evidence.
    """

    enabled: bool = False
    first_year: int | None = None  # None = earliest year this sensor has coverage
    last_year: int | None = None  # None = most recent available
    first_doy: int = 1  # seasonal window start, applied every year (legacy firstDOY)
    last_doy: int = 365  # seasonal window end, applied every year (legacy lastDOY)
    cloud_cover_threshold: float = 20.0  # legacy CloudCoverThreshold
    sar_polarization: SARPolarization | None = None  # S1/AL only; legacy SARValueToTrack
    s2_cloud_mask: S2CloudMaskConfig | None = None  # S2 only


@dataclass
class EvidenceConfig:
    """Continuous-archive evidence window across all enabled sensors.

    Replaces the legacy's `expectationCollectionParameters` /
    `targetCollectionParameters` pair with one continuous stream that
    BULC updates through sequentially, instead of comparing two discrete
    periods.
    """

    day_step_size: int = 4  # legacy dayStepSize
    sensors: dict[SensorCode, SensorEvidenceConfig] = field(default_factory=dict)


@dataclass
class ReductionConfig:
    band: ReductionBand = "nbr"  # legacy whichReduction / bandName_reduction / bandNameToFit


@dataclass
class ModalityConfig:
    """Legacy `modalityDictionary`.

    Selects the functional form fit to the expectation-period seasonal
    curve at each pixel: constant (no seasonality — typical evergreen),
    linear (trend only), unimodal (one seasonal peak — typical
    deciduous), bimodal (two peaks), trimodal (three peaks). NOT
    mutually exclusive in the legacy example (both `constant` and
    `unimodal` are `true`) — read as "candidate shapes to try," not a
    single selector, until `organizeBULCD_Inputs`'s source confirms how
    multiple `true` values are resolved.
    """

    constant: bool = True
    linear: bool = False
    unimodal: bool = False
    bimodal: bool = False
    trimodal: bool = False


@dataclass
class SensitivityConfig:
    """Legacy `sensitivityDictionary`.

    Scales the expectation-model residual into a z-score
    (`targetLOFAsZScore`); exact formula lives in the still-missing
    `organizeBULCD_Inputs` source, not here.
    """

    z_score_numerator_factor: float = 1.0
    z_score_denominator_factor: float = 0.05


@dataclass
class BULCAdvancedParams:
    """Placeholder for `BULCD-AdvancedParameters-v5`.

    Per the caller script's own comment: "transition matrices or more
    detailed outputs" for the underlying BULC (not BULC-D) engine —
    "unlikely to change... could be tweaked by an advanced user." We
    don't have this file's contents yet, so this is an opaque
    passthrough dict until we do; do not assume its shape.
    """

    raw: dict = field(default_factory=dict)


@dataclass
class ExportConfig:
    destination: Literal["asset", "drive"] = "asset"
    asset_folder: str | None = None  # legacy exportParams.assetId's containing folder
    drive_folder: str | None = None
    max_pixels: int = int(1e13)
    description_prefix: str = "bulcd"


@dataclass
class BULCDConfig:
    study_area: StudyAreaConfig
    evidence: EvidenceConfig
    schema_version: str = "1"
    reduction: ReductionConfig = field(default_factory=ReductionConfig)
    modality: ModalityConfig = field(default_factory=ModalityConfig)
    sensitivity: SensitivityConfig = field(default_factory=SensitivityConfig)
    bin_cuts: list[float] = field(
        default_factory=lambda: [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]
    )
    harmonic_constant: bool = False  # legacy harmonicConstant; purpose not yet documented upstream
    plotting_means: bool = False  # legacy plottingMeans
    verbose: bool = False
    bulc_advanced_params: BULCAdvancedParams = field(default_factory=BULCAdvancedParams)
    export: ExportConfig = field(default_factory=ExportConfig)
