"""Runs the real, config-driven BULC-D pipeline for the cell 8C vs.
legacy-GUI comparison (see CLAUDE.md "Legacy-GUI parameter matching +
Sentinel-2 support" and "Real production BULC-D parameters").

Unlike every other scripts/debug_*.py entry point, this one loads its
config via bulcd.config.loader.load_config() instead of hardcoding a
BULCDConfig(...) in Python - see configs/cell_8c_comparison.yaml for the
actual parameters, transcribed from a real legacy GUI run.

STALE NOTE, corrected 2026-08-11: this docstring used to warn that
dampening_factor was still bulc.py's single-scalar placeholder (0.5),
not production's real three-"leveler" mechanism. That was true before
BULC-Minimal-Module-107's source was obtained (2026-08-10) - as of that
fix, configs/cell_8c_comparison.yaml's dampening_factor/posterior_leveler/
initializing_leveler ARE the real matched production values (see that
config's own header comments), not placeholders. Comparison against the
real GUI under the restored expectation/target split
(docs/decisions/0010) found the outputs close but not identical - see
docs/decisions/0010's "Revalidated 2026-08-11" note; the remaining gap's
cause is unidentified, not a known dampening approximation.

custom_transition_matrix, evidence window, DOY, sensors, modality,
sensitivity, and all three levelers in the config ARE the real matched
production values.

Uses ee.Image.getThumbURL() - a synchronous preview render, NOT
Export.image.toAsset/toDrive - fine for a first-look visual comparison,
not a production export.

Usage:
    conda run -n bulcd python scripts/run_cell_8c_comparison.py
Prints a URL; fetching it requires an authenticated request (see other
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

# Same R=decrease/G=unchanged/B=increase convention as the legacy caller's
# Map.addLayer(finalBulcProbs, ...) and scripts/debug_disturbance_map.py.
url = result.final_probabilities.select(["decrease", "unchanged", "increase"]).getThumbURL(
    {"region": region, "dimensions": 512, "min": 0, "max": 1}
)
print("Cell 8C final_probabilities (R=decrease, G=unchanged, B=increase):")
print(url)
