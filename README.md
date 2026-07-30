# BULC-D Rebuild

Modernization of **BULC-D** (Bayesian Updating of Land Cover Detection), a
probabilistic forest-change-detection algorithm originally built as a
Google Earth Engine (GEE) JavaScript Code Editor tool.

## Status

Early implementation, actively in progress (as of 2026-07-29). Config
handling and continuous-evidence assembly (Landsat 5/7/8/9) are real and
tested. The Bayesian updating core itself is being written now, against
a credible published reconstruction of the legacy math — see "Reference
papers" below — since the original GEE JavaScript source for that core
still hasn't been obtained. See `CLAUDE.md`'s "Current code state" for
the exact, up-to-date breakdown of what's real vs. stubbed vs. unverified.

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
  - `bulcd/inputs.py` — continuous multi-sensor evidence assembly
    (real, Landsat 5/7/8/9) plus the z-score/expectation-model layer.
  - `bulcd/bulc.py` — the generic, index-agnostic Bayesian updating
    engine (update table → Bayes formula → dampening → posterior), plus
    an optional, off-by-default recency-weighting extension
    (`discount()`) not found in the reference papers — see CLAUDE.md
    "Recency weighting".
  - `bulcd/engine.py` — BULC-D-specific orchestration gluing the above
    two together (bins the z-score stream, looks up the transition
    matrix, runs the engine).
- `scripts/debug_run.py` — the actual way to run the pipeline today
  (`conda run -n bulcd python scripts/debug_run.py`). Not a real CLI
  (`bulcd/cli.py` doesn't exist yet) - a hardcoded small test AOI/config
  that prints intermediate values via cheap `.getInfo()` calls, so you
  can sanity-check the pipeline without kicking off a billed export.
  Two companion scripts test real known disturbances: `scripts/debug_bb_complex_fire.py`
  (2003 B&B Complex Fire - the strongest validation the pipeline has had)
  and `scripts/debug_long_baseline_disturbance.py` (a major finding: long
  stable baselines can mask real disturbance at the default dampening
  factor - see CLAUDE.md).
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
