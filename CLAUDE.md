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
- Two published-paper PDFs at the repo root, added 2026-07-29 — see
  "Reference papers" below for what each contributes:
  - `1-s2.0-S0034425716303248-main.pdf` — Cardille & Fortin (2016),
    *Remote Sensing of Environment* 186. The original BULC (not BULC-D)
    paper; gives the actual low-level Bayesian updating math.
  - `2022_Honours_Project_Written_Report__Eidan_Willis__compressed_.pdf`
    — Eidan Willis's McGill honours thesis on BULC-**D** specifically
    (NBR12 vs. BAI burn-index comparison). Gives the z-score/harmonic
    /transition-matrix math that `guiBULCD.rtf`'s missing
    `organizeBULCD_Inputs` source would otherwise be the only source for.
  - Both are scanned/text PDFs; the `Read` tool needs `poppler` for its
    normal page-render path, which isn't installed in this environment —
    text was extracted instead with `pypdf`, and the two figure pages
    with the actual transition-matrix numbers were rendered to PNG with
    `pymupdf` (`pip install pypdf pymupdf`) and read as images.

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
Bayesian updating core" requirement above. **Update 2026-07-29:** the two
papers in "Reference papers" below substantially de-risk this — they're
published, citable descriptions of the actual method (not a guess from
field names), covering both the low-level Bayesian update (`bulc.py`) and
the BULC-D-specific z-score/transition-matrix layer (`organize_inputs()`).
They're not a substitute for the real `organizeBULCD_Inputs` source if
exact production behavior ever needs to match bit-for-bit (e.g. precise
bin cut-points, the *shipped* default transition matrix rather than one
researcher's hand-tuned example) — but they're a credible basis to
implement against now rather than waiting on the missing source.
**Update 2026-07-29 (later same day):** `bulc.py`, `bulcd/engine.py`, and
`organize_inputs()` are now actually written against this reconstruction
— see "Current code state" below for exactly what's implemented vs.
still assumption-flagged vs. still unverified against live Earth Engine.

## Reference papers — real math for the Bayesian core

Two papers (see "Contents") were read in full 2026-07-29. Together they
cover both layers of BULC-D that were previously unwritten stubs:

**Cardille & Fortin 2016 (the original BULC paper)** describes the
low-level Bayesian engine BULC-D wraps (likely corresponds to the
still-unfetched `BULC-Minimal-Module-107`) — this is `bulc.py`/`engine.py`
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
  to any single Event (the paper used `d = 0.5`).
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
  In practice a simplified 2-term version fit better:
  `index_t = β0 + β3*sin(2πωt)` — i.e. just the constant + one sine term.
  This is almost certainly what `ModalityConfig`'s `unimodal` shape maps
  to; `constant` would be `β0` alone (no seasonality term).
- **Z-score**: `(observed_index - fitted_expectation) / residual_stddev`,
  the standard definition — confirms `ZScoreNumeratorFactor`/
  `ZScoreDenominatorFactor` are just scaling knobs on this same formula.
- **10 discrete "collection bins"** (→ `binCuts`) by z-score, roughly:
  bins 5–6 = within ±1 std ("no change"); bins 1–4 = increasingly large
  drops (1–3 = most extreme); bins 7–10 = increasingly large increases
  (bin 10 as a catch-all for atmospheric-interference outliers, weighted
  low so it doesn't dominate). Exact cut-points weren't given as a
  formula in the thesis — still worth confirming against
  `organizeBULCD_Inputs` if bit-exact reproduction ever matters.
- **The key structural difference from classic BULC**: instead of a
  *data-derived* confusion matrix between two classified Events, BULC-D
  uses a **fixed, hand-tuned "custom transition matrix"** — a 10×3
  lookup (10 bins × 3 decision classes: index-drop/burn, no-change,
  index-increase/regrowth) supplied as a literal parameter, playing the
  same conditional-probability role in the Bayes formula above. This is
  almost certainly what the missing `BULCD-AdvancedParameters-v5` file
  contains for production. The thesis gives its own worked NBR12 example
  verbatim (not necessarily the shipped default, but a concrete, correctly-
  shaped real one):
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
  likelihood weights, not empirical proportions.
- BAI needed its own separately hand-tuned transition matrix (not
  transcribed here) because it inverts NBR12's sign convention (BAI
  *increases* on burn) and spans a very different numeric range —
  reinforcing that this matrix is index-specific, not universal, and
  should be a configurable parameter per burn index rather than hardcoded.

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
  fixed window. **Decided (2026-07-29):** implemented as
  `EvidenceConfig.expectation_first_year`/`expectation_last_year` — a
  single **global** date range (not per-sensor) applied as a plain date
  filter on the already-merged, sensor-agnostic evidence stream
  (`assemble_evidence_collection()` discards sensor identity once every
  image is reduced to one spectral-index band, so `organize_inputs()`
  fits one harmonic model per pixel over that one band regardless of
  which sensor(s) contributed images within the window). This is a
  deliberate domain choice of which real calendar years count as
  "normal, undisturbed forest" — not derived from sensor
  data-availability, which would silently drift if a sensor's own
  `first_year`/`last_year` changed later. `loader.py` validates the
  window overlaps at least one enabled sensor's configured range.

  **The target period has no code representation at all - this is where
  the modernization actually changes the shape of the problem, not just
  the config surface.** The legacy scored one separate, fixed target
  window against the expectation model, once. There is no
  `target_collection` object anywhere in `organize_inputs()`. Concretely,
  in `bulcd/inputs.py`:

  ```python
  harmonic_full = evidence_collection.map(_add_harmonic_terms)  # EVERY image, not just "target" ones
  expectation_fitted_collection = harmonic_full.map(
      lambda img: _add_fitted_band(img, fit.coefficients, fit.regressor_names)
  )
  lof_zscore = expectation_fitted_collection.map(_add_zscore).select("zscore")  # z-score for EVERY image, forever
  ```

  The *same* fitted expectation curve (fit only on the baseline window
  above) is applied to score **every image in the entire evidence
  stream** - including the baseline years themselves (a deliberate sanity
  check: those z-scores should hover near 0, confirmed in "First live-EE
  verification" above) and every year after, indefinitely, as far as the
  archive goes. `bulcd/engine.py`'s `run_bulcd()` then takes that
  per-timestep z-score sequence, bins each value, and folds them through
  the sequential Bayesian updater (`bulc.run_bulc()`) one at a time. So
  the legacy's single "expectation vs. one target period" comparison
  becomes a continuous *sequence* of comparisons - every image is its own
  mini-comparison against the same fixed expectation model, each one a
  fresh piece of evidence folded into the running posterior via Bayes'
  rule. That sequence, not a second fixed window, *is* "use the full
  Landsat archive as continuous evidence" (Vision doc primary goal) in
  literal code terms.
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
  `organizeBULCD_Inputs` source once we have it.
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

## GEE Cloud project

Decided (2026-07-29): `bulcd` uses its own dedicated project,
**`bulcd-python-rebuild`** — NOT the sibling GeoTimeSeries project's
`eastern-cascades-bugnet` (that was considered and explicitly rejected in
favor of a project dedicated to this repo). Registered for Earth Engine
access and confirmed working via `ee.Initialize(project="bulcd-python-rebuild")`.
This unblocks real testing against live Earth Engine for the first time.

## First live-EE verification (2026-07-29) — and a default worth changing

With `bulcd-python-rebuild` working, `bulc.py`/`engine.py`/`organize_inputs()`
were run against real Earth Engine for the first time: a small AOI in the
eastern Cascades (WA), Landsat 8, 2014–2021, NBR, expectation window
2014–2016, Willis (2022)'s worked NBR12 transition matrix. **Nothing
crashed** — evidence assembly, the harmonic regression fit, z-scoring, bin
lookup, and the full 61-step Bayesian fold all executed end to end. Two
concrete sanity checks passed: evidence count (61 Landsat 8 scenes) was
reasonable for the date range, and the z-score of an image *inside* the
baseline window came back ≈0 (0.014), exactly as expected — a real,
working confirmation that `organize_inputs()`'s baseline-scoring logic
is behaving correctly, not just failing to crash.

**Finding: `dampening_factor: 1.0` (the schema's default at the time, i.e.
no dampening) produces extreme overconfidence over many sequential Events** —
exactly the failure mode Cardille & Fortin (2016) section 4.6 describes
as the reason they added the dampening factor in the first place (their
own example run used `d=0.5`, not `d=1.0`). At the same test pixel, one
run each with `d=1.0` and `d=0.5`, all else identical:

```
d=1.0: {decrease: 4.31e-58, unchanged: 1.0,          increase: 1.35e-48}
d=0.5: {decrease: 9.42e-10, unchanged: 0.99999999937, increase: 5.32e-09}
```

Both land on the same classification ("unchanged" — plausibly correct;
this pixel likely never burned across the test period), but the *magnitude*
of confidence differs by ~48 orders of magnitude. Repeated multiplicative
Bayesian updates over 61 consecutive Events compound relative differences
in the transition matrix's rows without dampening, overshooting into
values at the edge of float64 precision — not yet a NaN/underflow risk
here, but a real concern for a full multi-decade run with hundreds of
Events instead of 61.

**Applied (2026-07-29):** `BULCAdvancedParams.dampening_factor`'s default
changed from `1.0` to `0.5` (matching the paper's own tested value, in
`schema.py`, `loader.py`, and `bulc.py`'s `run_bulc()` signature), so a
config that doesn't explicitly think about this doesn't silently run with
no dampening. `d=1.0` (no dampening) is still fully supported by setting
it explicitly - just no longer the silent default. This is a documented,
empirically-observed finding, not a theoretical concern from reading the
paper alone.

## Known-burn validation (2026-07-29): the 2003 B&B Complex Fire

The first live test above only exercised an "unchanged" (never-burned)
pixel. To validate the "decrease/burn" path, the pipeline was run against
a real, known-burned point (user-supplied coordinates,
`-121.90249210117729, 44.53142096854933`, central Oregon Cascades) —
identified as inside the **2003 B&B Complex Fire** (ignited Aug 15, 2003).

Two dead ends before the working test, both informative:
- First attempt used only Landsat 8 (2013+) with a 2014–2018 baseline.
  Result: mostly *positive* z-scores in later years (0.7–1.25), i.e.
  apparent regrowth, not a burn signal — because a fire in 2003 predates
  Landsat 8 entirely. An L8-only evidence window can only see the tail
  end of recovery, never the actual transition. Fixed by enabling
  **Landsat 5** (2000–2012) to reach back before the fire — the first
  real exercise of the "use the full Landsat archive," not just L8, and
  a concrete illustration of why that modernization goal matters in
  practice, not just in principle.
- A separate full-year-DOY test (unrelated pixel, see the dampening-factor
  test above) surfaced wild winter z-scores (as extreme as ±6.8) from
  snow reflectance contamination — matching Willis (2022)'s own discussion
  section almost exactly. Growing-season-only DOY filtering (roughly
  May–Oct) avoids this and is the right default, not full-year.

With L5 (2000–2012, pre-fire baseline 2000–2002, R²=0.49) + L8
(2014–2023) combined and growing-season DOY filtering, the z-score
trajectory is unambiguous:

```
2003-08-18 (3 days post-ignition): zscore=-1.61
2003-09-26:                        zscore=-5.88
2004 through 2023, every year:     zscore between -2.8 and -6.3 (never recovers)
```

`engine.run_bulcd()`'s final classification at that point:
`decrease=0.9999`, `unchanged=0.000076`, `increase=2.6e-28` — confident,
correct. This is the strongest end-to-end validation the pipeline has
had: a real pre-fire baseline, a real fire, and a correct answer, with
the exact ignition date visible in the z-score jump. Still only one
pixel, one fire, one transition matrix (Willis's NBR12 example, not a
verified production default) — not a substitute for broader validation.

## Moderate-severity test (2026-07-29): the bin/matrix mechanism working as designed

A second point was picked via MTBS burn-severity data (`USFS/GTAC/MTBS/
annual_burn_severity_mosaics/v1`, band `Severity`, classes 1=Unburned-Low,
2=Low, 3=Moderate, 4=High), ~2.5km from the B&B Complex point above,
classified as MTBS severity 3 ("Moderate"). Note: MTBS actually classifies
the *original* B&B point above as severity 2 ("Low"), despite its
persistent -3 to -6 z-scores for 20 years — a discrepancy not
investigated further, flagged here in case it matters later.

Counterintuitive at first glance: the moderate-severity point's raw
z-scores were *more* extreme (down to -9.6) than the original point's
(-5.88), yet its final classification was far less confident
(`decrease=0.29, unchanged=0.71`, vs. the original's `decrease=0.9999`).
Explained by checking the actual bin distribution at each pixel
(`bulcd/engine.py`'s `_bin_zscore()`, using the default `bin_cuts` whose
outermost cuts are ±2 - any z beyond that collapses into the same
bin regardless of magnitude, so -2.1 and -9.6 get identical treatment):

```
                        bin 1 (extreme drop)   bins 2-4 (mild/moderate)
low-severity (orig):    155/186 valid (83%)    13
moderate-severity:      116/194 valid (60%)    51
```

Bins 3-4 in Willis's transition matrix actually favor "unchanged" over
"decrease" (`[0.07,0.12,0.02]`, `[0.03,0.16,0.02]`). The moderate point's
history has meaningfully more of its 20 years sitting in those
intermediate bins, diluting the accumulated evidence. This is the
pipeline correctly reflecting a real difference in how *consistently*
each pixel stayed changed over decades, not reacting to peak z-score
magnitude (which the ±2 bin ceiling makes irrelevant beyond that point
anyway) - reassuring, face-valid behavior.

## Major finding (2026-07-29): long stable baselines can mask real disturbance

A third point (user-supplied, picked via LandTrendr for a high-magnitude
disturbance, `-122.0582, 44.4823`) exposed a real structural limitation,
not a bug. R²=0.62 (the best fit of any test point). Z-scores sit near
zero for **14 years** (2000-2014), then crash to -6.9 in June 2015 and
stay between -5 and -10.9 for the following **9 years** - about as
unambiguous a disturbance signal as this pipeline will ever see.

At the default `dampening_factor=0.5`, the final classification was
`unchanged=0.9999999999994` - practically certain "no change," despite
nine years of extreme, sustained contrary evidence. A dampening sweep at
the same pixel:

```
d=0.5:  unchanged=0.99999999999936
d=0.2:  unchanged=0.9997
d=0.1:  unchanged=0.977   decrease=0.023
d=0.05: unchanged=0.846   decrease=0.140
d=0.02: unchanged=0.589   decrease=0.291   increase=0.120
```

**Mechanism:** Willis's transition matrix's "unchanged" bins (5/6) are
*more* lopsided (`[0.015, 0.2, 0.01]`, a 13:1 ratio) than its "decrease"
bin (1) is (`[0.16, 0.11, 0.02]`, only 1.5:1). Under sequential Bayesian
updating (Cardille & Fortin 2016 Eq. 2), each observation's tilt
compounds multiplicatively with every prior observation. Fourteen years
of mild-but-consistent "confirm normal" evidence (~90 observations, each
tilting hard toward unchanged) built up such a lead that nine years of
dramatic "this changed" evidence (~130 observations, each tilting only
mildly toward decrease) can't fully overturn it at `d=0.5` - it takes
very aggressive dampening (`d≈0.02-0.05`) before "decrease" even becomes
competitive.

**Why this matters beyond this one pixel:** this is a structural property
of naive sequential Bayesian updating over long, mostly-stable evidence
streams, not a fluke of this transition matrix or this pixel. It's
directly in tension with this project's core modernization goal - "use
the full Landsat archive (1984-present) as continuous evidence." The
longer a stable pre-disturbance baseline gets (which using more of the
archive as evidence directly causes), the harder a genuine later
disturbance becomes to detect at a fixed dampening factor, because more
stable years means more compounding "confirm normal" evidence to
overturn. A pixel with 40 years of stable history before a 2020
disturbance would face an even steeper climb than this 14-year case.

**Follow-up test: does lowering the default to `d=0.05` actually fix
this?** Reran all four test pixels above (stable, B&B Complex fire,
moderate-severity, long-baseline disturbance) at `d=0.5` vs `d=0.05`:

| Point | `d=0.5` (argmax) | `d=0.05` (argmax) | Changed? |
|---|---|---|---|
| Stable/unchanged | unchanged 0.9999999937 | unchanged 0.65 | Same label, much less confident |
| B&B Complex fire | decrease 0.9999 | decrease 0.67 | Same (correct) label, less confident |
| Moderate-severity | unchanged 0.71 | decrease 0.50 vs. 0.485 | **Flips** - barely, to the arguably-more-correct answer |
| Long-baseline disturbance | unchanged 0.99999999999936 | unchanged 0.846 | **Still wrong** - confidence drops a lot but doesn't flip |

**Conclusion: dampening alone, even pushed fairly hard (`d=0.05`, and
per the sweep above even `d=0.02`), is NOT sufficient to fix the worst
case.** It reduces overconfidence broadly (useful) and correctly nudges
the genuinely-ambiguous moderate-severity pixel toward "decrease," but
the stark 14-year-stable/9-year-disturbed pixel stays misclassified as
"unchanged" even at `d=0.02`. This rules out "just lower the default
dampening factor" as a complete fix by itself - it's a real mitigant,
not a solution, for this specific failure mode.

Three possible directions were considered: lowering `dampening_factor`
further (ruled out above - doesn't fully fix it even at `d=0.02`); adding
a recency-weighting/forgetting mechanism (not part of the classic BULC
formulation, a genuine departure from the reconstructed method); or
rebalancing the transition matrix itself (no real production matrix to
compare against, so any rebalancing would be a guess). Recency weighting
was implemented and validated - see "Recency weighting" below.

## Recency weighting (2026-07-30): implemented and validated

`bulcd/bulc.py` gained a new function, `discount()`, and `run_bulc()`/
`run_bulcd()` gained a new optional parameter, `recency_factor`
(threaded through `BULCAdvancedParams.recency_factor`, schema/loader
validated to `0 < recency_factor <= 1`, same pattern as
`dampening_factor`). **This is NOT part of Cardille & Fortin (2016) or
Willis (2022) - a genuine algorithmic addition**, not a port of anything
in the reconstructed source material. Mechanism: after each
`bayes_update()` step, the posterior is raised to the power
`recency_factor` and renormalized (`posterior^gamma / sum(posterior^gamma)`).
At `gamma=1.0` (the default - off) this is an exact no-op, so the engine
remains faithful to the reconstructed classic method unless a caller
explicitly opts in - "preserve the Bayesian updating core" (CLAUDE.md
modernization goal) means this must never be a silent default. At
`gamma<1`, each step's influence on the running posterior decays
geometrically relative to the most recent step, which directly targets
the compounding-imbalance mechanism described above.

**Validated by rerunning all four test pixels at `gamma=1.0` (off) vs.
`gamma=0.99`/`0.98`/`0.95`, all at `dampening_factor=0.5`:**

| Point | gamma=1.0 (off) | gamma=0.99 | gamma=0.98 | gamma=0.95 |
|---|---|---|---|---|
| Stable/unchanged | unchanged 0.99999999 | unchanged 0.9999989 | unchanged 0.99996 | unchanged 0.9933 |
| B&B Complex fire | decrease 0.9999 | decrease 0.9995 | decrease 0.9930 | decrease 0.8825 |
| Moderate-severity | unchanged 0.71 | ~toss-up (0.49/0.51) | unchanged 0.77 | unchanged 0.82 |
| **Long-baseline disturbance** | **unchanged 0.9999999999994 (wrong)** | unchanged 0.81 (still wrong) | **decrease 0.93 (correct)** | decrease 0.88 (correct) |

At `gamma=0.98`: the long-baseline case **flips to the correct
classification**, while the two unambiguous cases (stable, B&B fire)
*stay* correctly classified with high confidence - the fix doesn't come
at the cost of breaking what already worked. The moderate-severity case
wobbles non-monotonically across gamma values, which is expected for a
genuinely borderline case (MTBS itself only calls it "moderate"), not a
red flag.

**Default stays `recency_factor=1.0` (off).** This was a deliberate
choice, not an oversight: unlike `dampening_factor` (whose 0.5 default
matches Cardille & Fortin's own tested value), there is no published
value for this parameter anywhere in the reference material - it's a
novel addition validated against exactly one stark failure case plus
three others as regression checks, not broadly validated. Turn it on
deliberately per-config, informed by this section, not by assuming the
default should change again.

`scripts/debug_long_baseline_disturbance.py` now includes both the
dampening sweep and a `recency_factor` sweep reproducing the table above
directly against the real `engine.run_bulcd()` code (not just the ad hoc
experiment this was first tried in).

## Disturbance map (2026-07-30): first full-AOI visualization, plus a water mask

Every validation above only ever sampled a single pixel via
`reduceRegion()`. `engine.run_bulcd()`'s `final_probabilities` has always
been a full image over the entire AOI, not just a point - this was the
first time it was actually looked at spatially, via
`ee.Image.getThumbURL()` (a cheap, synchronous preview render, NOT
`Export.image.toAsset/toDrive` - `bulcd/export.py` still doesn't exist).

Rendered the B&B Complex Fire AOI (widened to ~13km, see
`scripts/debug_disturbance_map.py`) as an RGB composite
(R=decrease, G=unchanged, B=increase - the same convention the legacy
caller used for `Map.addLayer(finalBulcProbs, ...)`). Result: a coherent,
irregular red region with a realistic fire-perimeter shape, not noise
scattered across the AOI - the strongest visual validation the pipeline
has had, corroborating all the single-pixel numeric checks above.

**Artifact found: water bodies misclassified as "increase"** (scattered
blue specks, mostly in the AOI's upper portion and a lower-left cluster).
Expected - water's reflectance behaves nothing like the forest-tuned
harmonic model, and the legacy pipeline always applies `afn_waterMask()`
before displaying/exporting results (`legacy/BULCD-Caller-Current.txt`);
we'd never applied any water masking. Added `bulcd/engine.py`'s
`_water_mask()`, using the standard public **JRC Global Surface Water**
dataset (`JRC/GSW1_4/GlobalSurfaceWater`, band `occurrence`, threshold
>50% - we don't have `afn_waterMask()`'s actual source, so this is a
reasonable standard-dataset substitute, not a reconstruction of it).
Wired in via `StudyAreaConfig.mask_water` (default `True`, matching the
legacy's unconditional behavior; can be disabled).

**Verified partial, not total, fix.** Rerendering with masking on shows
real water bodies now correctly excluded (visible as new gaps in the
map). But most of the original blue specks are still there. Sampling one
directly: JRC `occurrence` at that exact pixel is `None` (zero recorded
water history) - it isn't water at all. So the remaining "increase"
speckling has a different, NOT YET IDENTIFIED cause - candidates include
genuine small-scale greening, a terrain/shadow artifact in the Cascades'
rugged relief, or persistent snow/ice at elevation even within the
growing-season DOY window. Flagged here rather than investigated further
this session - don't assume the water mask fully resolved the artifact
just because it's now present in the code.

`scripts/debug_disturbance_map.py` reproduces this (prints a thumbnail
URL - fetching it requires an authenticated request, see the script's
own docstring for the pattern used to build one).

## Grid-cell maps (2026-07-30): AOI sourced from the real study-area grid

`scripts/debug_grid_cell_map.py CELL_ID` runs the same disturbance-map
pipeline as `debug_disturbance_map.py` above, but sources its AOI from
the actual study-area grid asset instead of a hand-picked box:
`projects/eastern-cascades-bugnet/assets/clipped_grid_35000m` (a sibling
GeoTimeSeries-project asset — the route-corridor grid, cells clipped to
the buffer so they're irregular polygons, not clean squares). Cells are
selected by their `grid_id` property (row + column-letter, e.g. `"11A"`,
`"2F"`) — confirmed via `.propertyNames()`/`.toDictionary()` on the
asset (`row`, `column`, `column_letter`, `grid_id`, `clipped_area_m2`,
`cell_size_m` are the other fields). The script filters the
`FeatureCollection` to one feature, pulls its polygon ring via
`.geometry().getInfo()`, and feeds it through `StudyAreaConfig.aoi_coordinates`
(the config layer has no "asset + filter" option yet — `resolve_study_area()`'s
`aoi_asset` path only supports a whole collection's unioned geometry, not
a single filtered feature — so the filtering happens in the script, not
`bulcd/inputs.py`).

Sensor/baseline config (L5 2000-2012 + L8 2014-2024, growing-season DOY,
2000-2003 expectation baseline, Willis NBR12 transition matrix,
`dampening_factor=0.5` default) is copied as-is from `debug_disturbance_map.py`
rather than tuned per cell — the 2000-2003 window was originally chosen
for the B&B Complex Fire's known pre-fire history, and is reused here as
a generic "earliest available" default since arbitrary grid cells have
no known disturbance history to tune against. Worth revisiting per-cell
if a specific cell's baseline years turn out not to be disturbance-free.

First run, cell `2F`: a coherent map, mostly "unchanged" (green) with
"decrease" (red) clustered in patches rather than scattered noise, and —
notably — a river visibly cut out as a clean white (masked/nodata) line
through the middle of the AOI, the clearest visual confirmation yet that
`_water_mask()` is doing real work along a linear water feature, not just
isolated ponds like the earlier B&B Complex test.

## Year of change (2026-07-30): querying "disturbance in year Y," and a major lag finding

Everything above answers "what's the current state" (`final_probabilities`)
or "what's the state as of some cutoff" (truncate the evidence config).
Neither answers what was actually asked next: "if I say 2025, give me a
disturbance map for 2025 specifically" - i.e. WHEN, not just whether, a
pixel changed. This didn't exist in the pipeline at all until now - it's
the post-run analysis step the legacy calls `afn_interpretBULCDResult`
(still-missing source, `r-2902-Dev` - see "Legacy source repos" above),
so everything here is a new reconstruction, not a port.

**Two prerequisite gaps had to be fixed first, both in code that already
existed:**
- `bulc.py`'s `run_bulc()` folds `classification_stack`/`probability_stack`
  from arithmetic on `prior`/`update_factors` - neither ever carried the
  source Event's date. Fixed by `.set("system:time_start", ...)` in
  `_step()` - NOT `copyProperties()`, which was tried first and silently
  no-ops for `system:` properties even when named explicitly in its
  `properties` argument (only "ordinary" properties are copied; this isn't
  documented clearly and cost real debugging time).
- `engine.py`'s `_bin_to_update_factors()` builds each update-factor image
  via `ee.Image.cat()` over `ee.Image.constant()`/`.where()` chains, none
  derived from the source z-score image - so even after fixing `bulc.py`,
  every step was STILL undated until `_to_update_factors()` in
  `run_bulcd()` also explicitly re-set `system:time_start` from the
  z-score image onto the resulting update-factor image before it reaches
  `bulc.run_bulc()`.

**New module: `bulcd/interpret.py`.** `year_of_change(classification_stack,
target_class_index=0)` returns, per pixel, the calendar year of the
earliest Event that begins an unbroken run of the target class
(default: "decrease") lasting through the LAST Event in the stack;
masked where the pixel doesn't currently sit in that class.
`disturbance_mask_for_year(classification_stack, year, target_class_index)`
filters that to one specific year. Implementation note: `ee.Array`-based,
entirely server-side, no client-side round trip for series length. Two
non-obvious EE quirks hit along the way, both now commented in the code:
`ee.ImageCollection.toArray()` produces a 2-D array (image axis x band
axis) even for a single-band collection - needs `.arrayProject([0])` to
collapse to a plain 1-D time series; and `ee.Image.arraySlice()` has no
negative-step reverse, so the detector finds the LAST mismatching index
via a forward `arrayReduce(max)` trick instead of scanning backward from
the end. Explicitly does NOT handle "changed, then recovered" - a pixel
whose persistent run doesn't reach the final Event is masked, identically
to a pixel that never changed - a real, documented limitation pending the
actual `afn_interpretBULCDResult` source.

**Validated against the known 2003 B&B Complex Fire point - and this
surfaced a major finding, not just a confirmation.** At default settings
(`dampening_factor=0.5`, `recency_factor=1.0`/off), `year_of_change()`
returned **2015**, not 2003. This was double-checked against the raw
`classification_stack` sequence directly (dumped every Event's date +
argmax class at the point) - the algorithm's own argmax classification
genuinely stays "unchanged" from 2000-06-22 all the way through
2015-08-19, THEN flips to "decrease" and never reverts. So the detector
is behaving correctly; the finding is about the algorithm, not a bug:

**Even though the z-score jumps hugely negative within days of the real
2003 ignition (see "Known-burn validation" above), the running Bayesian
argmax classification takes 12 YEARS to actually flip**, because each
step's update factor is dampened toward uniform (`d=0.5`) and the prior
years of "confirm normal" evidence (even just 3 years, 2000-2002) still
takes many consecutive negative-z Events to overcome. This is the same
compounding mechanism as "Major finding: long stable baselines can mask
real disturbance" above, but demonstrated here on the pipeline's own
best-validated real-fire test point - and it directly undermines the
premise of a year-specific query: at default settings, "disturbance in
year Y" is really answering "when did the algorithm finally admit it,"
which can lag the true event by over a decade.

`recency_factor` (built earlier for exactly this compounding problem)
measurably helps, tested at the same point:

| `recency_factor` | detected `year_of_change` |
|---|---|
| 1.0 (off) | 2015 |
| 0.99 | 2009 |
| 0.98 | 2007 |
| 0.95 | 2006 |

Monotonically closer to the true 2003 ignition as recency weighting
increases, but NOT exact even at 0.95 - there is no known setting that
eliminates this lag, only reduces it. Anyone using
`disturbance_mask_for_year()` for real analysis needs to know this before
trusting a specific year's map, especially at the library default
(`recency_factor=1.0`).

**A second, unrelated limit surfaced trying to render this spatially,
not just at one point:** `year_of_change()` materializes a full per-pixel
time-array (~200+ values for a multi-decade config) - much heavier per
pixel than `final_probabilities`' simple 3-band image. A `getThumbURL`
preview at `dimensions=512` (fine for `debug_disturbance_map.py`'s
`final_probabilities`) hit "User memory limit exceeded" for a
`year_of_change`-based map over the same ~13km test box; `dimensions=128`
succeeded and showed a coherent, non-random cluster of pixels flipping to
"decrease" specifically in 2015. This is a synchronous-preview scale
limit, not a fundamental one - a real full-resolution/full-cell map would
need an actual batch export (`Export.image.toAsset`/`toDrive` -
`bulcd/export.py` still doesn't exist), not `getThumbURL`.

`scripts/debug_year_of_change_map.py CELL_ID YEAR [RECENCY_FACTOR]`
reproduces all of this against a real grid cell (see "Grid-cell maps"
above for how AOIs are sourced from `clipped_grid_35000m`).

## Two-layer "was this abnormal in year Y" + first real export (2026-07-30)

Follow-up to "Year of change" above, prompted by the user pointing out
their actual mental model: "flag disturbance if pixels in the target
image are outside what is normal as defined by the expectation time
period" - i.e. the raw z-score, not the Bayesian-accumulated
classification `year_of_change()` reads. Both are real, valid answers to
"was this pixel abnormal in year Y," at two different layers of the
pipeline, with a fundamental noise-robustness-vs-lag tradeoff between
them - see `bulcd/interpret.py`'s module docstring for the split. New:
`interpret.zscore_anomaly_mask_for_year(zscore_collection, year,
threshold=-2.0)` - true where ANY image in that calendar year has a
z-score at or below `threshold` (default matches `bin_cuts`'s own most
extreme cut), read straight from `organize_inputs()`'s per-image z-score
stream. No Bayesian accumulation, so no lag - but also no protection
against a single noisy/cloud-contaminated image, unlike
`disturbance_mask_for_year()`'s robustness-by-design.

**`bulcd/export.py` now exists** - thin wrapper around
`ee.batch.Export.image.toAsset()` (starts the task, hands back the
`ee.batch.Task`, does not poll/block - jobs can take minutes to hours).
This was the last major documented gap in "Current code state" below
alongside `interpret.py` (now also real, if partial).

**First real export run**, not a preview: cell `2F`, year 2025, both
layers combined into one 2-band image (`zscore_anomaly`,
`bulc_classification`), to `projects/bulcd-python-rebuild/assets/disturbance_2025`
(`scripts/export_year_disturbance_map.py`). Notes specific to this run:
- L8's `last_year` had to be bumped to 2026 (from other scripts' 2024) -
  `_date_bounds()`'s end-year is EXCLUSIVE, so 2025 data requires
  `last_year=2026`.
- Sanity-checked before spending the export: 13 evidence images exist for
  cell 2F in 2025 (non-zero, reasonable), and `zscore_anomaly` alone
  computes fine at full-cell scale (30m, real `reduceRegion` over the
  whole ~35km cell) with a non-degenerate split (~37% of the cell flagged
  anomalous in 2025 at the default threshold) - no evidence of a
  degenerate all-0/all-1 result before committing to the real export.
- `bulc_classification` (the `year_of_change()`-based band) still hits
  "User memory limit exceeded" via any synchronous call
  (`reduceRegion`/`getThumbURL`) at full-cell scale, even reduced to
  100m - consistent with the memory-limit finding above, and confirms
  this band genuinely needs the batch export path (a different compute
  tier, not subject to the interactive limit) rather than ever being
  previewable at this scale. Its actual output over the full cell
  wasn't verified before export - only at a single point and a smaller
  ~13km test box previously - so treat this run's `bulc_classification`
  band as unverified at cell-2F scale until the exported asset itself
  can be inspected.
- Given 2025 is only ~1 year removed from "now" (2026-07-30) and the
  validated 12-year lag finding, `bulc_classification` for this specific
  run is expected to come back mostly or entirely empty/masked - that's
  expected pipeline behavior given how little post-2025 evidence exists
  yet, not a bug, per the caveat threaded through this whole feature.

## Non-forest mask (2026-07-30): false "change" above treeline, and DOY narrowing ruled out

Inspecting the real `disturbance_2025` export (above), the user found
false "change" flagged near mountain tops, above the tree line. First
hypothesis - the same DOY window used everywhere else was still letting
in shoulder-season snow (June 1-Sept 30, `152-273`) - was tested by
narrowing to peak summer (`152-243`, June 1-Aug 31) across the three
active scripts (`debug_grid_cell_map.py`, `debug_year_of_change_map.py`,
`export_year_disturbance_map.py` - the earlier validation scripts
(`debug_bb_complex_fire.py` etc.) were deliberately left at `152-273`
since their documented CLAUDE.md findings are tied to that exact window).
**Re-exporting with the narrower window did not fix it** - confirmed by
the user directly. This ruled out the hypothesis, not just failed to
help: above-treeline terrain (bare rock, scree, permanent snow/ice) has
no seasonal window where it resembles the forest the expectation model
was fit on - narrowing WHEN you look doesn't fix looking at land that was
never forest in the first place.

**Real cause, found by inspecting the config rather than guessing
further:** `StudyAreaConfig.forest_mask_asset` has existed as a schema
field since the project's early scaffold stage (loaded by
`config/loader.py`) but was NEVER actually wired into `engine.py` - only
`mask_water`/`_water_mask()` were ever applied. Zero non-forest screening
existed anywhere in the pipeline until now.

**Fix: `StudyAreaConfig.mask_non_forest: bool = True`** (new field,
`config/loader.py` updated to parse it) + `engine.py`'s new
`_forest_mask(region, forest_mask_asset)`: uses `forest_mask_asset` if
the caller supplied one (treated as a boolean image, nonzero = forest),
else falls back to the standard public **Hansen Global Forest Change**
dataset's `treecover2000` band (`UMD/hansen/global_forest_change_2025_v1_13`,
not the deprecated `_2023_v1_11` - the API warns on that one), thresholded
at 10% canopy cover (FAO's common minimum-canopy "forest" definition) -
same "standard substitute, not the legacy's real asset" posture as
`_water_mask()`/JRC water. Sanity-checked on cell 2F before use: ~28% of
the cell flagged non-forest, ~72% forest - plausible for a mountainous
Cascades cell, not degenerate.

**New public helper: `engine.study_area_mask(config)`** - returns the
combined water+non-forest mask (or `None` if both toggles are off).
Needed because `run_bulcd()`'s automatic masking only ever touched
`final_probabilities` - `classification_stack`/`probability_stack`/
`organize_inputs()`'s `lof_zscore` bypass it entirely. This surfaced a
second, independent gap while fixing the first: **the `disturbance_2025`
export had no water masking either**, since
`zscore_anomaly_mask_for_year()`/`disturbance_mask_for_year()` both read
those un-masked collections directly, never routing through
`run_bulcd()`'s masking step. `export_year_disturbance_map.py` now calls
`engine.study_area_mask(config)` explicitly and applies it to the
combined 2-band output before export - fixes both the treeline artifact
and the missing water mask in one change.

Re-exported to `projects/bulcd-python-rebuild/assets/disturbance_2025`
(same path, asset overwritten) with both masks applied. **Open question,
not yet resolved:** verifying the two prior export attempts via
`ee.data.getAsset()`/`listAssets()` reported the asset as not existing
even though both tasks showed `state: SUCCEEDED` with a valid
`destination_uris` link, and the user was clearly able to view real
content from it (that's how the treeline artifact was found in the first
place). Root cause not identified - flagged here in case it recurs;
verify new exports directly in the GEE Code Editor rather than relying
solely on this codebase's own asset-listing calls until this is
understood.

## Legacy-GUI parameter matching + Sentinel-2 support (2026-08-10)

User's plan: run cell 8C through both the legacy GUI (`guiBULCD.rtf`) and
this rebuild, then compare outputs directly - the first real GUI-vs-rebuild
validation attempted in this project. Before running anything, worked out
which parameters could actually be matched, and how.

**Investigated `guiBULCD.rtf` directly** (converted via `textutil -convert
txt`) rather than guessing at "GUI defaults," since an imagined default
would have made for a false comparison:
- The Expectation/Target year checkboxes and DOY textboxes have **no
  default at all** - every year checkbox is instantiated
  `ui.Checkbox('20XX', false)` and every DOY field is a blank `ui.Textbox`
  with only a placeholder. These have to be chosen fresh in the GUI each
  session and mirrored by hand into the rebuild's config - there was
  nothing to inherit.
- `binCuts` **is** hardcoded (`[-2,-1.5,-1,-0.5,0,0.5,1,1.5,2]`, line 5965)
  - already matches `schema.py`'s default.
- `modalityDictionary`/`sensitivityDictionary` **do** have real GUI
  defaults: `{constant:true, unimodal:true}` / `{ZScoreNumeratorFactor:1,
  ZScoreDenominatorFactor:0.05}` (lines 5935-5954), matching
  `BULCD-InputParameters-v5`'s real production example too. This exposed
  a genuine, pre-existing mismatch: `ModalityConfig.unimodal` defaults to
  `False` in `schema.py`, not `True` - left as-is in the schema (not
  clearly a bug, just undocumented), but must be overridden per-config
  for any GUI-matching run.
- `customTransitionMatrix`/dampening factor are **not in `guiBULCD.rtf` at
  all** - pulled at runtime from a separate module we still don't have
  source for (`getBULCParameterDictionary()`,
  `6003.3c-BULC-AdvancedParameters`, `r-2903-Dev`). But the GUI **prints
  its fully-resolved argument dictionary to the Console right before
  calling the algorithm**: `print("Arguments to BULC-D", var_args_BULCD)`
  (line 7182), where `var_args_BULCD.BULCargumentDictionaryPlus` is
  exactly that module's real return value. **This is the actual way to
  get real production dampening/transition-matrix numbers** - run the GUI
  once, expand that object in the Console - not something to keep
  guessing at from Willis (2022)'s thesis example.
- Legacy applies `afn_waterMask()` unconditionally but has **zero
  forest-mask logic anywhere** in `guiBULCD.rtf` (grepped for
  forest/treecover/hansen/canopy - no hits). A real asymmetry against
  this rebuild's `mask_non_forest` (defaults `True`) - disabled per-config
  for a fair comparison rather than changing the schema default.

**New file: `configs/cell_8c_comparison.yaml`** - the first config file
actually driving a real run through `load_config()` rather than a
debug script's hardcoded Python `BULCDConfig(...)` construction (every
`scripts/debug_*.py` script until now built its config inline). AOI
fetched live from `clipped_grid_35000m`'s `grid_id="8C"` feature (same
pattern as "Grid-cell maps" above). Parameters transcribed directly from
the user's real GUI run: cross-sensor L8+L9+S2, expectation year 2024 /
target year 2025 (collapsed into one continuous evidence window per
sensor, `first_year:2024, last_year:2026` - `last_year` is exclusive),
DOY narrowed from an initial 1-365 to 74-288 (applied uniformly - the
schema has one DOY window per sensor covering the whole evidence stream,
no separate expectation-only/target-only split), cloud cover threshold
70, NBR, `day_step_size:3`, modality **unimodal only** (not
`constant+unimodal` - a deliberate GUI choice for this run, different
from the GUI's own out-of-the-box default found above), sensitivity
`{1, 0.05}`. `bulc_advanced_params.dampening_factor`/
`custom_transition_matrix` remain Willis-thesis placeholders pending the
Console readout described above - **not yet a fully parameter-matched
run** until those are filled in.

**Sentinel-2 support implemented in `bulcd/inputs.py`** - needed because
the real GUI comparison run enables S2, which previously raised
`NotImplementedError`. New: `_s2_with_cloud_probability()` (joins
`COPERNICUS/S2_SR_HARMONIZED` to its `COPERNICUS/S2_CLOUD_PROBABILITY`
companion collection by `system:index`), `_mask_s2_clouds()` (cloud +
cloud-shadow mask via cloud-probability threshold + NIR dark-pixel
shadow projection), `_scale_s2_sr()`, `_s2_evidence()` (mirrors
`_landsat_evidence()`'s shape). This is the standard community
s2cloudless recipe (Google's own tutorial, already referenced in
`S2CloudMaskConfig`'s docstring) - not a novel reconstruction, same
"standard substitute" posture as the water/forest mask additions above.

VERIFIED against real Earth Engine for cell 8C: evidence assembly returns
real imagery (352 total L8+L9+S2 images at the final DOY 74-288 window;
an isolated S2-only pull returned sane NBR values, e.g. 0.69 at one
sample date/region), and the full `organize_inputs()` harmonic-fit/
z-score pipeline runs end to end (477-image z-score stream at an earlier
DOY 1-365 test, one z-score per evidence image as expected - all 32
existing tests also still pass unchanged). A full-cell `reduceRegion` of
R2 timed out server-side ("Computation timed out") - consistent with the
interactive-compute-limit findings already documented for
`bulc_classification` above, not a defect in the new S2 code; a
single-point sample at the cell centroid worked fine (R2=0.039 - low,
plausibly a non-forest/glacier point near Mount Rainier given cell 8C's
coordinates, not diagnostic of a bug). MODIS/Sentinel-1/ALOS/NICFI/
Dynamic World remain unimplemented.

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
  expectation/target split, plus a global `expectation_first_year`/
  `expectation_last_year` baseline window — see "Design decision: the
  expectation baseline window" below), `ReductionConfig`, `ModalityConfig`,
  `SensitivityConfig`, `BULCAdvancedParams` (now partially typed:
  `custom_transition_matrix`, `dampening_factor`, `recency_factor` (see
  "Recency weighting" above — NOT from the legacy schema, a 2026-07-30
  addition, defaults off), plus an opaque `raw` dict for whatever else
  `BULCD-AdvancedParameters-v5` turns out to hold — see "Reference
  papers" above), `ExportConfig`). Each field's docstring cites which
  legacy field it replaces and why; see the module docstring for full
  provenance.
- `bulcd/config/loader.py` — `load_config(path) -> BULCDConfig`. Parses
  YAML, validates required fields and enum-like values section by
  section (including cross-field checks like "exactly one of
  `aoi_asset`/`aoi_coordinates`", "`sar_polarization` only valid for
  S1/AL", the expectation window overlapping at least one enabled
  sensor's range, `custom_transition_matrix` being 10×3, `bin_cuts`
  length + 1 matching the transition matrix's row count, `dampening_factor`
  in `(0, 1]`), raises `ConfigError` with a specific message rather than
  silently defaulting — a bad config here means a real, billed Earth
  Engine export runs against the wrong AOI/dates. 18 passing tests in
  `tests/test_config_loader.py`; `configs/example.yaml` is a filled-out
  example (including a transcription of Willis (2022)'s worked NBR12
  transition matrix, clearly commented as an example, not a shipped
  default). `configs/cell_8c_comparison.yaml` (added 2026-08-10) is the
  first config actually driving a real run rather than a debug script's
  hardcoded Python config - see "Legacy-GUI parameter matching" above.
- `bulcd/inputs.py` — PARTIAL. Real, working: `resolve_study_area()` and
  `assemble_evidence_collection()` (harmonized Landsat 5/7/8/9
  Collection 2 Level 2 SR, QA_PIXEL cloud mask, NBR/SWIR/NDVI reduction,
  per-sensor continuous year range + seasonal DOY filter via
  `ee.Filter.calendarRange`, merged + `.toFloat()`-cast + time-sorted),
  PLUS Sentinel-2 (added 2026-08-10 - `COPERNICUS/S2_SR_HARMONIZED` +
  the standard s2cloudless cloud-probability/shadow-projection recipe,
  see "Legacy-GUI parameter matching + Sentinel-2 support" above).
  Sentinel-1, MODIS, ALOS/NICFI/Dynamic World still raise
  `NotImplementedError` if enabled. `organize_inputs()` (the
  expectation-regression/R2/residuals/z-score step) is now IMPLEMENTED
  against the Cardille & Fortin (2016) / Willis (2022) reconstruction
  (see "Reference papers" above), not the real `organizeBULCD_Inputs`
  source, which we still don't have — every formula choice not given
  explicitly in the papers (modality-priority resolution when multiple
  `ModalityConfig` flags are true, the z-score denominator's stabilizing
  epsilon) is flagged inline as a documented assumption. Fits a harmonic
  regression per pixel over a configurable global baseline window
  (`ee.Reducer.linearRegression`, continuous fractional-year time axis
  rather than day-of-year, so multi-year baselines don't wrap around
  at year boundaries), then scores the *entire* evidence stream
  (baseline included, as a sanity check) into a continuous z-score
  `ee.ImageCollection`. VERIFIED against real Earth Engine (see "First
  live-EE verification" above) at a single test pixel — not a
  substitute for broader validation across more pixels/AOIs/conditions.
- `bulcd/bulc.py` — NEW, real code: the generic, index/sensor-agnostic
  Bayesian updating engine (`dampen()`, `bayes_update()`, `run_bulc()`),
  a direct implementation of Cardille & Fortin (2016) Eq. 1/2 and its
  dampening factor, PLUS `discount()` — a `recency_factor` extension
  added 2026-07-30 that's NOT part of the reconstructed classic method
  (see "Recency weighting" above), off by default. Mirrors the legacy's
  actual module split (this is the still-unfetched
  `BULC-Minimal-Module-107`'s counterpart; `afn_BULCD`'s counterpart is
  `engine.py` below) — this module has no idea what a z-score or a burn
  index is, only "update factor" images and a running prior.
  `BulcResult.probability_stack`/`classification_stack` are
  `ee.ImageCollection` rather than the legacy's single flattened
  multi-band `Image` fields — a deliberate divergence, more directly
  useful for "expose intermediate probability/uncertainty surfaces"
  (Vision doc goal). VERIFIED against real Earth Engine at four real
  test pixels (see all the sections above).
- `bulcd/engine.py` — NEW, real code: the `afn_BULCD` equivalent, gluing
  `organize_inputs()`'s z-score stream to `bulc.py`'s generic engine via
  binning (`_bin_zscore`) and a transition-matrix lookup
  (`_bin_to_update_factors`), passing `dampening_factor`/
  `recency_factor` through to `bulc.run_bulc()`, and applying
  `_water_mask()` to the final output by default (`StudyAreaConfig.mask_water`
  — see "Disturbance map" above; a verified-partial fix, not a complete
  one). `run_bulcd()` fails loudly up front (before touching `ee.*` at
  all) if `custom_transition_matrix` isn't configured, or if its row
  count doesn't match `bin_cuts`. VERIFIED against real Earth Engine at
  four real test pixels plus one full-AOI map. `scripts/debug_run.py`,
  `scripts/debug_bb_complex_fire.py`, `scripts/debug_long_baseline_disturbance.py`,
  `scripts/debug_disturbance_map.py`, and `scripts/debug_grid_cell_map.py`
  (see "Grid-cell maps" below) are the actual runnable entry
  points today — hardcoded test AOIs/configs, cheap preview renders
  (`.getInfo()`/`.getThumbURL()`), not a real CLI (`bulcd/cli.py` doesn't
  exist yet) and not a real export (`bulcd/export.py` doesn't exist
  either).
- **Reality check on test coverage**: only genuinely pure-Python logic
  is tested without a live EE session — `_select_modality_regressors()`,
  the loader's validations, and the upfront config guards in
  `organize_inputs()`/`run_bulcd()` (which raise before constructing any
  `ee.Image`). The actual regression fit, z-score/binning image math, and
  the Bayesian fold itself all construct `ee.Image`/`ee.ImageCollection`
  objects directly and therefore need a live, initialized EE session to
  test meaningfully — there's no way to unit-test that arithmetic in pure
  Python without either a live project or a parallel non-EE reference
  implementation that could drift from the real one. 32 passing tests
  total across `tests/test_config_loader.py`, `tests/test_inputs.py`,
  `tests/test_engine.py` (no dedicated `test_interpret.py` yet - see
  below).
- `bulcd/interpret.py` — NEW (2026-07-30), partial: `year_of_change()`/
  `disturbance_mask_for_year()` (see "Year of change" above) plus
  `zscore_anomaly_mask_for_year()` (see "Two-layer 'was this abnormal'"
  above) - a reconstruction, not a port, of the still-missing
  `afn_interpretBULCDResult`'s "when did it change" question specifically,
  not its full analysis surface. `year_of_change()`/`disturbance_mask_for_year()`
  VERIFIED against real Earth Engine at the known B&B Complex Fire point
  (surfaced a major finding: 12-year detection lag at default settings)
  and rendered spatially at reduced resolution (128px) over the same test
  AOI. `zscore_anomaly_mask_for_year()` VERIFIED at full-cell scale (cell
  2F, 30m, real AOI). No pure-Python-testable logic yet (unlike
  `organize_inputs()`/`run_bulcd()`'s upfront guards) - every function
  here builds `ee.Array`/`ee.Image` objects directly, so it needs a live
  EE session to test at all, same caveat as the rest of the array/image
  math in this codebase.
- `bulcd/export.py` — NEW (2026-07-30): `export_image_to_asset()`, a thin
  wrapper starting (not blocking on) an `ee.batch.Export.image.toAsset()`
  task. FIRST REAL EXPORT RUN (not a preview) completed the round-trip:
  cell 2F, year 2025, to `projects/bulcd-python-rebuild/assets/disturbance_2025`
  via `scripts/export_year_disturbance_map.py` - task queued successfully
  (see "Two-layer..." above for caveats specific to that run, notably
  that the `bulc_classification` band's actual full-cell output wasn't
  verified before export, only at a point and a smaller test box).
- `cli.py` and the `sensors/` submodule from the earlier package-structure
  draft are still unwritten — see "Legacy source repos and what's still
  missing" above.
