"""Quantified GUI-vs-rebuild diff for cell 8C, AFTER the DOY-boundary
evidence fix (docs/findings.md's "2026-08-12: RESOLVED" entry;
docs/decisions/0010's matching entry). Every prior comparison in this
investigation was either a side-by-side visual (subjective) or a raw
`subtract()` render (visual, and only shows one sign of disagreement,
per that entry's own caveat). This is the first actual pixel-statistics
pass: mean absolute error, RMSE, per-band correlation, and
argmax-classification agreement rate, computed via `reduceRegion()`
over the whole cell.

Uses the two real, already-exported assets confirmed live in
`projects/bulcd-python-rebuild/assets/` (not a fresh run):
  - GUI:     Version-V53e-4-Final-BULC-Probabilities_gui3
             (updateTime 2026-08-12T17:57:21Z - the GUI export the user
             loaded for the "much closer!" side-by-side verdict the same
             day)
  - Rebuild: bulcd_cell8c_comparison_final_probabilities
             (updateTime 2026-08-12T20:03:53Z - task X6FTZKHMKKEQMYVAYCNE4WHD,
             the post-fix re-export)
Band mapping: GUI's probCls1/probCls2/probCls3 correspond to the
customTransitionMatrix's own column order (drop/burn, no change,
increase/regrowth - see CLAUDE.md's "Reference papers" section), i.e.
decrease/unchanged/increase - the same order/convention every prior
RGB-thumbnail comparison in this investigation already assumed.

Usage:
    conda run -n bulcd python scripts/debug_cell_8c_postfix_quantified_diff.py
"""

import ee

ee.Initialize(project="bulcd-python-rebuild")

from bulcd.config.loader import load_config

CONFIG_PATH = "configs/cell_8c_comparison.yaml"
GUI_ASSET = "projects/bulcd-python-rebuild/assets/Version-V53e-4-Final-BULC-Probabilities_gui3"
REBUILD_ASSET = "projects/bulcd-python-rebuild/assets/bulcd_cell8c_comparison_final_probabilities"
BAND_NAMES = ["decrease", "unchanged", "increase"]

config = load_config(CONFIG_PATH)
region = ee.Geometry.Polygon([config.study_area.aoi_coordinates])

gui_image = ee.Image(GUI_ASSET).select(
    ["probCls1", "probCls2", "probCls3"], BAND_NAMES
)
rebuild_image = ee.Image(REBUILD_ASSET).select(BAND_NAMES)

abs_diff = gui_image.subtract(rebuild_image).abs().rename(
    [f"abs_diff_{b}" for b in BAND_NAMES]
)
sq_diff = gui_image.subtract(rebuild_image).pow(2).rename(
    [f"sq_diff_{b}" for b in BAND_NAMES]
)

reduce_kwargs = dict(
    reducer=ee.Reducer.mean(),
    geometry=region,
    scale=config.study_area.scale,
    crs=config.study_area.crs,
    maxPixels=1e10,
)

mae = abs_diff.reduceRegion(**reduce_kwargs).getInfo()
mse = sq_diff.reduceRegion(**reduce_kwargs).getInfo()

print("=== Mean absolute error per band (0-1 probability scale) ===")
for b in BAND_NAMES:
    print(f"  {b}: {mae[f'abs_diff_{b}']:.4f}")
print(f"  overall (mean across bands): {sum(mae.values()) / 3:.4f}")

print("\n=== RMSE per band ===")
for b in BAND_NAMES:
    print(f"  {b}: {mse[f'sq_diff_{b}'] ** 0.5:.4f}")

print("\n=== Per-band Pearson correlation (GUI vs rebuild) ===")
for b in BAND_NAMES:
    paired = gui_image.select([b], ["gui"]).addBands(
        rebuild_image.select([b], ["rebuild"])
    )
    corr = paired.reduceRegion(
        reducer=ee.Reducer.pearsonsCorrelation(),
        geometry=region,
        scale=config.study_area.scale,
        crs=config.study_area.crs,
        maxPixels=1e10,
    ).getInfo()
    print(f"  {b}: r = {corr['correlation']:.4f}")

gui_argmax = gui_image.toArray().arrayArgmax().arrayGet([0]).rename("gui_class")
rebuild_argmax = rebuild_image.toArray().arrayArgmax().arrayGet([0]).rename(
    "rebuild_class"
)
agreement = gui_argmax.eq(rebuild_argmax).rename("agree")
agreement_stats = agreement.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=region,
    scale=config.study_area.scale,
    crs=config.study_area.crs,
    maxPixels=1e10,
).getInfo()
print(f"\n=== Argmax classification agreement rate ===")
print(f"  {agreement_stats['agree'] * 100:.1f}% of pixels agree on winning class")

for name, image in [("abs_diff", abs_diff), ("disagreement_mask", agreement.Not())]:
    if name == "abs_diff":
        url = image.select(["abs_diff_decrease", "abs_diff_unchanged", "abs_diff_increase"]).getThumbURL(
            {"region": region, "dimensions": 512, "min": 0, "max": 0.5}
        )
    else:
        url = image.getThumbURL(
            {"region": region, "dimensions": 512, "min": 0, "max": 1, "palette": ["000000", "ff0000"]}
        )
    print(f"{name} thumbnail: {url}")
