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
- **Not yet done:** revalidating `configs/cell_8c_comparison.yaml`
  against the real GUI's Console output under the restored split. Every
  prior cell-8C validation (`docs/decisions/0009` and earlier) was run
  against the continuous-stream design; the restructured config uses the
  same real parameter values, but the actual classification output
  hasn't been re-checked against a live Earth Engine run since this
  change landed.
