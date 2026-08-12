"""Diagnostic for the cell 8C GUI-vs-rebuild diff investigation (see
docs/decisions/0010's "Revalidated 2026-08-11..." entry and
docs/findings.md's matching entry): the user directly compared the real
GUI render against the rebuild's render side by side (not just the
subtract() diff) and found the mismatch isn't a clean west/east split -
it's a broad reduction in scattered `decrease` (red) speckle across much
of the cell in the rebuild, while the known discrete features (the
center disturbance cluster, the Longmire valley/road corridor string)
match well between the two. This ruled out the west/east framing every
prior diagnostic in this investigation was built around.

New hypothesis this tests: the rebuild's `final_probabilities` is a
SNAPSHOT of the posterior after only the LAST target-period Event.
`posterior_leveler`/`dampening_factor` pull every step back toward the
prior - so a pixel that classified `decrease` at some Event in the
MIDDLE of the target period, then reverted to `unchanged` by the last
Event, would show up as `unchanged` in `final_probabilities` even
though it had real, transient `decrease` evidence. If that transient
signal is common, it would look exactly like this: widespread scattered
`decrease` in a "was this pixel ever flagged" view that's much less
speckled in a "final Event only" view - independent of west/east,
elevation, or anything spatial.

Uses the real, unchanged `engine.run_bulcd()` (not a re-implementation)
to get `classification_stack` (per-Event argmax labels) and compares:
  - "ever decrease": did this pixel classify as `decrease` at ANY
    target-period Event (ee.Reducer.anyNonZero() over class==0 masks)?
  - "final decrease": is `decrease` the argmax of `final_probabilities`
    (the same thing scripts/run_cell_8c_comparison.py already renders)?
If "ever" is visibly more widespread/speckled than "final" - especially
away from the two known discrete features - that's a real, demonstrated
cause distinct from every hypothesis tested so far in this investigation.

Usage:
    conda run -n bulcd python scripts/debug_cell_8c_transient_vs_final_decrease.py
Prints URLs; fetching them requires an authenticated request (see other
scripts/debug_*.py docstrings for the pattern).
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd import engine
from bulcd.config.loader import load_config

CONFIG_PATH = "configs/cell_8c_comparison.yaml"

config = load_config(CONFIG_PATH)
print(f"Loaded {CONFIG_PATH}")

result = engine.run_bulcd(config)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])

# "class" band: 0=decrease, 1=unchanged, 2=increase (bulc.py's
# _argmax_label() over bands in [decrease, unchanged, increase] order).
ever_decrease = result.classification_stack.map(lambda img: img.eq(0)).reduce(
    ee.Reducer.anyNonZero()
).rename("ever_decrease")

final_decrease = (
    result.final_probabilities.select(["decrease", "unchanged", "increase"])
    .toArray()
    .arrayArgmax()
    .arrayGet([0])
    .eq(0)
    .rename("final_decrease")
)

n_events = result.classification_stack.size().getInfo()
print(f"Target-period Event count (classification_stack size): {n_events}")

for name, image in [("ever_decrease", ever_decrease), ("final_decrease", final_decrease)]:
    url = image.getThumbURL(
        {"region": region, "dimensions": 512, "min": 0, "max": 1, "palette": ["000000", "ff0000"]}
    )
    print(f"{name} thumbnail: {url}")

# Whole-cell reduceRegion() over the full 61-step fold hits "User memory
# limit exceeded" for a synchronous getInfo() call (unlike getThumbURL's
# server-side tiled rendering above) - skip exact stats, the thumbnails
# are the primary evidence here.
