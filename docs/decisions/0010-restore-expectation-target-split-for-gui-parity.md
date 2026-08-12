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
  the GUI apparently does. This is a different, still-open question.

  **"Wider/multi-year GUI baseline" candidate — RULED OUT 2026-08-12.**
  Checked `guiBULCD.rtf` directly for the Expectation Period widget's
  actual default (both the per-sensor tabs, e.g. `l8years_t` ~line 2948,
  and the "Cross-Sensors" panel actually used for cell 8C's real run,
  `csyears_t` ~line 1042): it's a bank of individual year checkboxes
  (2013–2025) that are ALL `ui.Checkbox(year, false)` — every one
  unchecked — with the backing list (`chosen`/`crossSensorDictionary["year"]`)
  initialized to `[]`. **There is no built-in default expectation-year
  range at all** — the GUI ships with nothing selected; the user must
  explicitly check which year(s) apply, and could in principle pick a
  multi-year or even non-contiguous set. But the real cell 8C run's
  actual selection was already pulled directly from the GUI's own
  Console output (`BULCargumentDictionaryPlus`, see this config's header
  comment): a single year, 2024 — exactly what
  `cell_8c_comparison.yaml` already uses. So there's no divergence to
  find here: the rebuild already matches the real run's actual
  expectation-year selection, not a guessed default. This candidate is
  closed; the west-side gap's cause is still unidentified.

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

  **Hypothesis (b) — land-management gradient — CHECKED 2026-08-12: the
  geographic feature is real, but doesn't add an independent cause
  beyond (c).** `scripts/debug_cell_8c_land_management_gradient.py`
  (new) checked two things over the same cell: (1) `WCMC/WDPA/current/polygons`
  (World Database on Protected Areas), filtered to features intersecting
  the cell - found Mount Rainier NP plus three adjacent wilderness areas
  (Goat Rocks, Tatoosh, William O. Douglas) genuinely cross the AOI; (2)
  `UMD/hansen/global_forest_change_2023_v1_11`'s `lossyear` band, a
  real, independent (not BULC-D-derived) historical-forest-loss dataset,
  as a proxy for "is this landscape under active timber management."

  West / east: protected-area fraction 0.149 / 0.679 (the east half is
  genuinely, substantially more protected wilderness - a real land-
  status gradient, confirmed, not hypothetical), any-forest-loss-2001-2023
  fraction 0.021 / 0.043 (east is actually HIGHER, not lower). The
  rendered protected-area-mask thumbnail shows a real boundary shape,
  including a valley-shaped unprotected notch cutting into the protected
  block that plausibly corresponds to the same Longmire road corridor
  both the GUI and rebuild agree is disturbed (mentioned in the
  side-by-side render comparison above) - not a coincidence, a
  real road running through there. The Hansen thumbnail's largest
  contiguous recent-loss cluster (dark purple, center) lines up with the
  "dense disturbance cluster in center-north" both renders already
  agreed on - independent confirmation that's a real event, not a
  pipeline artifact.

  **This does NOT support the original "actively managed land" framing**:
  if the west side were the more heavily logged/managed one, its
  Hansen-loss fraction should be higher, not lower (0.021 vs 0.043 - the
  opposite). The protection-status gradient is real and roughly aligned
  with the cell's spatial layout, but BULC-D's algorithm has no input
  that's aware of land ownership or protection status - the plausible
  mechanism is that "protected wilderness" here is simply a real-world
  proxy for the SAME elevation/terrain gradient already identified in
  hypothesis (c) (higher elevation → more natural disturbance regime →
  noisier/biased z-score), not a separate, independent cause. Treat
  hypothesis (b) as folded into (c) rather than a distinct explanation:
  the geographic gradient is confirmed real, but doesn't add a new
  causal mechanism beyond the elevation-correlated z-score bias already
  found.

  **Evidence-density (not tiling, not bias) candidate — RULED OUT
  2026-08-12.** `scripts/debug_cell_8c_target_event_density.py` (new)
  checked a different question than the sensor-coverage diagnostic
  above (which tested per-sensor tiling patterns in isolation): does the
  COMBINED, cross-sensor target-period Event count (how many of the 61
  `day_step_size=3` bins got a real observation from ANY enabled
  sensor, after cloud masking - counted via `assemble_evidence_collection()`
  directly, the actual real Event stream `organize_inputs()` folds
  through the Bayesian engine, not a proxy) differ west vs. east? This
  mattered because `initializing_leveler=0.7` gives every pixel a
  starting prior biased toward `unchanged` ([0.1, 0.8, 0.1], not flat
  uniform) - fewer real Events means fewer chances to pull a pixel away
  from that prior, regardless of how extreme any individual z-score is.
  Result: west 34.48 / east 34.89 valid Events (out of 61 total bins) -
  essentially identical, ~1% apart. The rendered thumbnail is uniformly
  mottled with no diagonal pattern resembling the diff. Evidence density
  is not the cause.

  **2026-08-12 correction: the west/east framing was wrong. The user
  directly compared the real GUI render against the rebuild's render
  side by side (not just the computed `subtract()` diff) and found the
  mismatch is NOT a clean spatial split** - it's a broad reduction in
  scattered `decrease` (red) speckle across much of the cell in the
  rebuild, while the two known discrete features (the center disturbance
  cluster, the Longmire valley/road corridor string) match well between
  GUI and rebuild. Every diagnostic above that assumed a west-half/
  east-half structure (sensor coverage, GUI expectation-year default,
  land-management gradient, target-period evidence density) is still
  factually correct on its own terms, but was answering a framing of the
  problem that doesn't match what's actually visible when the two
  renders are compared directly.

  **Major finding, `scripts/debug_cell_8c_transient_vs_final_decrease.py`
  (new): `final_probabilities` is a heavily-smoothed LAST-EVENT-ONLY
  snapshot that discards most real, transient `decrease` signal that
  occurred earlier in the target period.** Using the real, unchanged
  `engine.run_bulcd()`, compared "did this pixel ever classify as
  `decrease` at any of the target period's 61 Events" (via
  `classification_stack`) against "is `decrease` the argmax of
  `final_probabilities`" (the single last-Event snapshot - what every
  prior comparison in this investigation, and the real GUI-vs-rebuild
  render comparison, actually used). Result: `ever_decrease` is a dense,
  widespread, branching pattern covering a large fraction of the cell;
  `final_decrease` is sparse, confined mostly to the two known discrete
  features - visually, `ever_decrease`'s density and character is a much
  closer match to the real GUI render than `final_decrease` (the
  rebuild's actual output) is.

  Mechanism: `posterior_leveler=0.9` (a confirmed real production value)
  dampens the posterior toward the prior after EVERY real Event, not
  just once. With ~34 real (non-placeholder) Events per pixel on average
  in the target period (see the evidence-density check above), that
  compounds to roughly `0.9^34 ≈ 3%` of an early Event's influence
  surviving to the final Event. A pixel that genuinely showed `decrease`
  partway through the target period gets almost entirely smoothed back
  toward `unchanged` by the time the sequence ends - even though the
  underlying signal was real. This directly explains a BROAD, spatially
  non-localized reduction in visible `decrease`, matching what the user
  observed far better than any west/east-framed hypothesis did.

  **Open question, not yet resolved:** if GUI's own render is subject to
  the same confirmed real `posterior_leveler=0.9` compounding over a
  comparable number of real Events, it should show similarly heavy
  washing-out of transient signal by its own last Event - yet the real
  GUI render is visibly MORE speckled/red than the rebuild's, not less.
  Either (a) the GUI's displayed/exported image isn't literally "state
  after the single last target-period Event" the way this rebuild's
  `final_probabilities` is (a genuine definitional mismatch, not a math
  bug), or (b) something about how this rebuild orders/counts/applies
  Events differs from production's real per-step process in a way that
  causes MORE compounding decay here than production actually
  experiences (a real math difference, not yet identified) - e.g. this
  rebuild's exact Event count/ordering hasn't been cross-checked against
  a real GUI Console dump the way the levelers themselves were. Given
  `legacy/BULCD-Caller-Current.txt`'s confirmed `finalBulcProbs.select(0/1/2)`
  usage, "final" does appear to mean the same single-snapshot concept on
  both sides - which points toward (b), but this is not confirmed.

  This finding likely supersedes the west/east framing as the dominant
  explanation for cell 8C's GUI-vs-rebuild gap. The west/east-specific
  hypotheses above remain individually correct (each really was ruled
  out on its own terms) but are now understood as investigating a
  secondary effect (the elevation-correlated z-score bias, still real)
  layered on top of this larger, spatially-broad final-snapshot-vs-
  transient-signal issue.
