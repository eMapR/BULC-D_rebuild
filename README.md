# BULC-D Rebuild

Modernization of **BULC-D** (Bayesian Updating of Land Cover Detection), a
probabilistic forest-change-detection algorithm originally built as a
Google Earth Engine (GEE) JavaScript Code Editor tool.

## Status

Pre-implementation / early scaffold. The Bayesian updating core is
preserved from the legacy algorithm; everything around it — language,
parameter handling, GUI vs. programmatic use — is being rebuilt.

**Platform decision (2026-07-28):** Python + [`earthengine-api`](https://developers.google.com/earth-engine/guides/python_install),
not GEE JavaScript. The algorithm still runs server-side on Earth Engine
as a computation graph — this is a client-language choice, not a move off
GEE.

## Contents

- `bulcd/` — the new Python package (in progress).
  - `bulcd/config/schema.py` — typed configuration schema (draft) for
    study area, sensors, temporal window, reduction band, advanced BULC
    tuning, and export settings.
- `guiBULCD.rtf` — reference copy of the current production script (the
  ~7,500-line GEE JS GUI tool this rebuild replaces). Not edited in
  place — kept for reference only.
- `mckenzeBULCD.rtf` — reference copy of the non-interactive,
  config-driven way BULC-D is invoked in production today, without the
  GUI. Closest in spirit to the target of this rebuild.
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
