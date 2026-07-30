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

**Open design question, NOT resolved:** whether/how to address this is a
real decision, not something to default into silently:
- Lower the default `dampening_factor` further (tested range above
  suggests something like 0.05 is needed for competitive detection in a
  case this stark - but that's a specific number tuned to one pixel and
  one matrix, not validated broadly).
- Add a recency-weighting/forgetting mechanism so very old evidence
  matters less than recent evidence - NOT part of the classic BULC
  formulation described in Cardille & Fortin (2016) or Willis (2022);
  this would be a genuine departure from the reconstructed method, not
  just a parameter tweak.
- Rebalance the transition matrix's bin 1 vs. bin 5/6 asymmetry so
  "decrease" evidence tilts as hard, per observation, as "unchanged"
  evidence does - but that changes the matrix itself, and we don't have
  the real production matrix to compare against for whether this
  asymmetry is intentional or an artifact of Willis's one worked example.

None of these have been applied. Flag this prominently before treating
any BULC-D output over long evidence windows as reliable "no change"
labeling without checking dampening sensitivity first, the way this
finding was uncovered.

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
  `custom_transition_matrix`, `dampening_factor`, plus an opaque `raw`
  dict for whatever else `BULCD-AdvancedParameters-v5` turns out to hold
  — see "Reference papers" above), `ExportConfig`). Each field's
  docstring cites which legacy field it replaces and why; see the module
  docstring for full provenance.
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
  default).
- `bulcd/inputs.py` — PARTIAL. Real, working: `resolve_study_area()` and
  `assemble_evidence_collection()` (harmonized Landsat 5/7/8/9
  Collection 2 Level 2 SR, QA_PIXEL cloud mask, NBR/SWIR/NDVI reduction,
  per-sensor continuous year range + seasonal DOY filter via
  `ee.Filter.calendarRange`, merged + `.toFloat()`-cast + time-sorted).
  Sentinel-1/2, MODIS, ALOS/NICFI/Dynamic World raise
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
  dampening factor. Mirrors the legacy's actual module split (this is
  the still-unfetched `BULC-Minimal-Module-107`'s counterpart; `afn_BULCD`'s
  counterpart is `engine.py` below) — this module has no idea what a
  z-score or a burn index is, only "update factor" images and a running
  prior. `BulcResult.probability_stack`/`classification_stack` are
  `ee.ImageCollection` rather than the legacy's single flattened
  multi-band `Image` fields — a deliberate divergence, more directly
  useful for "expose intermediate probability/uncertainty surfaces"
  (Vision doc goal). VERIFIED against real Earth Engine (same single
  test pixel as above, run through the full 61-step fold).
- `bulcd/engine.py` — NEW, real code: the `afn_BULCD` equivalent, gluing
  `organize_inputs()`'s z-score stream to `bulc.py`'s generic engine via
  binning (`_bin_zscore`) and a transition-matrix lookup
  (`_bin_to_update_factors`). `run_bulcd()` fails loudly up front (before
  touching `ee.*` at all) if `custom_transition_matrix` isn't configured,
  or if its row count doesn't match `bin_cuts`. VERIFIED against real
  Earth Engine (same test run). `scripts/debug_run.py` is the actual
  runnable entry point for this today — hardcoded small test AOI/config,
  cheap `.getInfo()` sanity checks, not a real CLI (`bulcd/cli.py`
  doesn't exist yet).
- **Reality check on test coverage**: only genuinely pure-Python logic
  is tested without a live EE session — `_select_modality_regressors()`,
  the loader's validations, and the upfront config guards in
  `organize_inputs()`/`run_bulcd()` (which raise before constructing any
  `ee.Image`). The actual regression fit, z-score/binning image math, and
  the Bayesian fold itself all construct `ee.Image`/`ee.ImageCollection`
  objects directly and therefore need a live, initialized EE session to
  test meaningfully — there's no way to unit-test that arithmetic in pure
  Python without either a live project or a parallel non-EE reference
  implementation that could drift from the real one. 29 passing tests
  total across `tests/test_config_loader.py`, `tests/test_inputs.py`,
  `tests/test_engine.py`.
- `interpret.py`, `export.py`, `cli.py`, and the `sensors/` submodule
  from the earlier package-structure draft are still unwritten — see
  "Legacy source repos and what's still missing" above (`interpret.py`
  still needs the missing `afn_interpretBULCDResult` source; `export.py`/
  `cli.py` haven't been started).
