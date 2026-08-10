# BULC-D Rebuild

Modernization of **BULC-D** (Bayesian Updating of Land Cover Detection), a
probabilistic forest-change-detection algorithm originally built as a
Google Earth Engine (GEE) JavaScript Code Editor tool.

## Status

Actively in progress (as of 2026-08-10). Config handling and
continuous-evidence assembly (Landsat 5/7/8/9 + Sentinel-2) are real and
tested. The Bayesian updating core, expectation-model/z-score layer, and
BULC-D orchestration are implemented against a credible published
reconstruction of the legacy math — see "Reference papers" below — since
the original GEE JavaScript source for that core still hasn't been
obtained, and are validated against real Earth Engine at several known
disturbance points (including a real, dated wildfire). Post-run
"when did this change" analysis (`bulcd/interpret.py`) and real GEE
asset exports (`bulcd/export.py`) also exist now. See `CLAUDE.md`'s
"Current code state" for the exact, up-to-date breakdown of what's real
vs. stubbed vs. unverified.

**In progress: matching this rebuild against a real legacy GUI run**
(cell 8C, see CLAUDE.md "Legacy-GUI parameter matching" / "Real
production BULC-D parameters"). Reading the GUI's own Console output
live has already fixed one confirmed gap (unimodal's harmonic regressor
set) and surfaced the real production transition matrix, but also found
that production's dampening mechanism is structurally different from
this rebuild's single-parameter reconstruction (three separate
"levelers" plus minimum floors, not one scalar) — the comparison run is
paused pending `BULC-Minimal-Module-107`'s real source rather than
guessing at that formula.

**Platform decision (2026-07-28):** Python + [`earthengine-api`](https://developers.google.com/earth-engine/guides/python_install),
not GEE JavaScript. The algorithm still runs server-side on Earth Engine
as a computation graph — this is a client-language choice, not a move off
GEE.

## Reference papers


Two published papers (added 2026-07-29) stand in for the missing legacy
algorithm source and are the actual basis for the engine code in
`bulcd/bulc.py` and `bulcd/inputs.py`'s `organize_inputs()`:

- `1-s2.0-S0034425716303248-main.pdf` — Cardille & Fortin (2016),
  *Remote Sensing of Environment* — the original BULC paper; the
  low-level Bayesian update math (update tables, the Bayes formula,
  dampening).
- `2022_Honours_Project_Written_Report__Eidan_Willis__compressed_.pdf`
  — Eidan Willis's McGill honours thesis — BULC-D specifically:
  harmonic expectation-model fitting, z-score binning, and the
  hand-tuned "custom transition matrix."

These are a credible, citable reconstruction of the method, not a port
of the actual production source — see `CLAUDE.md`'s "Reference papers"
section for the full math and explicit caveats about where this
reconstruction is an assumption rather than a verified fact.

## Contents

- `bulcd/` — the new Python package (in progress).
  - `bulcd/config/schema.py` — typed configuration schema for study
    area, sensors, temporal window, reduction band, advanced BULC
    tuning (including the transition matrix / dampening factor above),
    and export settings.
  - `bulcd/inputs.py` — continuous multi-sensor evidence assembly (real,
    Landsat 5/7/8/9 + Sentinel-2) plus the z-score/expectation-model
    layer.
  - `bulcd/bulc.py` — the generic, index-agnostic Bayesian updating
    engine (update table → Bayes formula → dampening → posterior), plus
    an optional, off-by-default recency-weighting extension
    (`discount()`) not found in the reference papers — see CLAUDE.md
    "Recency weighting".
  - `bulcd/engine.py` — BULC-D-specific orchestration gluing the above
    two together (bins the z-score stream, looks up the transition
    matrix, runs the engine, applies water/non-forest masking).
  - `bulcd/interpret.py` — post-run "when did this pixel change"
    analysis: a fast-but-lag-prone Bayesian-classification answer and a
    fast-and-immediate raw-z-score answer to the same question, both
    real tradeoffs, not one replacing the other — see CLAUDE.md "Year of
    change" and "Two-layer 'was this abnormal in year Y'".
  - `bulcd/export.py` — thin wrapper starting a real
    `ee.batch.Export.image.toAsset()` task (not a preview render).
- `configs/` — YAML config files loaded via `bulcd.config.loader.load_config()`.
  `example.yaml` is a filled-out reference example; other files are
  real per-run configs (e.g. `cell_8c_comparison.yaml`, built to match
  a specific legacy-GUI run parameter-for-parameter for validation).
- `scripts/debug_run.py` — the actual way to run the pipeline today
  (`conda run -n bulcd python scripts/debug_run.py`). Not a real CLI
  (`bulcd/cli.py` doesn't exist yet) - a hardcoded small test AOI/config
  that prints intermediate values via cheap `.getInfo()` calls, so you
  can sanity-check the pipeline without kicking off a billed export.
  Companion scripts test real known disturbances: `scripts/debug_bb_complex_fire.py`
  (2003 B&B Complex Fire - the strongest single-pixel validation the
  pipeline has had), `scripts/debug_long_baseline_disturbance.py` (a
  major finding: long stable baselines can mask real disturbance - see
  CLAUDE.md), `scripts/debug_disturbance_map.py` (the first full-AOI
  spatial visualization, not just a single pixel), `scripts/debug_grid_cell_map.py`
  and `scripts/debug_year_of_change_map.py` (same pipeline sourced from
  the real study-area grid asset instead of a hand-picked box), and
  `scripts/export_year_disturbance_map.py` (the first real, non-preview
  GEE asset export).
- `guiBULCD.rtf` — reference copy of the current production script (the
  ~7,500-line GEE JS GUI tool this rebuild replaces). Not edited in
  place — kept for reference only.
- `mckenzeBULCD.rtf` — reference copy of the non-interactive,
  config-driven way BULC-D is invoked in production today, without the
  GUI. Closest in spirit to the target of this rebuild.
- `legacy/` — additional reference scripts pulled from the GEE Code
  Editor (current production caller + a real input parameter file).
  See `CLAUDE.md` for what these reveal and what source is still
  missing.
- `BULCD_Modernization_Vision.docx` — the design brief: goals and
  constraints for the rebuild.
- `CLAUDE.md` — detailed project context and decisions for AI-assisted
  development in this repo.

## Modernization goals

- Preserve the Bayesian updating core (not a rewrite of the method).
- Use the full Landsat archive (1984–present) as continuous evidence,
  replacing the legacy model's discrete expectation-period vs.
  target-period comparison.
- Separate the algorithm from any interface — callable programmatically,
  no Code Editor UI required.
- Expose intermediate probability/uncertainty surfaces, not just a final
  change map.
- Design for extensibility to new sensors/algorithm variants.

See `CLAUDE.md` for full architectural context and decision history.
