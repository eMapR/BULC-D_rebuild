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

**These are `.rtf`/`.docx`, not plain text** — the Read tool will show raw
markup. Convert first: `textutil -convert txt -output out.txt in.rtf` (macOS).

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
  its sub-configs: study area, sensors, temporal window, reduction band,
  advanced BULC tuning, export settings).
- `bulcd/config/loader.py` — `load_config(path) -> BULCDConfig`. Parses
  YAML, validates required fields and enum-like values section by
  section, raises `ConfigError` with a specific message rather than
  silently defaulting — a bad config here means a real, billed Earth
  Engine export runs against the wrong AOI/dates. 8 passing tests in
  `tests/test_config_loader.py`; `configs/example.yaml` is a filled-out
  example.
- No engine/algorithm code yet (`inputs.py`, `bulc.py`, `engine.py`,
  `interpret.py`, `export.py`, `cli.py`, and the `sensors/` submodule
  from the earlier package-structure draft are all still unwritten).
