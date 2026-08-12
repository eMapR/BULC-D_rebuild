# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project documentation map

This project's context is split across three places, each with a different job:

- **`CLAUDE.md`** (this file) — stable facts: what the project is, how the
  legacy system works, what's implemented today, and requirements to hold
  to. Read this first.
- **`docs/decisions/`** — one file per significant "why did we choose X
  over Y" decision (context / decision / consequences). Read these when
  you need to know *why* a default or design choice is what it is, or
  before proposing to change one.
- **`docs/findings.md`** — a dated, chronological lab notebook of
  validation runs, experiments, and bugs found — the play-by-play behind
  the decisions above. Read this for the evidence behind a decision, or
  to avoid re-discovering something already tested.

When something new happens: a **decision** (chose X over Y, for reason Z)
gets a new file in `docs/decisions/`; an **experiment or validation
result** gets appended to `docs/findings.md`; a change to **current
implemented state** updates the relevant section of this file.

## What this is

This folder is the planning/reference workspace **and** the actively
developed Python implementation for **modernizing BULC-D** (Bayesian
Updating of Land Cover Detection), a probabilistic forest-change-
detection algorithm originally built in Google Earth Engine (GEE)
JavaScript. It holds the design vision, reference copies of the
*existing* production implementation the rebuild replaces, and the
`bulcd/` Python package itself — config, evidence assembly, the Bayesian
engine, interpretation, and export (see "Current code state" below for
exactly what's implemented). Read the reference material before
proposing architecture changes. The target platform is **Python +
`earthengine-api`** (see `docs/decisions/0001-python-earthengine-platform.md`)
— confirm scope/approach with the user before large structural changes.
This is a git repo; commit as normal.

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
- Two published-paper PDFs at the repo root — see "Reference papers"
  below for what each contributes:
  - `1-s2.0-S0034425716303248-main.pdf` — Cardille & Fortin (2016),
    *Remote Sensing of Environment* 186. The original BULC (not BULC-D)
    paper; gives the actual low-level Bayesian updating math.
  - `2022_Honours_Project_Written_Report__Eidan_Willis__compressed_.pdf`
    — Eidan Willis's McGill honours thesis on BULC-**D** specifically
    (NBR12 vs. BAI burn-index comparison). Gives the z-score/harmonic
    /transition-matrix math that `guiBULCD.rtf`'s missing
    `organizeBULCD_Inputs` source would otherwise be the only source for.
  - Both are scanned/text PDFs; the `Read` tool needs `poppler` for its
    normal page-render path. If unavailable, extract text with `pypdf`
    and render specific figure pages to PNG with `pymupdf`
    (`pip install pypdf pymupdf`) to read as images.

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

## Legacy source repos — most of the core algorithm is now fetched

`legacy/BULCD-Caller-Current.txt` (V52a, newer than `guiBULCD.rtf`'s V53e
GUI but simpler — no GUI) revealed the algorithm's actual pieces are
spread across **three separate `alemlakes` GEE repos**, plus shared
library code in `CommonCode2` — a real discrepancy in the legacy
codebase, not a mistake in our notes. As of 2026-08-10, most of the
files that matter for the Bayesian core have been fetched (see
`docs/findings.md` for the full narrative of how each was found and what
each revealed):

- **`r-2903-Dev`** — the BULC-D/BULC algorithm modules. **All fetched**:
  `afn_organizeBULCD_Inputs` (`6002.A2b.3-BULCD-Module-organizeBULCD_Inputs`,
  `legacy/6002.A2b.3-BULCD-Module-organizeBULCD_Inputs.txt`) and
  `afn_BULCD` (`6002.B2-BULCD-Module`, `legacy/6002.B2-BULCD-Module.txt`)
  — confirmed and fixed the z-score denominator/`residual_stddev`
  formulas (see `bulcd/inputs.py`'s docstring); `6003.3c-BULC-AdvancedParameters`
  (`getBULCParameterDictionary()`, `legacy/6003.3c-BULC-AdvancedParameters.txt`)
  — the real source of the transition matrix, all three levelers, and
  `baseLandCoverImage`.
- **`CommonCode2`** (shared library, not one of the three
  `alemlakes`-owned algorithm repos, but where the actual math lives for
  several pieces) — also fetched: `515-gatherCollections27b`
  (`515.ImageCollectionFilteringAndGathering/515-gatherCollections27b`,
  `legacy/515-gatherCollections27b.txt`) — confirmed `dayStepSize` is a
  temporal binning window (see `docs/decisions/0008`), implemented;
  `502.7-1h5-HarmonicFunctions` (`/502.7-Harmonics/502.7-1h5-HarmonicFunctions`,
  `legacy/502.7-1h5-HarmonicFunctions.txt`) — confirmed the
  modality-resolution logic is additive, not priority-based (CONFIRMED
  WRONG in `_select_modality_regressors()`, not yet fixed), and the real
  (adjusted) R² formula.
- **`r-2909-BULC-Releases`** — the current parameter files:
  `BULCD-InputParameters-v5` (have it). `BULCD-AdvancedParameters-v5`/
  `BULCD-AnalysisParameters-v5`/`BULCD-ExportParameters-v5` themselves
  still not individually fetched, but `BULCD-AdvancedParameters-v5`'s
  real content is now effectively known via `6003.3c-BULC-AdvancedParameters`
  above (the actual function that supplies it). `BULC-Module-Current/BULC-Minimal-Module-107`
  — fetched 2026-08-10, `legacy/BULC-Minimal-Module-107.txt`. Confirmed
  production dampening uses three separate "levelers" plus two minimum
  floors, not one scalar — all three now implemented
  (`transitionLeveler`/`posteriorLeveler`/`initializingLeveler`, see
  `docs/decisions/0007`).
- **`r-2902-Dev`** — `afn_interpretBULCDResult`
  (`6002.C2-BULCD-Module-analyzeOutputs`,
  `legacy/6002.C2-BULCD-Module-analyzeOutputs.txt`), the post-run
  analysis step — **fetched 2026-08-10**. Revealed `interpret.py`'s
  `year_of_change()` likely uses the wrong definition entirely
  (production's real "when did it change" is the FIRST threshold
  crossing, no unbroken-run requirement) — a plausible real explanation
  for the documented 12-year lag finding. Not yet fixed; still missing
  `BULCD-AnalysisParameters-v5` for the exact
  `dropThresholdToDenoteChange`/mean-threshold values this module also
  depends on.

Still genuinely unfetched: the full `BULCD-AnalysisParameters-v5`/
`BULCD-ExportParameters-v5` parameter files (post-run thresholding,
export band selection).

**Bottom line:** config handling and the sensor-data-assembly half of
`inputs.py` are built with confidence. `bulc.py`'s core dampening
mechanism is now confirmed directly against the real
`BULC-Minimal-Module-107` source (fetched 2026-08-10 — see "Current
code state" below), not just the paper reconstruction. The
expectation-model-fitting / z-score half of `inputs.py`, `engine.py`'s
binning/transition-matrix logic, and `interpret.py` are still
implemented against the "Reference papers" reconstruction below —
published, citable descriptions of the actual method, not a guess from
field names — but are **not** a substitute for the real
`organizeBULCD_Inputs` source (still missing) if exact production
behavior ever needs to match bit-for-bit (precise bin cut-points, the
`initializingLeveler`/`baseLandCoverImage` starting-prior mechanism).
See "Current code state" below for exactly what's implemented vs. still
assumption-flagged vs. confirmed against live Earth Engine or the real
GUI Console output.

## Reference papers — real math for the Bayesian core

Two papers (see "Contents") together cover both layers of BULC-D that
would otherwise be unwritten stubs given the missing source above:

**Cardille & Fortin 2016 (the original BULC paper)** describes the
low-level Bayesian engine BULC-D wraps (confirmed to correspond to
`BULC-Minimal-Module-107`, fetched 2026-08-10 — see "Current code
state") — this is `bulc.py`/`engine.py`
territory:
- An **"update table"** is built between consecutive classified images
  ("Events") by cross-tabulating Event *i* against Event *i+1* like a
  confusion matrix, then reading it as conditional probabilities:
  `P(class c2 at i+1 | class c1 at i) = P(c2,i+1 and c1,i) / P(c1,i)`
  — algebraically this is just Producer's Accuracy per class.
- Those conditional probabilities feed the **standard Bayes update**
  applied per pixel, per class, at every new Event:
  `P(c1, i+1 | c2,i+1) = [P(c2,i+1|c1,i) * P(c1,i)] / Σ_c[P(c,i+1|c,i) * P(c,i)]`
  — the posterior at step *i* becomes the prior for step *i+1*.
- A pixel's class at any time step is just `argmax` over its current
  probability vector.
- A **dampening factor** `0 < d ≤ 1` can flatten update strength:
  `dampened = d * raw_update_factor + (1 - d) / n_classes` — used when
  classifications agree suspiciously well and you don't want to overreact
  to any single Event (the paper used `d = 0.5`; see
  `docs/decisions/0004-dampening-factor-default-0.5.md`).
- Missing data at a time step = leave that pixel's probabilities
  unchanged (don't zero anything out).

**Willis honours thesis 2022 (BULC-D specifically, NBR12 vs. BAI)**
describes the layer that's actually novel to "-D": how a continuous
burn-index value (not a full classified image) gets turned into the
conditional-probability input for the same Bayes formula above. This is
`organize_inputs()`/the z-score half of `inputs.py`, plus the part of
`bulc.py` that differs from classic BULC:
- **Expectation-year fit**: rather than a flat mean, BULC-D fits a
  **harmonic regression** to the a priori ("expectation") year's index
  values per pixel: `index_t = β0 + β1*t + β2*cos(2πωt) + β3*sin(2πωt) + e_t`.
  Willis's own thesis found a simplified 2-term version
  (`index_t = β0 + β3*sin(2πωt)`) fit better in their tests — **but
  real production GUI Console output confirmed 2026-08-10 that unimodal
  actually uses the full 3-term first-order harmonic
  (`constant + cos + sin`)**, not the simplified 2-term version; see
  `docs/findings.md`'s "Real production BULC-D parameters" entry. `bulcd/inputs.py`
  now implements the confirmed 3-term version.
- **Z-score**: `(observed_index - fitted_expectation) / residual_stddev`,
  the standard definition — confirms `ZScoreNumeratorFactor`/
  `ZScoreDenominatorFactor` are just scaling knobs on this same formula.
- **10 discrete "collection bins"** (→ `binCuts`) by z-score, roughly:
  bins 5–6 = within ±1 std ("no change"); bins 1–4 = increasingly large
  drops (1–3 = most extreme); bins 7–10 = increasingly large increases
  (bin 10 as a catch-all for atmospheric-interference outliers, weighted
  low so it doesn't dominate). Exact cut-points weren't given as a
  formula in the thesis — confirmed to match `guiBULCD.rtf`'s hardcoded
  `binCuts = [-2,-1.5,-1,-0.5,0,0.5,1,1.5,2]` (line 5965), already
  `schema.py`'s default.
- **The key structural difference from classic BULC**: instead of a
  *data-derived* confusion matrix between two classified Events, BULC-D
  uses a **fixed, hand-tuned "custom transition matrix"** — a 10×3
  lookup (10 bins × 3 decision classes: index-drop/burn, no-change,
  index-increase/regrowth) supplied as a literal parameter, playing the
  same conditional-probability role in the Bayes formula above. The
  thesis gives its own worked NBR12 example verbatim (not the shipped
  default, but a concrete, correctly-shaped real one — used throughout
  this project's early validation, see `docs/findings.md`):
  ```
  var customTransitionMatrix = [
   [0.16,0.11,0.02],   // bin 1  (most extreme drop)
   [0.14,0.07,0.02],   // bin 2
   [0.07,0.12,0.02],   // bin 3
   [0.03,0.16,0.02],   // bin 4
   [0.015,0.2,0.01],   // bin 5
   [0.015,0.195,0.025],// bin 6
   [0.02,0.1255,0.07], // bin 7
   [0.02,0.07,0.11],   // bin 8
   [0.02,0.05,0.12],   // bin 9
   [0.02,0.02,0.08]    // bin 10 (deliberately down-weighted — outlier bin)
  ]
  ```
  Columns are `[P(bin | Drop/burn), P(bin | No change), P(bin | Increase/regrowth)]`.
  Note this does *not* sum to 1 across rows or columns — unlike classic
  BULC's confusion-matrix-derived update table, these are hand-picked
  likelihood weights, not empirical proportions. **A real production
  matrix (cell 8C, read live from the GUI Console, genuinely different
  from this thesis example and with rows that do sum to ~0.98-0.99) was
  obtained 2026-08-10 — see `docs/findings.md`'s "Real production BULC-D
  parameters" entry and `configs/cell_8c_comparison.yaml`.**
- BAI needed its own separately hand-tuned transition matrix because it
  inverts NBR12's sign convention (BAI *increases* on burn) and spans a
  very different numeric range — reinforcing that this matrix is
  index-specific, not universal, and should be a configurable parameter
  per burn index rather than hardcoded.

## Legacy parameter semantics (from BULCD-InputParameters-v5)

Notes on *why* fields in `bulcd/config/schema.py` mean what they mean —
useful context that isn't obvious from the field names alone:

- **Expectation period vs. target period**: the legacy's core method
  treats a short "expectation" window as ground truth for "normal,
  undisturbed forest" and a separate "target" window as what's compared
  against it. This rebuild's schema now restores that exact split —
  `EvidenceConfig.expectation`/`EvidenceConfig.target`, each an
  `EvidencePeriodConfig` (`bulcd/config/schema.py`) — after briefly
  replacing it with a continuous evidence stream + single global baseline
  window (`docs/decisions/0003`, now superseded). See
  `docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md`
  for the full reversal: direction from the user's boss to match the
  legacy GUI's structure as closely as possible, not just its formulas.
  `organize_inputs()` fits the harmonic model against `expectation`'s
  collection and scores z-scores over `target`'s collection only.
- **`modalityDictionary`** (→ `ModalityConfig`): picks the seasonal-curve
  shape fit to the expectation period per pixel (constant = no
  seasonality, typically evergreen; unimodal = one seasonal peak,
  typically deciduous; bimodal/trimodal = more complex seasonal cycles;
  linear = trend only). The one real example we have sets both
  `constant` and `unimodal` to `true` simultaneously — so these read as
  candidate shapes to try/select between, not a single exclusive choice.
  `bulcd/inputs.py`'s `_select_modality_regressors()` resolves this as
  "richest enabled shape wins" (trimodal > bimodal > unimodal > linear >
  constant) — a documented assumption, still worth confirming against
  `organizeBULCD_Inputs` source once we have it. Unimodal's own regressor
  set (`["constant", "cos", "sin"]`) is confirmed, not assumed — see
  "Reference papers" above.
- **`sensitivityDictionary`** (→ `SensitivityConfig`): scales
  "observed minus expected" into a z-score
  (`ZScoreNumeratorFactor`/`ZScoreDenominatorFactor`). Implemented in
  `bulcd/inputs.py`'s `_zscore_image()` as
  `numerator_factor * (observed - fitted) / (residual_stddev + denominator_factor)`
  — reading the denominator factor as a divide-by-zero-stabilizing
  epsilon (documented assumption; the exact formula isn't given in
  either reference paper, and still isn't confirmed against the real
  `organizeBULCD_Inputs` source).
- **`binCuts`**: BULC's core Bayesian updating step operates on discrete
  states, not continuous z-scores — this is where the continuous z-score
  gets discretized before it reaches the actual updater. Implemented in
  `bulcd/engine.py`'s `_bin_zscore()` (chained greater-than comparisons)
  and `_bin_to_update_factors()` (looks the resulting bin up against
  `custom_transition_matrix`'s rows).
- **Per-sensor dictionaries** (`L5dictionary`, `L8dictionary`,
  `S2dictionary`, `S1dictionary`, etc.): each enabled sensor gets its own
  `yearsList`/`firstDOY`/`lastDOY`/`CloudCoverThreshold`, because
  different sensors have different noise characteristics and archive
  availability. Sentinel-1 swaps `CloudCoverThreshold` for
  `SARValueToTrack` (polarization: HH/HV/VH/VV) since radar isn't
  affected by cloud. Sentinel-2 additionally nests an `s2cloudless`
  block (see [Google's s2cloudless tutorial](https://developers.google.com/earth-engine/tutorials/community/sentinel-2-s2cloudless))
  in the legacy `BULCD-InputParameters-v5` file — **CONFIRMED 2026-08-10
  as vestigial**: `515-gatherCollections27b`'s real, currently-running
  source shows Google Cloud Score+ as the only live S2 cloud-mask path
  for any usable year, not s2cloudless at all (see "Current code state"
  below) — `bulcd/config/schema.py` has no `s2_cloud_mask` field to match.
- **`datasetSelection`** sensor codes: `L5`/`L7`/`L8`/`L9` = Landsat,
  `MO` = MODIS, `S2`/`S1` = Sentinel-2/1, `AL` = ALOS (SAR), `NI` =
  NICFI (Planet), `DW` = Dynamic World. The last three aren't mentioned
  in the Vision doc or `guiBULCD.rtf`'s header comment — treat as
  unconfirmed/experimental until we learn more.

## Modernization goals (from the Vision doc — treat as requirements, not suggestions)

- **Preserve the Bayesian updating core** — this is not a rewrite of the
  method, just the software and data-usage strategy around it.
- ~~**Use the full Landsat archive (1984–present) as continuous
  evidence**, instead of the legacy model's discrete "expectation period
  vs. target period" comparison. This is the primary objective, not a
  nice-to-have.~~ **Superseded 2026-08-11** — explicit direction from the
  user's boss to match the legacy GUI's structure as closely as possible
  overrides this goal; the discrete expectation/target comparison is
  restored instead. See
  `docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md`.
- **Separate the algorithm from the GUI.** The legacy script's biggest
  structural problem is that `afn_runBULCD_Interface` and `afn_runBULCD_Code`
  are entangled — the engine must become callable programmatically without
  a Code Editor UI attached (`mckenzeBULCD.rtf`'s style, not `guiBULCD.rtf`'s).
- **Expose intermediate probability/uncertainty surfaces**, not just a final
  change map — current opacity in the legacy tool is called out as a problem.
- **Design for extensibility** to new sensors/algorithm variants without
  reworking the core.

## Platform and infrastructure decisions

- **Language/platform:** Python + `earthengine-api`, not GEE JavaScript
  — see `docs/decisions/0001-python-earthengine-platform.md`.
- **GEE Cloud project:** `bulcd-python-rebuild`, a dedicated project (not
  the sibling GeoTimeSeries project's `eastern-cascades-bugnet`) — see
  `docs/decisions/0002-dedicated-gee-cloud-project.md`.

## Environment

- Conda env: `bulcd` (`environment.yml`; python=3.11, pyyaml, pytest,
  pip-installed `earthengine-api`).
- Package is pip-installed editable into that env (`pip install -e .`,
  via `pyproject.toml`) so `bulcd.*` imports resolve without PYTHONPATH
  hacks.
- Run tests: `conda run -n bulcd pytest tests/ -v`.

## Current code state

- `bulcd/config/schema.py` — typed config dataclasses (`BULCDConfig` and
  its sub-configs: `StudyAreaConfig`, `EvidenceConfig` (holds
  `expectation`/`target`, each an `EvidencePeriodConfig` wrapping
  `dict[SensorCode, SensorEvidenceConfig]` — the restored legacy
  expectation/target period split, see
  `docs/decisions/0010-restore-expectation-target-split-for-gui-parity.md`;
  `docs/decisions/0003`, now superseded, previously collapsed these into
  one continuous stream + a global baseline window),
  `ReductionConfig`, `ModalityConfig`, `SensitivityConfig`,
  `BULCAdvancedParams` (now partially typed: `custom_transition_matrix`,
  `dampening_factor`, `recency_factor` — see
  `docs/decisions/0005-recency-weighting-extension.md`, NOT from the
  legacy schema, defaults off — plus an opaque `raw` dict for whatever
  else `BULCD-AdvancedParameters-v5` turns out to hold), `ExportConfig`).
  Each field's docstring cites which legacy field it replaces and why;
  see the module docstring for full provenance.
- `bulcd/config/loader.py` — `load_config(path) -> BULCDConfig`. Parses
  YAML, validates required fields and enum-like values section by
  section (including cross-field checks like "exactly one of
  `aoi_asset`/`aoi_coordinates`", "`sar_polarization` only valid for
  S1/AL", `evidence.expectation`/`evidence.target` each required and each
  needing at least one enabled sensor, `custom_transition_matrix` being
  10×3, `bin_cuts` length + 1 matching the transition matrix's row count,
  `dampening_factor` in `(0, 1]`), raises `ConfigError` with a specific
  message rather than silently defaulting — a bad config here means a
  real, billed Earth Engine export runs against the wrong AOI/dates. 24
  passing tests in `tests/test_config_loader.py`; `configs/example.yaml` is a filled-out
  example (including a transcription of Willis (2022)'s worked NBR12
  transition matrix, clearly commented as an example, not a shipped
  default). `configs/cell_8c_comparison.yaml` is the first config
  actually driving a real run rather than a debug script's hardcoded
  Python config — see `docs/findings.md`'s "Legacy-GUI parameter
  matching" and "Real production BULC-D parameters" entries.
- `bulcd/inputs.py` — PARTIAL. Real, working: `resolve_study_area()` and
  `assemble_evidence_collection(config, period)` (harmonized Landsat 5/7/8/9
  Collection 2 Level 2 SR, NBR/SWIR/NDVI reduction, per-sensor continuous
  year range + seasonal DOY filter via `ee.Filter.calendarRange`, merged
  + `.toFloat()`-cast + time-sorted, for ONE `EvidencePeriodConfig` at a
  time — called once for `config.evidence.expectation`, once for
  `config.evidence.target`), PLUS Sentinel-2
  (`COPERNICUS/S2_SR_HARMONIZED`). **Cloud masking corrected 2026-08-10**
  against the real `515-gatherCollections27b` source, confirmed wrong for
  every sensor: L5/L7 and L8/L9 now use two genuinely different QA_PIXEL
  bit checks (`_mask_landsat_clouds_l5_l7()` = bits 3+4 only;
  `_mask_landsat_clouds_l8_l9()` = bits 0-4 plus a separate `QA_RADSAT`
  saturation mask) instead of one shared function; S2 now uses Google
  Cloud Score+ (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`, `cs >= 0.60`,
  confirmed as production's only real live path) instead of the
  s2cloudless community recipe first implemented — `S2CloudMaskConfig`/
  `s2_cloud_mask` removed entirely (the legacy config's `s2cloudless`
  block is vestigial in production's real running code). VALIDATED
  against real Earth Engine: correct fixes across all three of cell 8C's
  enabled sensors, but classification moved only ~0.03 percentage
  points — inert, like most fixes after `dayStepSize` (see
  `docs/findings.md` "Cloud masking was wrong for every sensor"). Sentinel-1,
  MODIS, ALOS/NICFI/Dynamic World still raise `NotImplementedError` if
  enabled. `day_step_size` is now REAL
  (2026-08-10, see `docs/decisions/0008`): its source
  (`afn_gatherCollectionsAndReduce`) confirmed it's a temporal
  binning/aggregation window, not a sampling parameter — production
  medians together every image from every enabled sensor landing in each
  `day_step_size`-day bin into exactly ONE "Event," not one Event per raw
  image. `_evidence_date_and_doy_bounds()`/`_bin_evidence_by_day_step()`
  implement this (via `ee.Join.saveAll()` — a naive per-bin
  `.filterDate()` inside `.map()` hit "User memory limit exceeded" even
  for a single-point query). VALIDATED: the first of four confirmed
  fixes in this investigation that actually moved the classification
  (not just left it unchanged) — `unchanged` roughly tripled at 2 of 3
  test points. `organize_inputs()` (the expectation-regression/R2/
  residuals/z-score step) — its real source (`organizeBULCD_Inputs`) was
  fetched 2026-08-10 (see `docs/findings.md` "initializing_leveler, real
  organizeBULCD_Inputs source, z-score fixes"). CONFIRMED and fixed
  against it: `_zscore_image()`'s denominator is
  `max(residual_stddev, denominator_factor)` clamped to `[-10, 10]` (not
  an additive epsilon); `residual_stddev` is a plain `n-1` sample
  standard deviation of residuals (not a regression
  residual-standard-error). Also confirmed: the legacy's discrete
  expectation/target split is real in production — this rebuild briefly
  diverged from it (continuous full-stream scoring, `docs/decisions/0003`)
  before restoring it exactly (`docs/decisions/0010`, 2026-08-11, per
  explicit direction to match the GUI's structure). Modality-priority
  resolution FIXED (2026-08-10): the real source
  (`502.7-1h5-HarmonicFunctions`) confirmed production is ADDITIVE (every
  true `ModalityConfig` flag's terms concatenate), not "richest shape
  wins" as `_select_modality_regressors()` previously implemented — now
  matches. R2 also FIXED to the confirmed adjusted formula
  (dof-corrected residual variance over sample variance of y, reusing
  the regression reducer's own `residuals` output directly). VALIDATED
  against real Earth Engine: both fixes left cell 8C's classification
  identical to the decimal (R2 is diagnostic-only and never feeds the
  Bayesian engine; cell 8C's config only ever exercises the
  unimodal-alone regressor path regardless) — real, correct fixes,
  confirmed classification-inert for this specific config. Fits a
  harmonic regression per pixel over the expectation period's collection
  (`ee.Reducer.linearRegression`, continuous fractional-year time axis
  rather than day-of-year, so multi-year expectation windows don't wrap
  around at year boundaries), then scores ONLY the target period's
  collection into z-scores (restored 2026-08-11, `docs/decisions/0010` —
  previously scored the *entire* evidence stream, baseline included, as
  a continuous z-score `ee.ImageCollection`). VERIFIED against real Earth
  Engine at a single test pixel and at cell 8C under the prior
  continuous-stream design — not yet revalidated under the restored
  split, and not a substitute for broader validation across more
  pixels/AOIs/conditions.
- `bulcd/bulc.py` — NEW, real code: the generic, index/sensor-agnostic
  Bayesian updating engine (`dampen()`, `bayes_update()`, `run_bulc()`),
  a direct implementation of Cardille & Fortin (2016) Eq. 1/2 and its
  dampening factor, PLUS `discount()` — a `recency_factor` extension
  (see `docs/decisions/0005-recency-weighting-extension.md`), off by
  default. Mirrors the legacy's actual module split — this is
  `BULC-Minimal-Module-107`'s counterpart (source now obtained, saved to
  `legacy/BULC-Minimal-Module-107.txt`); `afn_BULCD`'s counterpart is
  `engine.py` below. `dampen()` is now reused for TWO steps, matching the
  real source exactly (confirmed 2026-08-10, see
  `docs/decisions/0007-posterior-leveler-regularization.md`): dampening
  the incoming update factors (`dampening_factor`, matches production's
  `transitionLeveler`) AND a second, separate dampening of the posterior
  after every Bayes update (new `posterior_leveler` parameter, matches
  production's `posteriorLeveler`) — the latter was completely missing
  before and confirmed to be the cause of a real runaway-overconfidence
  bug found via a live GUI-vs-rebuild comparison (probabilities at the
  edge of float64 precision). `posterior_leveler` defaults to `1.0`
  (no-op) pending a considered default, same rollout as
  `dampening_factor`'s own history. `initializingLeveler`/
  `baseLandCoverImage` also now CONFIRMED and implemented (engine.py
  below) — production's real value is a hardcoded, run-independent
  constant (`ee.Image(2)`, "default is 'nothing has changed'"), not a
  real per-AOI land-cover classification. VALIDATED but with a
  surprising null result: at `posterior_leveler=0.9`, any single step's
  influence (including the initial prior) decays by `~0.9^N` per
  subsequent step — for a ~350-step sequence that's washed out almost
  immediately, so `initializing_leveler` provably cannot move the final
  classification for evidence windows this long. See
  `docs/findings.md`'s "initializing_leveler, real organizeBULCD_Inputs
  source, z-score fixes" entry. `BulcResult.probability_stack`/`classification_stack` are
  `ee.ImageCollection` rather than the legacy's single flattened
  multi-band `Image` fields — a deliberate divergence, more directly
  useful for "expose intermediate probability/uncertainty surfaces"
  (Vision doc goal). VERIFIED against real Earth Engine at four real
  test pixels (see `docs/findings.md`).
  **MAJOR BUG FIXED 2026-08-10** (see
  `docs/decisions/0009-masking-bugs-resolve-the-classification-gap.md`):
  `bayes_update()` used to call `.unmask(prior)` immediately, before
  `_step()`'s `posterior_leveler` dampening ran — so a no-data step's
  already-restored-to-prior posterior still got pulled partway toward
  uniform instead of being a true no-op. Confirmed against the real
  `BULC-Minimal-Module-107` source: production rebalances the masked,
  valid-pixel-only slice FIRST, then merges onto the untouched prior —
  rebalance-then-merge, not merge-then-rebalance. Fixed by having
  `bayes_update()` stay masked and moving the single `.unmask(prior)`
  call to the end of `_step()`, after `dampen()`/`discount()` (both
  mask-preserving arithmetic, so correct no-ops on masked steps).
- `bulcd/engine.py` — NEW, real code: the `afn_BULCD` equivalent, gluing
  `organize_inputs()`'s z-score stream to `bulc.py`'s generic engine via
  binning (`_bin_zscore`) and a transition-matrix lookup
  (`_bin_to_update_factors`), passing `dampening_factor`/
  `recency_factor` through to `bulc.run_bulc()`, and applying
  `_water_mask()`/`_forest_mask()` to the final output by default
  (`StudyAreaConfig.mask_water`/`mask_non_forest` — see
  `docs/decisions/0006-standard-dataset-masks.md`; verified-partial
  fixes, not complete ones). `run_bulcd()` fails loudly up front (before
  touching `ee.*` at all) if `custom_transition_matrix` isn't
  configured, or if its row count doesn't match `bin_cuts`.
  **MAJOR BUG FIXED 2026-08-10** (see
  `docs/decisions/0009-masking-bugs-resolve-the-classification-gap.md`):
  `_bin_to_update_factors()`'s `.where()` chain didn't propagate the
  input bin image's mask, so every masked/no-data day was silently
  injected into the Bayesian fold as maximum-confidence "decrease"
  evidence (bin 1's matrix row) instead of a true no-op — confirmed via
  a full step-by-step trace of cell 8C's Bayesian fold, hand-simulated
  in Python, which isolated an entire session-long classification
  discrepancy (7 other confirmed, validated, but largely inert fixes) to
  this one mask-propagation bug plus the `bulc.py` one above. Fixed by
  appending `.updateMask(binned_image.mask())` to the return value.
  VALIDATED against real Earth Engine: both fixes together flipped cell
  8C's classification from `decrease`-dominant (~82–91%) to
  `unchanged`-dominant (~83–91%) at all three test points, matching the
  GUI's expected render for the first time in this investigation. Public
  helper `study_area_mask(config)` returns the combined water+forest
  mask for callers that bypass `run_bulcd()`'s automatic masking (e.g.
  code reading `classification_stack`/`lof_zscore` directly — this must
  be called explicitly, it is not automatic outside
  `final_probabilities`). VERIFIED against real Earth Engine at four
  real test pixels plus multiple full-AOI maps. `scripts/debug_run.py`,
  `scripts/debug_bb_complex_fire.py`, `scripts/debug_long_baseline_disturbance.py`,
  `scripts/debug_disturbance_map.py`, `scripts/debug_grid_cell_map.py`,
  `scripts/debug_year_of_change_map.py`, and `scripts/run_cell_8c_comparison.py`
  are the actual runnable entry points today — hardcoded test AOIs/configs
  (or, for the last one, `configs/cell_8c_comparison.yaml`), cheap
  preview renders (`.getInfo()`/`.getThumbURL()`), not a real CLI
  (`bulcd/cli.py` doesn't exist yet). `scripts/export_year_disturbance_map.py`
  and `scripts/export_cell_8c_comparison.py` (new 2026-08-11) are the two
  real, non-preview `Export.image.toAsset()` entry points.
- `bulcd/interpret.py` — partial: `year_of_change()`/
  `disturbance_mask_for_year()` (the "when did this pixel change"
  question) plus `zscore_anomaly_mask_for_year()` (the "was this pixel
  abnormal in year Y" question, read straight from the z-score stream
  with no Bayesian accumulation) — a reconstruction, not a port, of the
  still-missing `afn_interpretBULCDResult`'s "when did it change"
  question specifically, not its full analysis surface. Both approaches
  answer the same real question at two different pipeline layers, with a
  fundamental noise-robustness-vs-lag tradeoff — see the module
  docstring, and `docs/findings.md`'s "Year of change" entry for a major
  finding: at default settings, `year_of_change()` can lag a true
  disturbance event by over a decade. `year_of_change()`/
  `disturbance_mask_for_year()` VERIFIED against real Earth Engine at
  the known B&B Complex Fire point and rendered spatially at reduced
  resolution over the same test AOI. `zscore_anomaly_mask_for_year()`
  VERIFIED at full-cell scale. Explicitly does NOT handle "changed, then
  recovered" — a documented limitation pending the real
  `afn_interpretBULCDResult` source. **Not yet reconsidered for the
  restored expectation/target split** (`docs/decisions/0010`,
  2026-08-11): both functions were built to search a long multi-year
  `classification_stack`, which is now typically just the target
  period's short single-season Event sequence - "when did it change"
  mostly collapses to "did it change within this target window" under
  the restored design, a materially simpler question this module hasn't
  been updated to answer yet. Flagged as an open follow-up, not silently
  left stale.
- `bulcd/export.py` — `export_image_to_asset()`, a thin wrapper starting
  (not blocking on) an `ee.batch.Export.image.toAsset()` task. Used in
  production for `scripts/export_year_disturbance_map.py` (see
  `docs/findings.md`'s "Two-layer..." and "Non-forest mask" entries for
  what was and wasn't verified in that run, and an open, unresolved
  question about asset-listing calls not finding successfully-exported
  assets) and `scripts/export_cell_8c_comparison.py` (new 2026-08-11,
  see `docs/findings.md`'s "Revalidated 2026-08-11 against the real
  GUI..." entry — exports cell 8C's `final_probabilities` to
  `projects/bulcd-python-rebuild/assets/bulcd_cell8c_comparison_final_probabilities`.
  Compared by the user against the real GUI's render: large discrete
  disturbance features visually match, but a broad reduction in
  scattered `decrease` speckle across much of the cell in the rebuild
  does not. An initial `gui_image.subtract(rebuild_image)` diff read as
  a diagonal west/east split, and five hypotheses framed around that
  split were each tested and individually ruled out or folded into
  another (sensor-coverage tiling boundary; a GUI expectation-year
  default mismatch — the GUI has no default at all, checkboxes start
  unchecked; a land-management/protection-status gradient — real
  [Mount Rainier NP + 3 wildernesses, 68% protected east vs. 15% west]
  but Hansen `lossyear` loss is actually higher in the protected east,
  ruling out an "actively managed west" story; an elevation-correlated
  negative z-score bias in the east half, real but insufficient alone;
  target-period evidence density, nearly identical both sides). Full
  numbers for each in `docs/decisions/0010`'s matching entry.

  **2026-08-12, major finding: the west/east framing was wrong, and
  `final_probabilities` itself is the real issue.** Directly comparing
  the GUI and rebuild renders side by side (not just the diff) showed
  the mismatch is spatially broad, not a clean split.
  `scripts/debug_cell_8c_transient_vs_final_decrease.py` found that
  `final_probabilities` — a snapshot of only the LAST target-period
  Event's posterior — discards most real, transient `decrease` signal
  from earlier in the sequence: "did this pixel ever classify as
  `decrease` at any of the 61 target-period Events" is dense and
  widespread, while "is `decrease` the final argmax" is sparse, confined
  to the two known discrete features. Mechanism: `posterior_leveler=0.9`
  (confirmed real) dampens toward the prior after every real Event
  (~34/pixel on average) — `0.9^34 ≈ 3%` of an early Event's influence
  survives to the end, so genuine mid-sequence disturbance gets smoothed
  away by the time the sequence's last Event is reached. This is a
  spatially broad effect, matching the actual observed mismatch far
  better than any west/east hypothesis did. Open question: GUI's own
  render, using the same confirmed leveler math, should show similar
  washing-out — but visibly doesn't. Either the GUI's displayed image
  isn't literally "state after the single last Event" the way
  `final_probabilities` is (a definitional mismatch), or this rebuild's
  Event count/ordering differs from production's real per-step process
  in some unconfirmed way. Not yet resolved — see `docs/decisions/0010`'s
  matching entry.
- **Reality check on test coverage**: only genuinely pure-Python logic
  is tested without a live EE session — `_select_modality_regressors()`,
  the loader's validations, and the upfront config guards in
  `organize_inputs()`/`run_bulcd()` (which raise before constructing any
  `ee.Image`). The actual regression fit, z-score/binning image math, and
  the Bayesian fold itself all construct `ee.Image`/`ee.ImageCollection`
  objects directly and therefore need a live, initialized EE session to
  test meaningfully — there's no way to unit-test that arithmetic in pure
  Python without either a live project or a parallel non-EE reference
  implementation that could drift from the real one. 35 passing tests
  total across `tests/test_config_loader.py`, `tests/test_inputs.py`,
  `tests/test_engine.py` (no dedicated `test_interpret.py` yet — same
  live-EE-session caveat applies).
- `cli.py` and the `sensors/` submodule from the earlier package-structure
  draft are still unwritten — see "Legacy source repos and what's still
  missing" above.
