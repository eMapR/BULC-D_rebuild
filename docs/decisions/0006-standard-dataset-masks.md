# 0006 — Standard Public Datasets as Water/Forest Mask Substitutes

**Status:** Water mask decided/implemented 2026-07-30; forest mask
decided/implemented 2026-07-30 (same day, later)

## Context

The legacy pipeline unconditionally applies `afn_waterMask()` before
displaying/exporting results (`legacy/BULCD-Caller-Current.txt`), but we
don't have that function's source. Separately, `StudyAreaConfig.forest_mask_asset`
existed as an unused schema field since the project's early scaffold
stage — inspecting `guiBULCD.rtf` directly (grepped for
forest/treecover/hansen/canopy) confirmed the legacy actually has **zero**
forest-mask logic anywhere, so there's no legacy behavior to match on
that front, only a config field that was never wired up.

Both gaps were found empirically: water bodies first appeared
misclassified as "increase" in the first full-AOI visualization
(`docs/findings.md` "Disturbance map"); false "change" near mountain tops
above the tree line appeared later in a real export
(`docs/findings.md` "Non-forest mask").

## Decision

Use standard public Earth Engine datasets as reasonable substitutes, not
reconstructions of the legacy's real (unavailable) logic:

- **Water:** JRC Global Surface Water (`JRC/GSW1_4/GlobalSurfaceWater`,
  band `occurrence`, threshold >50%). Wired in via
  `StudyAreaConfig.mask_water` (default `True`, matching the legacy's
  unconditional behavior; can be disabled).
- **Forest:** if the caller supplies `forest_mask_asset`, treat it as a
  boolean image (nonzero = forest); otherwise fall back to Hansen Global
  Forest Change's `treecover2000` band
  (`UMD/hansen/global_forest_change_2025_v1_13`), thresholded at 10%
  canopy cover (FAO's common minimum-canopy "forest" definition). Wired
  in via `StudyAreaConfig.mask_non_forest` (new field, default `True`).
- New public helper `engine.study_area_mask(config)` returns the combined
  water+forest mask (or `None` if both toggles are off), for callers that
  bypass `run_bulcd()`'s automatic `final_probabilities` masking (e.g.
  code reading `classification_stack`/`lof_zscore` directly).

## Consequences

Both are **verified-partial fixes, not verified-complete** — see
`docs/findings.md` "Disturbance map" (water: most, not all, of the
original "increase" speckling turned out not to be water at all — cause
still not identified) and "Non-forest mask" (forest mask fixed the
treeline artifact; also surfaced and fixed a second bug, that
`disturbance_2025`'s export bypassed masking entirely since it read
un-masked collections directly rather than routing through
`run_bulcd()`). Anyone adding a new code path that reads
`classification_stack`/`probability_stack`/`lof_zscore` directly must
remember to call `engine.study_area_mask()` explicitly — it is not
automatic outside of `run_bulcd()`'s own `final_probabilities` output.
