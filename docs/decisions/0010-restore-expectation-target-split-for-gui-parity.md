# 0010 — Restore the Expectation/Target Period Split for GUI Structural Parity

**Status:** Decided/implemented 2026-08-11. Supersedes
[0003](0003-continuous-evidence-replaces-expectation-target-split.md).

## Context

The user relayed explicit direction from their boss: the rebuild should
match the legacy GUI (`guiBULCD.rtf`) as closely as possible. A clarifying
question resolved this to mean **full structural parity**, not just
algorithm-fidelity — i.e. reproducing the legacy's actual comparison
shape, not only its formulas.

This directly conflicts with [0003](0003-continuous-evidence-replaces-expectation-target-split.md),
which collapsed the legacy's discrete "expectation period vs. target
period" comparison into one continuous, indefinite evidence stream scored
against a single global baseline fit. 0003 was not a minor implementation
choice — it was previously documented as *the* modernization's primary
objective, straight from the Vision doc ("use the full Landsat archive as
continuous evidence, not a discrete expectation-vs-target comparison").
That tension is real, not a wording accident, and is being resolved here
in favor of the boss's explicit, more recent direction — not quietly
overwritten.

Confirmed directly from the real legacy parameter file
(`legacy/BULCD-InputParameters-v5.txt` lines 61–253):
`expectationCollectionParameters` and `targetCollectionParameters` are two
structurally identical objects, each with its own per-sensor dictionary
(`L5dictionary`, `L8dictionary`, ...) carrying its own `yearsList`/
`firstDOY`/`lastDOY`/`CloudCoverThreshold` — confirmed genuinely
different between the two periods in the real example (e.g. L5's
`CloudCoverThreshold` is 45 in the expectation period vs. 15 in the
target period). `configs/cell_8c_comparison.yaml`'s own header comments
already recorded the real values a GUI run used for both periods
(expectation: 2024, DOY 74–288, cloud 70; target: 2025, DOY 74–288, cloud
70) — the schema had nowhere to put "target" at all before this change,
so that file previously faked it by extending each sensor's `last_year`
through 2026 so 2025's images would land in the one continuous stream.

## Decision

- `EvidenceConfig` now holds `expectation: EvidencePeriodConfig` and
  `target: EvidencePeriodConfig` (new dataclass, each just
  `sensors: dict[SensorCode, SensorEvidenceConfig]`), replacing the flat
  `EvidenceConfig.sensors` and the global `expectation_first_year`/
  `expectation_last_year` baseline fields from 0003.
- `day_step_size` stays one shared field — both real `dayStepSize` values
  in the legacy example are identical, and the field is repeated (not
  varied) between the two period dictionaries in every real example seen
  so far.
- `bulcd/inputs.py`'s `organize_inputs()` fits the harmonic expectation
  model against the **expectation period's** assembled evidence
  collection (unchanged logic), but now scores z-scores over the
  **target period's** assembled evidence collection only — restoring the
  legacy's literal one-shot expectation-vs-target comparison instead of
  scoring "every image in the archive, forever." `bulcd/engine.py`'s
  binning/transition-matrix lookup and `bulcd/bulc.py`'s sequential
  Bayesian fold needed no logic changes — both already just consume
  whatever `ee.ImageCollection` z-score stream `organize_inputs()` hands
  them; it's now typically a short single-season sequence instead of a
  multi-decade one.
- `SensorEvidenceConfig.first_year`/`last_year` (a continuous range) is
  kept as the per-period, per-sensor year representation rather than
  switching to the legacy's literal `yearsList` (an explicit,
  occasionally non-contiguous list of years). Every real example
  available (`BULCD-InputParameters-v5`, cell 8C) uses contiguous years,
  so this is a documented, lower-complexity generalization, not a
  confirmed structural match — flagged the same way this schema flags
  its other assumptions (e.g. `SensorEvidenceConfig`'s own docstring).

## Consequences

- **`docs/decisions/0003` is superseded, not deleted** — this project's
  decisions are an append-only log; 0003 now carries a "Superseded by
  0010" note at its top, kept as the historical record of why the
  continuous-stream design was chosen in the first place.
- **`docs/decisions/0005-recency-weighting-extension.md`'s
  `recency_factor`** was built specifically to fix a failure mode of
  *long* continuous evidence streams (many years of "confirm normal"
  evidence compounding into a lead a later genuine disturbance couldn't
  overturn). With typically-short target periods restored, that failure
  mode mostly can't occur — a target period spanning one season has
  nowhere near enough Events for the compounding effect described in
  0005 to build up. The code and default (`1.0`, off) are left
  unchanged — it's still a valid opt-in knob for a caller who
  deliberately configures a long target period — but its original
  motivating case is now unlikely for a config shaped like the real
  legacy examples.
- **`docs/decisions/0004-dampening-factor-default-0.5.md`** (the
  dampening factor's own tested value) is unaffected — it's about signal
  strength per update, not window length.
- **`bulcd/interpret.py`'s `year_of_change()`/`disturbance_mask_for_year()`
  are NOT touched by this change and now need reconsideration.** Both
  were built to search a long multi-year `classification_stack` for a
  persistent run's start year. Over a restored short single-season target
  period, that question mostly collapses to "did it change within this
  target window," a materially different (and simpler) question closer
  to what the real `afn_interpretBULCDResult` apparently does. Left as an
  explicit open follow-up — every `scripts/debug_*.py`/
  `scripts/export_year_disturbance_map.py` script that calls into
  `interpret.py` now carries an inline note flagging this.
- **Config shape changed for every existing YAML file.**
  `configs/cell_8c_comparison.yaml` and `configs/example.yaml` were
  rewritten to the new `evidence.expectation`/`evidence.target` shape;
  `configs/cell_8c_comparison.yaml`'s rewrite used the exact real values
  its own header comments already documented, so it's a mechanical
  restructuring, not new research. Every `scripts/debug_*.py` script that
  hardcoded an `EvidenceConfig(sensors=..., expectation_first_year=...)`
  was updated to the new two-period shape; several (`debug_bb_complex_fire.py`,
  `debug_disturbance_map.py`, `debug_grid_cell_map.py`,
  `debug_year_of_change_map.py`, `export_year_disturbance_map.py`) needed
  a real judgment call about what target window to test against now that
  "extend the evidence window to the present" is no longer a valid
  pattern — documented inline in each script.
  `scripts/debug_long_baseline_disturbance.py`'s entire original premise
  (demonstrating a long-continuous-stream compounding failure) is now
  structurally moot under the restored design; its docstring and config
  were rewritten to instead test "does a one-shot comparison spanning the
  known disturbance date detect it," a related but genuinely different
  question.
- **Revalidated 2026-08-11 with side-by-side renders AND a computed diff
  image, not a perfect match — a spatially coherent gap, not just
  noise.** The user compared `scripts/export_cell_8c_comparison.py`'s
  real asset output against the legacy GUI's actual render for cell 8C
  (both R=decrease/G=unchanged/B=increase RGB thumbnails, same region,
  same map background), then computed `gui_image.subtract(rebuild_image)`
  in GEE and rendered that difference with the same RGB convention.
  Eyeballing the two renders side by side, the large, contiguous,
  geographically obvious disturbance features — a dense red/blue cluster
  in the center-north of the cell, and a diagonal red string following a
  valley/road corridor near Longmire — line up closely: same locations,
  same rough shapes, and the rebuild's `unchanged` regions looked mostly
  clean with scattered red flecking.

  **The subtract() image told a different, more complete story:** a
  large-scale, roughly diagonal, spatially COHERENT split, not
  scattered noise — the west/upper-left portion of the cell is
  strongly red (GUI's `decrease` band exceeds the rebuild's there by a
  wide margin), the east/lower-right portion is strongly dark blue/navy
  (GUI's `increase` band exceeds the rebuild's), and the valley/road
  corridor near Longmire shows green (GUI's `unchanged` exceeds the
  rebuild's slightly there, consistent with both renders agreeing that
  corridor is disturbed). In plain terms: the GUI is calling substantially
  more `decrease` on the west side and more `increase` on the east side
  than the rebuild does, across large contiguous areas — not just
  isolated speckle. **Caveat on this specific diff render:** a raw
  `subtract()` with no `abs()` only shows where the GUI's per-band value
  exceeds the rebuild's (positive difference) — pixels where the rebuild
  scored HIGHER than the GUI in a band render as black, indistinguishable
  from true agreement, so this image likely under-represents total
  disagreement and only shows one direction of it.

  This is NOT attributable to a known placeholder: all three levelers
  (`dampening_factor`/`posterior_leveler`/`initializing_leveler`) in
  `configs/cell_8c_comparison.yaml` are confirmed real production values
  (see that config's own header comments), not approximations. The
  diagonal shape of the split roughly tracks the cell's own tilted
  (Landsat-swath-like) orientation, which is suggestive but NOT confirmed
  as causal.

  **Hypothesis (a) — per-sensor coverage/tiling boundary — RULED OUT
  2026-08-11.** `scripts/debug_cell_8c_sensor_coverage.py` (new) built a
  target-period-only, single-sensor `EvidencePeriodConfig` for each of
  L8/L9/S2 via the real `assemble_evidence_collection()`, counted valid
  day_step_size-bin observations per pixel, and rendered an RGB composite
  (R=L8, G=L9, B=S2 counts). Whole-cell means: L8 ≈ 11.4, L9 ≈ 12.9, S2 ≈
  26.7 valid bins (S2's higher revisit rate, as expected) — but
  spatially, the composite showed a mottled, semi-uniform pattern (S2
  dominant almost everywhere, scattered patchiness) with no boundary
  lining up with the diff's diagonal split. Sensor coverage is not the
  cause.

  Remaining, still-unconfirmed candidates at the time: (b) a real
  geographic/land-management gradient (e.g. Mount Rainier NP boundary
  near Longmire vs. more actively managed land to the west) that both
  GUI and rebuild partially detect but weight differently — not a bug, a
  sensitivity difference; (c) snow/phenology contamination correlated
  with elevation, given the wide DOY 74–288 window and Rainier's
  elevation gradient; (d) some other still-unconfirmed formula/parameter
  difference that happens to manifest as a regional bias rather than a
  uniform shift.

  **Hypothesis (c) — snow/phenology contamination correlated with
  elevation — PARTIALLY SUPPORTED 2026-08-12, and explains the EAST half
  of the gap specifically, not the whole thing.**
  `scripts/debug_cell_8c_expectation_fit_quality.py` (new) called
  `organize_inputs()` directly (real, unchanged) and rendered
  `expectation_r2`, `expectation_residual_stddev`, and the target
  period's mean z-score spatially, plus elevation/aspect from
  `USGS/SRTMGL1_003`, all over the same cell 8C region — then compared
  west-half vs. east-half means (split at the AOI's own longitude
  median) and inspected the rendered thumbnails directly.

  Numbers (west / east):
  - `expectation_r2`: 0.360 / 0.397 — no meaningful difference.
  - `expectation_residual_stddev`: 0.054 / 0.073 — east ~35% noisier.
  - mean target-period z-score: −0.032 / −0.138 — both negative (the
    rebuild's own fit skews slightly "decrease"-leaning cell-wide), but
    the east is ~4× more negative than the west.
  - elevation: 1012m / 1326m — east is real, substantially higher
    terrain (~30%), confirmed by the rendered DEM thumbnail showing a
    branching valley/ridge system, not just two flat aggregate numbers.
  - aspect: 174° / 187° — both south-facing, essentially identical; NOT
    a differentiator.

  The rendered `mean_zscore` thumbnail shows this isn't just an artifact
  of the west/east split point — the right two-thirds of the cell is
  visibly, coherently blue (negative z-score) while the left third is
  closer to neutral/faint red, consistent with the numeric gap. **This
  directly explains the EAST side of the original GUI-vs-rebuild diff**:
  a more negative z-score there pushes the rebuild's own classification
  toward `decrease` and away from `increase`, which is exactly the
  direction of the GUI-minus-rebuild diff on the east side (GUI scores
  more `increase` there than the rebuild does — i.e. the rebuild is
  under-calling `increase` in the east, and a real negative z-score bias
  in the rebuild's own output is a sufficient, demonstrated cause).

  **It does NOT explain the WEST side.** There, the rebuild's own mean
  z-score is close to neutral (−0.032, not positive), so there's no
  comparable bias pushing the rebuild away from `decrease` — the rebuild
  simply isn't detecting as strong a `decrease` signal in the west as
  the GUI apparently does. This is a different, still-open question:
  either a real sensitivity/scale difference from something not yet
  identified, or the GUI's own expectation fit (unknown internals —
  possibly a wider/multi-year baseline, unlike this comparison's
  deliberately single-year 2024 window) picks up a real west-side
  disturbance signal this rebuild's fit misses entirely, not just
  under-weights.

  Correlationally, higher elevation lining up with both higher
  `residual_stddev` and a more negative z-score bias in the same region
  is consistent with hypothesis (c)'s snow/phenology mechanism (fitting
  a single-year, partial-DOY-window — 74–288, not a full calendar year —
  harmonic model is inherently more exposed to a bad early/late-season
  snow read at higher elevation, which would bias both the fit's
  residual spread and, if the 2025 target period's early-DOY images
  happened to have different snow timing than 2024's, the resulting
  z-score). This is real, aligned evidence, not proof of the underlying
  mechanism — worth stating precisely: elevation correlating with the
  z-score bias is confirmed; snow/phenology as the specific physical
  cause of that correlation is a plausible, unconfirmed mechanism.

  Treat cell 8C as: the EAST-side portion of the diagonal gap has a
  real, demonstrated cause inside this rebuild's own math (an
  elevation-correlated negative z-score bias); the WEST-side portion
  remains open, and is not sensor coverage, not a leveler placeholder,
  and not (by itself) the same z-score-bias mechanism.
