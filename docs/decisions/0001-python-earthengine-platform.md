# 0001 — Platform: Python + `earthengine-api`

**Status:** Decided 2026-07-28

## Context

The legacy BULC-D implementation is a GEE JavaScript Code Editor script.
A prior meeting with Robert (the original BULC-D author) surfaced a wish
for a "BULC-D python tool."

## Decision

The rebuild targets **Python + `earthengine-api`**, not GEE JavaScript.
The algorithm still executes server-side on Earth Engine — this is Python
code building an EE computation graph, same pattern as
`gee_export/export_timeseries.py` in the sibling GeoTimeSeries project.
This is a client-language choice, not a move off Earth Engine.

## Consequences

Unblocked scaffolding new code in `bulcd/` immediately. All engine code
(`bulc.py`, `engine.py`, `inputs.py`) builds `ee.Image`/`ee.ImageCollection`
objects via the Python client, so it still needs a live, initialized EE
session to test meaningfully — see `CLAUDE.md`'s "Current code state" for
what's pure-Python-testable vs. not.
