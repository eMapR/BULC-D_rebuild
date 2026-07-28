# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

This folder is the planning/reference workspace for **modernizing BULC-D**
(Bayesian Updating of Land Cover Detection), a probabilistic forest-change-
detection algorithm originally built in Google Earth Engine (GEE) JavaScript.
Early scaffold stage: the folder holds the design vision and reference
copies of the *existing* production implementation the rebuild replaces,
plus a starting `bulcd/` Python package (currently just a draft config
schema, `bulcd/config/schema.py` — no engine/algorithm code yet). Read the
reference material before proposing architecture. The target platform has
been decided — **Python + `earthengine-api`** (see "Platform decision"
below) — so scaffolding new code is unblocked, but still confirm
scope/approach with the user before large structural changes. This is a
git repo (initialized 2026-07-28); commit as normal.

## Contents

- `BULCD_Modernization_Vision.docx` — the design brief. States the goal,
  constraints, and what "done" looks like for the rebuild.
- `guiBULCD.rtf` — full source of the current production script: a ~7,500-line
  GEE JavaScript file (`theVersion = "V53e"`) that provides an interactive
  Code Editor GUI wrapping the BULC-D algorithm.
- `mckenzeBULCD.rtf` — a short (~80-line) *non-interactive* batch script
  showing how BULC-D is invoked programmatically for production exports,
  as opposed to through the GUI.
- `legacy/` — plain-text reference scripts pulled directly from the GEE
  Code Editor (not `.rtf`, pasted straight from the editor):
  - `BULCD-Caller-Current.txt` — the current (V52a) production caller,
    from `users/alemlakes/r-2909-BULC-Releases:BULC/BULC-Callers-Current/BULCD-Caller/BULCD-Caller-Current`.
    Shows the real call shape end to end.
  - `BULCD-InputParameters-v5.txt` — a real filled-out input parameter
    file, from `.../BULCD-Caller-Parameters/BULCD-InputParameters-v5`
    in the same repo. This is what `bulcd/config/schema.py` is a direct
    port of — see "Legacy parameter semantics" below.

**`.rtf`/`.docx` files are not plain text** — the Read tool will show raw
markup. Convert first: `textutil -convert txt -output out.txt in.rtf` (macOS).
Files under `legacy/` are already plain `.txt`.

## The legacy implementation (`guiBULCD.rtf`)

This is a reference artifact, not something to edit in place — the rebuild
is meant to replace it, not patch it. Its own header comment (lines 1–28)
is an accurate summary of its structure:

- **Everything lives in one script**, split into two functions:
  `afn_runBULCD_Interface()` (builds the GUI panels, ~line 83) and
  `afn_runBULCD_Code()` (runs the algorithm and renders results, ~line 7140).
- **The algorithm itself is not in this file.** It's pulled in via GEE's
  `require()` module system from a separate repo owned by `alemlakes`
  (`users/alemlakes/r-2903-Dev:BULC/...`), with a three-stage pipeline
  naming convention visible in the require paths:
  1. `organizeBULCD_Inputs` (module `6002.A2b.3-...`)
  2. `afn_BULCD` — the actual Bayesian updating engine (module `6002.B2-...`)
  3. `interpretBULCDResult` (module `6002.C2-...`)
  BULC-D itself calls a lower-level `BULC` module for the underlying Bayesian
  updating; the parameter dictionary for that is a separate require
  (`6003.3c-BULC-AdvancedParameters`) since it's rarely touched by end users.
- **UI is componentized** even though the algorithm isn't: separate widget
  modules for movie playback, "modality"/sensitivity controls, export-points,
  SAR sensor selection, and chart generation are imported from a shared
  `CommonCode2:521.InterfaceItems` library.
- Multi-sensor support (Landsat 5/7/8/9, MODIS, Sentinel-1/2), configurable
  expectation/target date ranges, and configurable reducers (NBR, SWIR, NDVI)
  are all interface-level choices layered on top of the core algorithm.

`mckenzeBULCD.rtf` shows the *other* way BULC-D gets used in practice: a
config-driven script (no GUI) that calls a higher-level `forestChangeEnsemble`
library (owned by `msime`, a different GEE user/repo than `alemlakes`) to run
BULC-D twice per AOI — once tuned for evergreen forest ("Stable") and once for
deciduous ("Seasonality") — and exports both as GEE assets. This is the
pattern closest to what a modernized, non-GUI, programmatic BULC-D should
support.

