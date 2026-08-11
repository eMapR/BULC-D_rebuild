"""Configuration schema for the BULC-D Python rebuild.

SKETCH / DRAFT — not wired to the engine yet (no engine exists).

This schema is a direct structural port of the legacy production
parameter file, including its discrete "expectation period vs. target
period" comparison (`EvidencePeriodConfig`/`EvidenceConfig.expectation`/
`EvidenceConfig.target` below) — restored 2026-08-11 per
docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md
after explicit direction to match the legacy GUI as closely as possible.
An earlier version of this schema (2026-07-29 through 2026-08-11)
collapsed expectation/target into one continuous per-sensor evidence
window instead, per docs/decisions/0003 (now superseded) — see 0010 for
the full reversal rationale.

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
has NOT been provided yet — `BULCAdvancedParams.raw` is a placeholder
for whatever else it turns out to hold. Its two most important known
fields (`custom_transition_matrix`, `dampening_factor`) are now typed
based on Cardille & Fortin (2016) and Willis (2022) — see CLAUDE.md
"Reference papers" and the field docstrings below — a credible
published reconstruction, not the actual source file.

Also known gap: the actual regression-fitting / R2 / residual / z-score
math lives inside `afn_organizeBULCD_Inputs` (module
`6002.A2b.3-BULCD-Module-organizeBULCD_Inputs` in `r-2903-Dev`), whose
source we don't have. This schema only captures the *parameters* that
feed that function, not its internals — though `bulcd/inputs.py`'s
`organize_inputs()` now implements a credible reconstruction of it too.

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

    # Legacy always applies afn_waterMask() unconditionally before
    # displaying/exporting finalBulcProbs (legacy/BULCD-Caller-Current.txt)
    # - we don't have that module's source, so this masks against the
    # standard public JRC Global Surface Water dataset instead (see
    # bulcd/engine.py's _water_mask()). A real, visible need: a live-EE
    # disturbance map generated 2026-07-30 (see CLAUDE.md "Disturbance
    # map") showed water bodies misclassified as "increase" (water's
    # reflectance behaves nothing like the forest-tuned harmonic model).
    # Defaults to True (matching legacy's unconditional behavior);
    # exposed as a toggle since JRC water data may not suit every AOI.
    mask_water: bool = True

    # Added 2026-07-30: a real disturbance export (cell 2F, year 2025)
    # showed false "change" above treeline - bare rock/permanent snow-ice
    # terrain that was never forest, so the forest-tuned harmonic
    # expectation model doesn't apply there at all (confirmed this isn't
    # seasonal snow contamination - narrowing the evidence DOY window to
    # peak summer did NOT remove the artifact). Uses forest_mask_asset if
    # set, else falls back to the standard public Hansen Global Forest
    # Change dataset's treecover2000 band (see bulcd/engine.py's
    # _forest_mask()) - same "standard substitute, not the legacy's real
    # source" posture as mask_water/_water_mask().
    mask_non_forest: bool = True


@dataclass
class SensorEvidenceConfig:
    """One sensor's contribution to ONE evidence period (expectation or
    target - see `EvidencePeriodConfig`).

    Mirrors one of the legacy per-sensor sub-dictionaries (`L5dictionary`,
    `L8dictionary`, `S2dictionary`, `S1dictionary`, etc.), which appear
    twice in BULCD-InputParameters-v5 - once inside
    `expectationCollectionParameters`, once inside
    `targetCollectionParameters` (legacy/BULCD-InputParameters-v5.txt
    lines 61-253) - each with its own `yearsList`/`firstDOY`/`lastDOY`/
    `CloudCoverThreshold`. `first_year`/`last_year` here is a continuous
    range standing in for the legacy's literal `yearsList` (an explicit,
    occasionally non-contiguous list of years) - every real example we
    have (BULCD-InputParameters-v5, cell 8C) uses contiguous years, so
    this is a documented, lower-complexity generalization, not a
    confirmed structural match - see
    docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md.
    """

    enabled: bool = False
    first_year: int | None = None  # None = earliest year this sensor has coverage
    last_year: int | None = None  # None = most recent available
    first_doy: int = 1  # seasonal window start, applied every year (legacy firstDOY)
    last_doy: int = 365  # seasonal window end, applied every year (legacy lastDOY)
    cloud_cover_threshold: float = 20.0  # legacy CloudCoverThreshold
    sar_polarization: SARPolarization | None = None  # S1/AL only; legacy SARValueToTrack
    # No s2_cloud_mask field - the legacy s2cloudless dictionary
    # (BULCD-InputParameters-v5) is vestigial in production's real,
    # currently-running code. CONFIRMED 2026-08-10
    # (legacy/515-gatherCollections27b.txt): the only live S2 cloud-mask
    # path for any usable year is Google Cloud Score+ (a single hardcoded
    # 0.60 threshold, no per-run configuration) - see
    # bulcd/inputs.py's `_mask_s2_clouds()`.


@dataclass
class EvidencePeriodConfig:
    """One of the legacy's two evidence periods: `expectationCollectionParameters`
    or `targetCollectionParameters` (legacy/BULCD-InputParameters-v5.txt).

    Each period gets its own per-sensor dictionary (a given sensor can be
    enabled in one period and not the other, or configured with different
    DOY/cloud-cover thresholds between the two - confirmed real in the
    legacy example, e.g. L5's CloudCoverThreshold is 45 in the
    expectation period vs. 15 in the target period).
    """

    sensors: dict[SensorCode, SensorEvidenceConfig] = field(default_factory=dict)


@dataclass
class EvidenceConfig:
    """The legacy's `expectationCollectionParameters` /
    `targetCollectionParameters` pair, restored 2026-08-11 (see
    docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md;
    docs/decisions/0003, now superseded, previously collapsed these into
    one continuous stream).

    `organize_inputs()` (bulcd/inputs.py) fits the harmonic expectation
    model against `expectation`'s assembled evidence collection, then
    scores z-scores over `target`'s assembled evidence collection only -
    the literal restoration of the legacy's one-shot expectation-vs-target
    comparison, not an indefinite continuous stream.
    """

    day_step_size: int = 4  # legacy dayStepSize - shared by both periods in every real example
    expectation: EvidencePeriodConfig = field(default_factory=EvidencePeriodConfig)
    target: EvidencePeriodConfig = field(default_factory=EvidencePeriodConfig)


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
    """Placeholder for `BULCD-AdvancedParameters-v5`, now partially typed.

    Per the caller script's own comment: "transition matrices or more
    detailed outputs" for the underlying BULC (not BULC-D) engine —
    "unlikely to change... could be tweaked by an advanced user." We
    still don't have this file's actual contents, but the Willis (2022)
    honours thesis (see CLAUDE.md "Reference papers") gives a credible,
    concretely-shaped worked example of what it holds for NBR12 — see
    the two fields below. `raw` remains an opaque passthrough for
    anything else still unknown; do not assume its shape.
    """

    # 10 bins (z-score "collection bins") x 3 decision classes
    # ([P(bin | decrease/burn), P(bin | no change), P(bin | increase/
    # regrowth)]). Hand-tuned likelihood weights, NOT empirical
    # proportions (confirmed by the thesis: rows/columns need not sum to
    # 1) - and index-specific (BAI needs an entirely different matrix
    # than NBR12 per the thesis), so there's no universal default here.
    # engine.py raises a clear error if this is None at run time, rather
    # than silently falling back to some arbitrary matrix.
    custom_transition_matrix: list[list[float]] | None = None

    # Cardille & Fortin (2016) section 4.6's dampening factor `d`:
    # dampened = d * raw_update_factor + (1 - d) / n_classes. 1.0 = no
    # dampening (raw update factors used as-is). Default is 0.5 (the
    # paper's own tested value), NOT 1.0 - a first live-EE run of this
    # codebase (2026-07-29, see CLAUDE.md "First live-EE verification")
    # found that d=1.0 produces extreme, likely-uninterpretable
    # overconfidence after many sequential Events (probabilities at the
    # edge of float64 precision), exactly the failure mode this factor
    # exists to prevent.
    dampening_factor: float = 0.5

    # NOT part of the legacy schema, NOT in Cardille & Fortin (2016) or
    # Willis (2022) - a genuine algorithmic addition (bulc.py's
    # discount()), made 2026-07-30 to address a real, empirically-found
    # failure mode: over long, mostly-stable evidence streams, many years
    # of mild "confirm normal" evidence can compound into a lead that a
    # later, genuine, sustained disturbance can't overturn even with
    # aggressive dampening (see CLAUDE.md "Major finding: long stable
    # baselines can mask real disturbance"). Powers each step's posterior
    # by this factor and renormalizes, so older evidence's influence
    # decays geometrically relative to recent evidence.
    # Defaults to 1.0 (off) - "preserve the Bayesian updating core"
    # (CLAUDE.md modernization goal) means this extension must be an
    # explicit opt-in, never a silent default. Verified empirically:
    # 0.98 fixes a previously-invisible 9-year disturbance without
    # breaking two other validated (stable / confidently-detected-fire)
    # test pixels - see CLAUDE.md "Recency weighting" for the full
    # comparison table before choosing a value.
    recency_factor: float = 1.0

    # CONFIRMED 2026-08-10 against the real BULC-Minimal-Module-107 source
    # (legacy/BULC-Minimal-Module-107.txt, alemlakes/r-2909-BULC-Releases) -
    # NOT a guess or an extension like recency_factor above. Production
    # applies a SECOND dampening step to the POSTERIOR after every single
    # Bayes update (afn_dayIRebalancingV3: posterior*posteriorLeveler +
    # posteriorMinimum, posteriorMinimum = (1-posteriorLeveler)/n_classes -
    # same formula shape as dampening_factor above, confirmed by the real
    # numbers: production's posteriorMinimum (0.0333...) = (1-0.9)/3
    # exactly). bulc.py previously only dampened the incoming update
    # factors (matching production's separate transitionLeveler step,
    # which dampening_factor above already models) and never re-dampened
    # the posterior - over many sequential steps (~350+ for a 2-year
    # evidence window), that missing regularization let posteriors
    # compound toward unbounded, uninterpretable confidence (observed:
    # probabilities differing from 1.0 by 10^-16 to 10^-112) instead of
    # staying bounded like production's. Defaults to 1.0 (no-op, exact
    # prior behavior) until empirically validated against real Earth
    # Engine and given a considered default via its own docs/decisions/
    # entry - same rollout discipline as dampening_factor's own history
    # (see docs/decisions/0004-dampening-factor-default-0.5.md).
    posterior_leveler: float = 1.0

    # CONFIRMED 2026-08-10 against the real BULC-Advanced-Parameters source
    # (6003.3c-BULC-AdvancedParameters, alemlakes/r-2903-Dev - the module
    # that actually SUPPLIES production's transitionLeveler/posteriorLeveler/
    # customTransitionMatrix, fetched after `afn_BULCD`'s own source showed
    # it doesn't build baseLandCoverImage itself). Production's starting
    # prior is NOT flat uniform - `baseLandCoverImage = ee.Image(2)`
    # ("default is 'nothing has changed'" - a hardcoded constant, not
    # derived from any AOI/run-specific data, since getBULCParameterDictionary()
    # takes no arguments at all), one-hot encoded to the "unchanged" class
    # and leveled by the SAME dampen()-shaped formula as everything else:
    # one_hot * initializingLeveler + (1-initializingLeveler)/n_classes.
    # Confirmed real value: 0.7, giving a starting prior of
    # [0.1, 0.8, 0.1] (decrease/unchanged/increase) - not this rebuild's
    # previous flat [0.333, 0.333, 0.333].
    #
    # Defaults to 0.0, NOT 1.0 like the other levelers above - at leveler=0,
    # dampen()'s formula collapses to flat uniform regardless of which
    # class was one-hot-encoded (image*0 + uniform_share), exactly
    # reproducing this rebuild's prior (pre-2026-08-10) behavior - the
    # correct "off"/backward-compatible value for THIS parameter, unlike
    # dampening_factor/posterior_leveler/recency_factor where 1.0 means
    # "pass real data through unchanged." Range is `0 <= x <= 1`
    # (inclusive of 0), not `0 < x <= 1` like the other three, for the
    # same reason.
    initializing_leveler: float = 0.0

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