## Legacy source repos and what's still missing

`legacy/BULCD-Caller-Current.txt` (V52a, newer than `guiBULCD.rtf`'s V53e
GUI but simpler — no GUI) revealed the algorithm's actual pieces are
spread across **three separate `alemlakes` GEE repos**, which is a real
discrepancy in the legacy codebase, not a mistake in our notes:

- **`r-2903-Dev`** — the BULC-D/BULC algorithm modules themselves:
  `afn_organizeBULCD_Inputs` (`6002.A2b.3-BULCD-Module-organizeBULCD_Inputs`)
  and `afn_BULCD` (`6002.B2-BULCD-Module`). **We do not have this source.**
  This is where the actual regression-fitting / R² / residual / z-score
  math lives — the real statistical core of BULC-D. Everything in
  `bulcd/config/` only captures the *parameters* fed into these
  functions, never their internals. Do not guess at this math; get the
  source first (same method as the files already in `legacy/`: open in
  Code Editor, select-all, paste to a `.txt` file).
- **`r-2909-BULC-Releases`** — the current parameter files:
  `BULCD-InputParameters-v5` (have it), `BULCD-AdvancedParameters-v5`
  (**don't have it** — transition matrices / detailed BULC engine
  outputs, per the caller script's comment), `BULCD-AnalysisParameters-v5`
  and `BULCD-ExportParameters-v5` (don't have either — post-run
  thresholding and export band selection). Also has
  `BULC-Module-Current/BULC-Minimal-Module-107`, likely the low-level
  Bayesian updating engine BULC-D wraps — not yet fetched, matters once
  we reach `bulc.py`/`engine.py`.
- **`r-2902-Dev`** — `afn_interpretBULCDResult`
  (`6002.C2-BULCD-Module-analyzeOutputs`), the post-run analysis step
  (drop/gain probability, "was it ever," change timing). Don't have
  this source either; matters for `interpret.py`.

**Bottom line:** we can build config handling and (once written) the
sensor-data-assembly half of `inputs.py` with confidence. The
expectation-model-fitting / z-score half of `inputs.py`, all of
`bulc.py`/`engine.py`, and all of `interpret.py` need the corresponding
module source before they can be more than a stub — reconstructing that
math from field names alone risks silently violating the "preserve the
Bayesian updating core" requirement above.

## Legacy parameter semantics (from BULCD-InputParameters-v5)

Notes on *why* fields in `bulcd/config/schema.py` mean what they mean —
useful context that isn't obvious from the field names alone:

- **Expectation period vs. target period**: the legacy's core method.
  A short "expectation" window of imagery is treated as ground truth for
  "normal, undisturbed forest"; a separate short "target" window is
  compared against it. Our schema deliberately collapses both into one
  continuous per-sensor `EvidenceConfig` window — the modernization's
  primary goal — but the *concept* of an expectation model fit against
  which later imagery is scored still has to exist somewhere in the new
  engine; it just needs to work over a continuous stream instead of one
  fixed window.
- **`modalityDictionary`** (→ `ModalityConfig`): picks the seasonal-curve
  shape fit to the expectation period per pixel (constant = no
  seasonality, typically evergreen; unimodal = one seasonal peak,
  typically deciduous; bimodal/trimodal = more complex seasonal cycles;
  linear = trend only). The one real example we have sets both
  `constant` and `unimodal` to `true` simultaneously — so these read as
  candidate shapes to try/select between, not a single exclusive choice.
  Confirm against `organizeBULCD_Inputs` source once we have it.
- **`sensitivityDictionary`** (→ `SensitivityConfig`): scales
  "observed minus expected" into a z-score
  (`ZScoreNumeratorFactor`/`ZScoreDenominatorFactor`). Exact formula is
  in the missing `organizeBULCD_Inputs` source.
- **`binCuts`**: BULC's core Bayesian updating step operates on discrete
  states, not continuous z-scores — this is where the continuous z-score
  gets discretized before it reaches the actual updater.
- **Per-sensor dictionaries** (`L5dictionary`, `L8dictionary`,
  `S2dictionary`, `S1dictionary`, etc.): each enabled sensor gets its own
  `yearsList`/`firstDOY`/`lastDOY`/`CloudCoverThreshold`, because
  different sensors have different noise characteristics and archive
  availability. Sentinel-1 swaps `CloudCoverThreshold` for
  `SARValueToTrack` (polarization: HH/HV/VH/VV) since radar isn't
  affected by cloud. Sentinel-2 additionally nests an `s2cloudless`
  block (see [Google's s2cloudless tutorial](https://developers.google.com/earth-engine/tutorials/community/sentinel-2-s2cloudless)).
- **`datasetSelection`** sensor codes: `L5`/`L7`/`L8`/`L9` = Landsat,
  `MO` = MODIS, `S2`/`S1` = Sentinel-2/1, `AL` = ALOS (SAR), `NI` =
  NICFI (Planet), `DW` = Dynamic World. The last three aren't mentioned
  in the Vision doc or `guiBULCD.rtf`'s header comment — treat as
  unconfirmed/experimental until we learn more.

## Modernization goals (from the Vision doc — treat as requirements, not suggestions)

- **Preserve the Bayesian updating core** — this is not a rewrite of the
  method, just the software and data-usage strategy around it.
- **Use the full Landsat archive (1984–present) as continuous evidence**,
  instead of the legacy model's discrete "expectation period vs. target
  period" comparison. This is the primary objective, not a nice-to-have.
- **Separate the algorithm from the GUI.** The legacy script's biggest
  structural problem is that `afn_runBULCD_Interface` and `afn_runBULCD_Code`
  are entangled — the engine must become callable programmatically without
  a Code Editor UI attached (`mckenzeBULCD.rtf`'s style, not `guiBULCD.rtf`'s).
- **Expose intermediate probability/uncertainty surfaces**, not just a final
  change map — current opacity in the legacy tool is called out as a problem.
- **Design for extensibility** to new sensors/algorithm variants without
  reworking the core.

## Platform decision

Decided (2026-07-28): the rebuild targets **Python + `earthengine-api`**,
not GEE JavaScript. This matches a prior note from a meeting with Robert
(the original BULC-D author) about wanting a "BULC-D python tool." The
algorithm still executes server-side on Earth Engine (it's Python code
building an EE computation graph, same as `gee_export/export_timeseries.py`
in the sibling GeoTimeSeries project) — this is a client-language choice,
not a move off Earth Engine.

## Environment

- Conda env: `bulcd` (`environment.yml`; python=3.11, pyyaml, pytest,
  pip-installed `earthengine-api`).
- Package is pip-installed editable into that env (`pip install -e .`,
  via `pyproject.toml`) so `bulcd.*` imports resolve without PYTHONPATH
  hacks.
- Run tests: `conda run -n bulcd pytest tests/ -v`.

## Current code state

- `bulcd/config/schema.py` — typed config dataclasses (`BULCDConfig` and
  its sub-configs: `StudyAreaConfig`, `EvidenceConfig`/`SensorEvidenceConfig`
  (continuous per-sensor evidence window, replacing the legacy
  expectation/target split), `ReductionConfig`, `ModalityConfig`,
  `SensitivityConfig`, `BULCAdvancedParams` (placeholder — see "what's
  still missing" above), `ExportConfig`). Each field's docstring cites
  which legacy field it replaces and why; see the module docstring for
  full provenance.
- `bulcd/config/loader.py` — `load_config(path) -> BULCDConfig`. Parses
  YAML, validates required fields and enum-like values section by
  section (including cross-field checks like "exactly one of
  `aoi_asset`/`aoi_coordinates`", "`sar_polarization` only valid for
  S1/AL"), raises `ConfigError` with a specific message rather than
  silently defaulting — a bad config here means a real, billed Earth
  Engine export runs against the wrong AOI/dates. 12 passing tests in
  `tests/test_config_loader.py`; `configs/example.yaml` is a filled-out
  example.
- No engine/algorithm code yet (`inputs.py`, `bulc.py`, `engine.py`,
  `interpret.py`, `export.py`, `cli.py`, and the `sensors/` submodule
  from the earlier package-structure draft are all still unwritten) —
  see "Legacy source repos and what's still missing" above for why
  `inputs.py`/`bulc.py`/`engine.py`/`interpret.py` can only be partially
  written until we have more legacy source.
