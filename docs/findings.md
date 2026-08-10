# Findings

A dated, chronological lab notebook: validation runs, experiments, bugs
found and fixed, dead ends — the play-by-play behind this project's
decisions and current state. Entries are append-only and in date order;
don't edit past entries to "correct" them in place — add a follow-up
entry instead, the way several sections below already do (e.g.
"Non-forest mask" following up on "Disturbance map").

See `decisions/` for the extracted "why we chose X" decisions this log
led to, and `../CLAUDE.md` for current stable project state (what's
implemented today, requirements, environment).

## First live-EE verification (2026-07-29) — and a default worth changing

With `bulcd-python-rebuild` working, `bulc.py`/`engine.py`/`organize_inputs()`
were run against real Earth Engine for the first time: a small AOI in the
eastern Cascades (WA), Landsat 8, 2014–2021, NBR, expectation window
2014–2016, Willis (2022)'s worked NBR12 transition matrix. **Nothing
crashed** — evidence assembly, the harmonic regression fit, z-scoring, bin
lookup, and the full 61-step Bayesian fold all executed end to end. Two
concrete sanity checks passed: evidence count (61 Landsat 8 scenes) was
reasonable for the date range, and the z-score of an image *inside* the
baseline window came back ≈0 (0.014), exactly as expected — a real,
working confirmation that `organize_inputs()`'s baseline-scoring logic
is behaving correctly, not just failing to crash.

**Finding: `dampening_factor: 1.0` (the schema's default at the time, i.e.
no dampening) produces extreme overconfidence over many sequential Events** —
exactly the failure mode Cardille & Fortin (2016) section 4.6 describes
as the reason they added the dampening factor in the first place (their
own example run used `d=0.5`, not `d=1.0`). At the same test pixel, one
run each with `d=1.0` and `d=0.5`, all else identical:

```
d=1.0: {decrease: 4.31e-58, unchanged: 1.0,          increase: 1.35e-48}
d=0.5: {decrease: 9.42e-10, unchanged: 0.99999999937, increase: 5.32e-09}
```

Both land on the same classification ("unchanged" — plausibly correct;
this pixel likely never burned across the test period), but the *magnitude*
of confidence differs by ~48 orders of magnitude. Repeated multiplicative
Bayesian updates over 61 consecutive Events compound relative differences
in the transition matrix's rows without dampening, overshooting into
values at the edge of float64 precision — not yet a NaN/underflow risk
here, but a real concern for a full multi-decade run with hundreds of
Events instead of 61.

**Applied:** see [decisions/0004](decisions/0004-dampening-factor-default-0.5.md)
— `BULCAdvancedParams.dampening_factor`'s default changed from `1.0` to
`0.5`.

## Known-burn validation (2026-07-29): the 2003 B&B Complex Fire

The first live test above only exercised an "unchanged" (never-burned)
pixel. To validate the "decrease/burn" path, the pipeline was run against
a real, known-burned point (user-supplied coordinates,
`-121.90249210117729, 44.53142096854933`, central Oregon Cascades) —
identified as inside the **2003 B&B Complex Fire** (ignited Aug 15, 2003).

Two dead ends before the working test, both informative:
- First attempt used only Landsat 8 (2013+) with a 2014–2018 baseline.
  Result: mostly *positive* z-scores in later years (0.7–1.25), i.e.
  apparent regrowth, not a burn signal — because a fire in 2003 predates
  Landsat 8 entirely. An L8-only evidence window can only see the tail
  end of recovery, never the actual transition. Fixed by enabling
  **Landsat 5** (2000–2012) to reach back before the fire — the first
  real exercise of the "use the full Landsat archive," not just L8, and
  a concrete illustration of why that modernization goal matters in
  practice, not just in principle.
- A separate full-year-DOY test (unrelated pixel, see the dampening-factor
  test above) surfaced wild winter z-scores (as extreme as ±6.8) from
  snow reflectance contamination — matching Willis (2022)'s own discussion
  section almost exactly. Growing-season-only DOY filtering (roughly
  May–Oct) avoids this and is the right default, not full-year.

With L5 (2000–2012, pre-fire baseline 2000–2002, R²=0.49) + L8
(2014–2023) combined and growing-season DOY filtering, the z-score
trajectory is unambiguous:

```
2003-08-18 (3 days post-ignition): zscore=-1.61
2003-09-26:                        zscore=-5.88
2004 through 2023, every year:     zscore between -2.8 and -6.3 (never recovers)
```

`engine.run_bulcd()`'s final classification at that point:
`decrease=0.9999`, `unchanged=0.000076`, `increase=2.6e-28` — confident,
correct. This is the strongest end-to-end validation the pipeline has
had: a real pre-fire baseline, a real fire, and a correct answer, with
the exact ignition date visible in the z-score jump. Still only one
pixel, one fire, one transition matrix (Willis's NBR12 example, not a
verified production default) — not a substitute for broader validation.

## Moderate-severity test (2026-07-29): the bin/matrix mechanism working as designed

A second point was picked via MTBS burn-severity data (`USFS/GTAC/MTBS/
annual_burn_severity_mosaics/v1`, band `Severity`, classes 1=Unburned-Low,
2=Low, 3=Moderate, 4=High), ~2.5km from the B&B Complex point above,
classified as MTBS severity 3 ("Moderate"). Note: MTBS actually classifies
the *original* B&B point above as severity 2 ("Low"), despite its
persistent -3 to -6 z-scores for 20 years — a discrepancy not
investigated further, flagged here in case it matters later.

Counterintuitive at first glance: the moderate-severity point's raw
z-scores were *more* extreme (down to -9.6) than the original point's
(-5.88), yet its final classification was far less confident
(`decrease=0.29, unchanged=0.71`, vs. the original's `decrease=0.9999`).
Explained by checking the actual bin distribution at each pixel
(`bulcd/engine.py`'s `_bin_zscore()`, using the default `bin_cuts` whose
outermost cuts are ±2 - any z beyond that collapses into the same
bin regardless of magnitude, so -2.1 and -9.6 get identical treatment):

```
                        bin 1 (extreme drop)   bins 2-4 (mild/moderate)
low-severity (orig):    155/186 valid (83%)    13
moderate-severity:      116/194 valid (60%)    51
```

Bins 3-4 in Willis's transition matrix actually favor "unchanged" over
"decrease" (`[0.07,0.12,0.02]`, `[0.03,0.16,0.02]`). The moderate point's
history has meaningfully more of its 20 years sitting in those
intermediate bins, diluting the accumulated evidence. This is the
pipeline correctly reflecting a real difference in how *consistently*
each pixel stayed changed over decades, not reacting to peak z-score
magnitude (which the ±2 bin ceiling makes irrelevant beyond that point
anyway) - reassuring, face-valid behavior.

## Major finding (2026-07-29): long stable baselines can mask real disturbance

A third point (user-supplied, picked via LandTrendr for a high-magnitude
disturbance, `-122.0582, 44.4823`) exposed a real structural limitation,
not a bug. R²=0.62 (the best fit of any test point). Z-scores sit near
zero for **14 years** (2000-2014), then crash to -6.9 in June 2015 and
stay between -5 and -10.9 for the following **9 years** - about as
unambiguous a disturbance signal as this pipeline will ever see.

At the default `dampening_factor=0.5`, the final classification was
`unchanged=0.9999999999994` - practically certain "no change," despite
nine years of extreme, sustained contrary evidence. A dampening sweep at
the same pixel:

```
d=0.5:  unchanged=0.99999999999936
d=0.2:  unchanged=0.9997
d=0.1:  unchanged=0.977   decrease=0.023
d=0.05: unchanged=0.846   decrease=0.140
d=0.02: unchanged=0.589   decrease=0.291   increase=0.120
```

**Mechanism:** Willis's transition matrix's "unchanged" bins (5/6) are
*more* lopsided (`[0.015, 0.2, 0.01]`, a 13:1 ratio) than its "decrease"
bin (1) is (`[0.16, 0.11, 0.02]`, only 1.5:1). Under sequential Bayesian
updating (Cardille & Fortin 2016 Eq. 2), each observation's tilt
compounds multiplicatively with every prior observation. Fourteen years
of mild-but-consistent "confirm normal" evidence (~90 observations, each
tilting hard toward unchanged) built up such a lead that nine years of
dramatic "this changed" evidence (~130 observations, each tilting only
mildly toward decrease) can't fully overturn it at `d=0.5` - it takes
very aggressive dampening (`d≈0.02-0.05`) before "decrease" even becomes
competitive.

**Why this matters beyond this one pixel:** this is a structural property
of naive sequential Bayesian updating over long, mostly-stable evidence
streams, not a fluke of this transition matrix or this pixel. It's
directly in tension with this project's core modernization goal - "use
the full Landsat archive (1984-present) as continuous evidence." The
longer a stable pre-disturbance baseline gets (which using more of the
archive as evidence directly causes), the harder a genuine later
disturbance becomes to detect at a fixed dampening factor, because more
stable years means more compounding "confirm normal" evidence to
overturn. A pixel with 40 years of stable history before a 2020
disturbance would face an even steeper climb than this 14-year case.

**Follow-up test: does lowering the default to `d=0.05` actually fix
this?** Reran all four test pixels above (stable, B&B Complex fire,
moderate-severity, long-baseline disturbance) at `d=0.5` vs `d=0.05`:

| Point | `d=0.5` (argmax) | `d=0.05` (argmax) | Changed? |
|---|---|---|---|
| Stable/unchanged | unchanged 0.9999999937 | unchanged 0.65 | Same label, much less confident |
| B&B Complex fire | decrease 0.9999 | decrease 0.67 | Same (correct) label, less confident |
| Moderate-severity | unchanged 0.71 | decrease 0.50 vs. 0.485 | **Flips** - barely, to the arguably-more-correct answer |
| Long-baseline disturbance | unchanged 0.99999999999936 | unchanged 0.846 | **Still wrong** - confidence drops a lot but doesn't flip |

**Conclusion: dampening alone, even pushed fairly hard (`d=0.05`, and
per the sweep above even `d=0.02`), is NOT sufficient to fix the worst
case.** It reduces overconfidence broadly (useful) and correctly nudges
the genuinely-ambiguous moderate-severity pixel toward "decrease," but
the stark 14-year-stable/9-year-disturbed pixel stays misclassified as
"unchanged" even at `d=0.02`. This rules out "just lower the default
dampening factor" as a complete fix by itself - it's a real mitigant,
not a solution, for this specific failure mode.

Three possible directions were considered: lowering `dampening_factor`
further (ruled out above - doesn't fully fix it even at `d=0.02`); adding
a recency-weighting/forgetting mechanism (not part of the classic BULC
formulation, a genuine departure from the reconstructed method); or
rebalancing the transition matrix itself (no real production matrix to
compare against, so any rebalancing would be a guess). Recency weighting
was implemented and validated - see "Recency weighting" below, and
[decisions/0005](decisions/0005-recency-weighting-extension.md).

## Recency weighting (2026-07-30): implemented and validated

See [decisions/0005](decisions/0005-recency-weighting-extension.md) for
the decision itself (`bulc.py`'s new `discount()`/`recency_factor`,
default off). This entry is the validation behind it.

**Validated by rerunning all four test pixels at `gamma=1.0` (off) vs.
`gamma=0.99`/`0.98`/`0.95`, all at `dampening_factor=0.5`:**

| Point | gamma=1.0 (off) | gamma=0.99 | gamma=0.98 | gamma=0.95 |
|---|---|---|---|---|
| Stable/unchanged | unchanged 0.99999999 | unchanged 0.9999989 | unchanged 0.99996 | unchanged 0.9933 |
| B&B Complex fire | decrease 0.9999 | decrease 0.9995 | decrease 0.9930 | decrease 0.8825 |
| Moderate-severity | unchanged 0.71 | ~toss-up (0.49/0.51) | unchanged 0.77 | unchanged 0.82 |
| **Long-baseline disturbance** | **unchanged 0.9999999999994 (wrong)** | unchanged 0.81 (still wrong) | **decrease 0.93 (correct)** | decrease 0.88 (correct) |

At `gamma=0.98`: the long-baseline case **flips to the correct
classification**, while the two unambiguous cases (stable, B&B fire)
*stay* correctly classified with high confidence - the fix doesn't come
at the cost of breaking what already worked. The moderate-severity case
wobbles non-monotonically across gamma values, which is expected for a
genuinely borderline case (MTBS itself only calls it "moderate"), not a
red flag.

`scripts/debug_long_baseline_disturbance.py` now includes both the
dampening sweep and a `recency_factor` sweep reproducing the table above
directly against the real `engine.run_bulcd()` code (not just the ad hoc
experiment this was first tried in).

## Disturbance map (2026-07-30): first full-AOI visualization, plus a water mask

Every validation above only ever sampled a single pixel via
`reduceRegion()`. `engine.run_bulcd()`'s `final_probabilities` has always
been a full image over the entire AOI, not just a point - this was the
first time it was actually looked at spatially, via
`ee.Image.getThumbURL()` (a cheap, synchronous preview render, NOT
`Export.image.toAsset/toDrive` - `bulcd/export.py` still doesn't exist
at this point).

Rendered the B&B Complex Fire AOI (widened to ~13km, see
`scripts/debug_disturbance_map.py`) as an RGB composite
(R=decrease, G=unchanged, B=increase - the same convention the legacy
caller used for `Map.addLayer(finalBulcProbs, ...)`). Result: a coherent,
irregular red region with a realistic fire-perimeter shape, not noise
scattered across the AOI - the strongest visual validation the pipeline
has had, corroborating all the single-pixel numeric checks above.

**Artifact found: water bodies misclassified as "increase"** (scattered
blue specks, mostly in the AOI's upper portion and a lower-left cluster).
Expected - water's reflectance behaves nothing like the forest-tuned
harmonic model, and the legacy pipeline always applies `afn_waterMask()`
before displaying/exporting results (`legacy/BULCD-Caller-Current.txt`);
we'd never applied any water masking. See
[decisions/0006](decisions/0006-standard-dataset-masks.md) for the fix
(`_water_mask()`, JRC Global Surface Water).

**Verified partial, not total, fix.** Rerendering with masking on shows
real water bodies now correctly excluded (visible as new gaps in the
map). But most of the original blue specks are still there. Sampling one
directly: JRC `occurrence` at that exact pixel is `None` (zero recorded
water history) - it isn't water at all. So the remaining "increase"
speckling has a different, NOT YET IDENTIFIED cause - candidates include
genuine small-scale greening, a terrain/shadow artifact in the Cascades'
rugged relief, or persistent snow/ice at elevation even within the
growing-season DOY window. Flagged here rather than investigated further
this session - don't assume the water mask fully resolved the artifact
just because it's now present in the code.

`scripts/debug_disturbance_map.py` reproduces this (prints a thumbnail
URL - fetching it requires an authenticated request, see the script's
own docstring for the pattern used to build one).

## Grid-cell maps (2026-07-30): AOI sourced from the real study-area grid

`scripts/debug_grid_cell_map.py CELL_ID` runs the same disturbance-map
pipeline as `debug_disturbance_map.py` above, but sources its AOI from
the actual study-area grid asset instead of a hand-picked box:
`projects/eastern-cascades-bugnet/assets/clipped_grid_35000m` (a sibling
GeoTimeSeries-project asset — the route-corridor grid, cells clipped to
the buffer so they're irregular polygons, not clean squares). Cells are
selected by their `grid_id` property (row + column-letter, e.g. `"11A"`,
`"2F"`) — confirmed via `.propertyNames()`/`.toDictionary()` on the
asset (`row`, `column`, `column_letter`, `grid_id`, `clipped_area_m2`,
`cell_size_m` are the other fields). The script filters the
`FeatureCollection` to one feature, pulls its polygon ring via
`.geometry().getInfo()`, and feeds it through `StudyAreaConfig.aoi_coordinates`
(the config layer has no "asset + filter" option yet — `resolve_study_area()`'s
`aoi_asset` path only supports a whole collection's unioned geometry, not
a single filtered feature — so the filtering happens in the script, not
`bulcd/inputs.py`).

Sensor/baseline config (L5 2000-2012 + L8 2014-2024, growing-season DOY,
2000-2003 expectation baseline, Willis NBR12 transition matrix,
`dampening_factor=0.5` default) is copied as-is from `debug_disturbance_map.py`
rather than tuned per cell — the 2000-2003 window was originally chosen
for the B&B Complex Fire's known pre-fire history, and is reused here as
a generic "earliest available" default since arbitrary grid cells have
no known disturbance history to tune against. Worth revisiting per-cell
if a specific cell's baseline years turn out not to be disturbance-free.

First run, cell `2F`: a coherent map, mostly "unchanged" (green) with
"decrease" (red) clustered in patches rather than scattered noise, and —
notably — a river visibly cut out as a clean white (masked/nodata) line
through the middle of the AOI, the clearest visual confirmation yet that
`_water_mask()` is doing real work along a linear water feature, not just
isolated ponds like the earlier B&B Complex test.

## Year of change (2026-07-30): querying "disturbance in year Y," and a major lag finding

Everything above answers "what's the current state" (`final_probabilities`)
or "what's the state as of some cutoff" (truncate the evidence config).
Neither answers what was actually asked next: "if I say 2025, give me a
disturbance map for 2025 specifically" - i.e. WHEN, not just whether, a
pixel changed. This didn't exist in the pipeline at all until now - it's
the post-run analysis step the legacy calls `afn_interpretBULCDResult`
(still-missing source, `r-2902-Dev`), so everything here is a new
reconstruction, not a port.

**Two prerequisite gaps had to be fixed first, both in code that already
existed:**
- `bulc.py`'s `run_bulc()` folds `classification_stack`/`probability_stack`
  from arithmetic on `prior`/`update_factors` - neither ever carried the
  source Event's date. Fixed by `.set("system:time_start", ...)` in
  `_step()` - NOT `copyProperties()`, which was tried first and silently
  no-ops for `system:` properties even when named explicitly in its
  `properties` argument (only "ordinary" properties are copied; this isn't
  documented clearly and cost real debugging time).
- `engine.py`'s `_bin_to_update_factors()` builds each update-factor image
  via `ee.Image.cat()` over `ee.Image.constant()`/`.where()` chains, none
  derived from the source z-score image - so even after fixing `bulc.py`,
  every step was STILL undated until `_to_update_factors()` in
  `run_bulcd()` also explicitly re-set `system:time_start` from the
  z-score image onto the resulting update-factor image before it reaches
  `bulc.run_bulc()`.

**New module: `bulcd/interpret.py`.** `year_of_change(classification_stack,
target_class_index=0)` returns, per pixel, the calendar year of the
earliest Event that begins an unbroken run of the target class
(default: "decrease") lasting through the LAST Event in the stack;
masked where the pixel doesn't currently sit in that class.
`disturbance_mask_for_year(classification_stack, year, target_class_index)`
filters that to one specific year. Implementation note: `ee.Array`-based,
entirely server-side, no client-side round trip for series length. Two
non-obvious EE quirks hit along the way, both now commented in the code:
`ee.ImageCollection.toArray()` produces a 2-D array (image axis x band
axis) even for a single-band collection - needs `.arrayProject([0])` to
collapse to a plain 1-D time series; and `ee.Image.arraySlice()` has no
negative-step reverse, so the detector finds the LAST mismatching index
via a forward `arrayReduce(max)` trick instead of scanning backward from
the end. Explicitly does NOT handle "changed, then recovered" - a pixel
whose persistent run doesn't reach the final Event is masked, identically
to a pixel that never changed - a real, documented limitation pending the
actual `afn_interpretBULCDResult` source.

**Validated against the known 2003 B&B Complex Fire point - and this
surfaced a major finding, not just a confirmation.** At default settings
(`dampening_factor=0.5`, `recency_factor=1.0`/off), `year_of_change()`
returned **2015**, not 2003. This was double-checked against the raw
`classification_stack` sequence directly (dumped every Event's date +
argmax class at the point) - the algorithm's own argmax classification
genuinely stays "unchanged" from 2000-06-22 all the way through
2015-08-19, THEN flips to "decrease" and never reverts. So the detector
is behaving correctly; the finding is about the algorithm, not a bug:

**Even though the z-score jumps hugely negative within days of the real
2003 ignition (see "Known-burn validation" above), the running Bayesian
argmax classification takes 12 YEARS to actually flip**, because each
step's update factor is dampened toward uniform (`d=0.5`) and the prior
years of "confirm normal" evidence (even just 3 years, 2000-2002) still
takes many consecutive negative-z Events to overcome. This is the same
compounding mechanism as "Major finding: long stable baselines can mask
real disturbance" above, but demonstrated here on the pipeline's own
best-validated real-fire test point - and it directly undermines the
premise of a year-specific query: at default settings, "disturbance in
year Y" is really answering "when did the algorithm finally admit it,"
which can lag the true event by over a decade.

`recency_factor` (built earlier for exactly this compounding problem)
measurably helps, tested at the same point:

| `recency_factor` | detected `year_of_change` |
|---|---|
| 1.0 (off) | 2015 |
| 0.99 | 2009 |
| 0.98 | 2007 |
| 0.95 | 2006 |

Monotonically closer to the true 2003 ignition as recency weighting
increases, but NOT exact even at 0.95 - there is no known setting that
eliminates this lag, only reduces it. Anyone using
`disturbance_mask_for_year()` for real analysis needs to know this before
trusting a specific year's map, especially at the library default
(`recency_factor=1.0`).

**A second, unrelated limit surfaced trying to render this spatially,
not just at one point:** `year_of_change()` materializes a full per-pixel
time-array (~200+ values for a multi-decade config) - much heavier per
pixel than `final_probabilities`' simple 3-band image. A `getThumbURL`
preview at `dimensions=512` (fine for `debug_disturbance_map.py`'s
`final_probabilities`) hit "User memory limit exceeded" for a
`year_of_change`-based map over the same ~13km test box; `dimensions=128`
succeeded and showed a coherent, non-random cluster of pixels flipping to
"decrease" specifically in 2015. This is a synchronous-preview scale
limit, not a fundamental one - a real full-resolution/full-cell map would
need an actual batch export (`Export.image.toAsset`/`toDrive`), not
`getThumbURL`.

`scripts/debug_year_of_change_map.py CELL_ID YEAR [RECENCY_FACTOR]`
reproduces all of this against a real grid cell (see "Grid-cell maps"
above for how AOIs are sourced from `clipped_grid_35000m`).

## Two-layer "was this abnormal in year Y" + first real export (2026-07-30)

Follow-up to "Year of change" above, prompted by the user pointing out
their actual mental model: "flag disturbance if pixels in the target
image are outside what is normal as defined by the expectation time
period" - i.e. the raw z-score, not the Bayesian-accumulated
classification `year_of_change()` reads. Both are real, valid answers to
"was this pixel abnormal in year Y," at two different layers of the
pipeline, with a fundamental noise-robustness-vs-lag tradeoff between
them - see `bulcd/interpret.py`'s module docstring for the split. New:
`interpret.zscore_anomaly_mask_for_year(zscore_collection, year,
threshold=-2.0)` - true where ANY image in that calendar year has a
z-score at or below `threshold` (default matches `bin_cuts`'s own most
extreme cut), read straight from `organize_inputs()`'s per-image z-score
stream. No Bayesian accumulation, so no lag - but also no protection
against a single noisy/cloud-contaminated image, unlike
`disturbance_mask_for_year()`'s robustness-by-design.

**`bulcd/export.py` now exists** - thin wrapper around
`ee.batch.Export.image.toAsset()` (starts the task, hands back the
`ee.batch.Task`, does not poll/block - jobs can take minutes to hours).

**First real export run**, not a preview: cell `2F`, year 2025, both
layers combined into one 2-band image (`zscore_anomaly`,
`bulc_classification`), to `projects/bulcd-python-rebuild/assets/disturbance_2025`
(`scripts/export_year_disturbance_map.py`). Notes specific to this run:
- L8's `last_year` had to be bumped to 2026 (from other scripts' 2024) -
  `_date_bounds()`'s end-year is EXCLUSIVE, so 2025 data requires
  `last_year=2026`.
- Sanity-checked before spending the export: 13 evidence images exist for
  cell 2F in 2025 (non-zero, reasonable), and `zscore_anomaly` alone
  computes fine at full-cell scale (30m, real `reduceRegion` over the
  whole ~35km cell) with a non-degenerate split (~37% of the cell flagged
  anomalous in 2025 at the default threshold) - no evidence of a
  degenerate all-0/all-1 result before committing to the real export.
- `bulc_classification` (the `year_of_change()`-based band) still hits
  "User memory limit exceeded" via any synchronous call
  (`reduceRegion`/`getThumbURL`) at full-cell scale, even reduced to
  100m - consistent with the memory-limit finding above, and confirms
  this band genuinely needs the batch export path (a different compute
  tier, not subject to the interactive limit) rather than ever being
  previewable at this scale. Its actual output over the full cell
  wasn't verified before export - only at a single point and a smaller
  ~13km test box previously - so treat this run's `bulc_classification`
  band as unverified at cell-2F scale until the exported asset itself
  can be inspected.
- Given 2025 is only ~1 year removed from "now" (2026-07-30) and the
  validated 12-year lag finding, `bulc_classification` for this specific
  run is expected to come back mostly or entirely empty/masked - that's
  expected pipeline behavior given how little post-2025 evidence exists
  yet, not a bug, per the caveat threaded through this whole feature.

## Non-forest mask (2026-07-30): false "change" above treeline, and DOY narrowing ruled out

Inspecting the real `disturbance_2025` export (above), the user found
false "change" flagged near mountain tops, above the tree line. First
hypothesis - the same DOY window used everywhere else was still letting
in shoulder-season snow (June 1-Sept 30, `152-273`) - was tested by
narrowing to peak summer (`152-243`, June 1-Aug 31) across the three
active scripts (`debug_grid_cell_map.py`, `debug_year_of_change_map.py`,
`export_year_disturbance_map.py` - the earlier validation scripts
(`debug_bb_complex_fire.py` etc.) were deliberately left at `152-273`
since their documented findings are tied to that exact window).
**Re-exporting with the narrower window did not fix it** - confirmed by
the user directly. This ruled out the hypothesis, not just failed to
help: above-treeline terrain (bare rock, scree, permanent snow/ice) has
no seasonal window where it resembles the forest the expectation model
was fit on - narrowing WHEN you look doesn't fix looking at land that was
never forest in the first place.

**Real cause, found by inspecting the config rather than guessing
further:** `StudyAreaConfig.forest_mask_asset` had existed as a schema
field since the project's early scaffold stage (loaded by
`config/loader.py`) but was NEVER actually wired into `engine.py` - only
`mask_water`/`_water_mask()` were ever applied. Zero non-forest screening
existed anywhere in the pipeline until now. See
[decisions/0006](decisions/0006-standard-dataset-masks.md) for the fix
(`StudyAreaConfig.mask_non_forest`, Hansen Global Forest Change fallback).

Sanity-checked on cell 2F before use: ~28% of the cell flagged
non-forest, ~72% forest - plausible for a mountainous Cascades cell, not
degenerate.

This surfaced a second, independent gap while fixing the first: **the
`disturbance_2025` export had no water masking either**, since
`zscore_anomaly_mask_for_year()`/`disturbance_mask_for_year()` both read
those un-masked collections directly, never routing through
`run_bulcd()`'s masking step. `export_year_disturbance_map.py` now calls
`engine.study_area_mask(config)` explicitly and applies it to the
combined 2-band output before export - fixes both the treeline artifact
and the missing water mask in one change.

Re-exported to `projects/bulcd-python-rebuild/assets/disturbance_2025`
(same path, asset overwritten) with both masks applied. **Open question,
not yet resolved:** verifying the two prior export attempts via
`ee.data.getAsset()`/`listAssets()` reported the asset as not existing
even though both tasks showed `state: SUCCEEDED` with a valid
`destination_uris` link, and the user was clearly able to view real
content from it (that's how the treeline artifact was found in the first
place). Root cause not identified - flagged here in case it recurs;
verify new exports directly in the GEE Code Editor rather than relying
solely on this codebase's own asset-listing calls until this is
understood.

## Legacy-GUI parameter matching + Sentinel-2 support (2026-08-10)

User's plan: run cell 8C through both the legacy GUI (`guiBULCD.rtf`) and
this rebuild, then compare outputs directly - the first real GUI-vs-rebuild
validation attempted in this project. Before running anything, worked out
which parameters could actually be matched, and how.

**Investigated `guiBULCD.rtf` directly** (converted via `textutil -convert
txt`) rather than guessing at "GUI defaults," since an imagined default
would have made for a false comparison:
- The Expectation/Target year checkboxes and DOY textboxes have **no
  default at all** - every year checkbox is instantiated
  `ui.Checkbox('20XX', false)` and every DOY field is a blank `ui.Textbox`
  with only a placeholder. These have to be chosen fresh in the GUI each
  session and mirrored by hand into the rebuild's config - there was
  nothing to inherit.
- `binCuts` **is** hardcoded (`[-2,-1.5,-1,-0.5,0,0.5,1,1.5,2]`, line 5965)
  - already matches `schema.py`'s default.
- `modalityDictionary`/`sensitivityDictionary` **do** have real GUI
  defaults: `{constant:true, unimodal:true}` / `{ZScoreNumeratorFactor:1,
  ZScoreDenominatorFactor:0.05}` (lines 5935-5954), matching
  `BULCD-InputParameters-v5`'s real production example too. This exposed
  a genuine, pre-existing mismatch: `ModalityConfig.unimodal` defaults to
  `False` in `schema.py`, not `True` - left as-is in the schema (not
  clearly a bug, just undocumented), but must be overridden per-config
  for any GUI-matching run.
- `customTransitionMatrix`/dampening factor are **not in `guiBULCD.rtf` at
  all** - pulled at runtime from a separate module we still don't have
  source for (`getBULCParameterDictionary()`,
  `6003.3c-BULC-AdvancedParameters`, `r-2903-Dev`). But the GUI **prints
  its fully-resolved argument dictionary to the Console right before
  calling the algorithm**: `print("Arguments to BULC-D", var_args_BULCD)`
  (line 7182), where `var_args_BULCD.BULCargumentDictionaryPlus` is
  exactly that module's real return value. **This is the actual way to
  get real production dampening/transition-matrix numbers** - run the GUI
  once, expand that object in the Console - not something to keep
  guessing at from Willis (2022)'s thesis example.
- Legacy applies `afn_waterMask()` unconditionally but has **zero
  forest-mask logic anywhere** in `guiBULCD.rtf` (grepped for
  forest/treecover/hansen/canopy - no hits). A real asymmetry against
  this rebuild's `mask_non_forest` (defaults `True`) - disabled per-config
  for a fair comparison rather than changing the schema default.

**New file: `configs/cell_8c_comparison.yaml`** - the first config file
actually driving a real run through `load_config()` rather than a
debug script's hardcoded Python `BULCDConfig(...)` construction (every
`scripts/debug_*.py` script until now built its config inline). AOI
fetched live from `clipped_grid_35000m`'s `grid_id="8C"` feature (same
pattern as "Grid-cell maps" above). Parameters transcribed directly from
the user's real GUI run: cross-sensor L8+L9+S2, expectation year 2024 /
target year 2025 (collapsed into one continuous evidence window per
sensor, `first_year:2024, last_year:2026` - `last_year` is exclusive),
DOY narrowed from an initial 1-365 to 74-288 (applied uniformly - the
schema has one DOY window per sensor covering the whole evidence stream,
no separate expectation-only/target-only split), cloud cover threshold
70, NBR, `day_step_size:3`, modality **unimodal only** (not
`constant+unimodal` - a deliberate GUI choice for this run, different
from the GUI's own out-of-the-box default found above), sensitivity
`{1, 0.05}`. `bulc_advanced_params.dampening_factor`/
`custom_transition_matrix` remain Willis-thesis placeholders pending the
Console readout described above - **not yet a fully parameter-matched
run** until those are filled in (see "Real production BULC-D parameters"
below - they since were, partially).

**Sentinel-2 support implemented in `bulcd/inputs.py`** - needed because
the real GUI comparison run enables S2, which previously raised
`NotImplementedError`. New: `_s2_with_cloud_probability()` (joins
`COPERNICUS/S2_SR_HARMONIZED` to its `COPERNICUS/S2_CLOUD_PROBABILITY`
companion collection by `system:index`), `_mask_s2_clouds()` (cloud +
cloud-shadow mask via cloud-probability threshold + NIR dark-pixel
shadow projection), `_scale_s2_sr()`, `_s2_evidence()` (mirrors
`_landsat_evidence()`'s shape). This is the standard community
s2cloudless recipe (Google's own tutorial, already referenced in
`S2CloudMaskConfig`'s docstring) - not a novel reconstruction, same
"standard substitute" posture as the water/forest mask additions above.

VERIFIED against real Earth Engine for cell 8C: evidence assembly returns
real imagery (352 total L8+L9+S2 images at the final DOY 74-288 window;
an isolated S2-only pull returned sane NBR values, e.g. 0.69 at one
sample date/region), and the full `organize_inputs()` harmonic-fit/
z-score pipeline runs end to end (477-image z-score stream at an earlier
DOY 1-365 test, one z-score per evidence image as expected - all 32
existing tests also still pass unchanged). A full-cell `reduceRegion` of
R2 timed out server-side ("Computation timed out") - consistent with the
interactive-compute-limit findings already documented for
`bulc_classification` above, not a defect in the new S2 code; a
single-point sample at the cell centroid worked fine (R2=0.039 - low,
plausibly a non-forest/glacier point near Mount Rainier given cell 8C's
coordinates, not diagnostic of a bug). MODIS/Sentinel-1/ALOS/NICFI/
Dynamic World remain unimplemented.

## Real production BULC-D parameters, read live from the GUI Console (2026-08-10)

Follow-up to the section above. The GUI's Console output turned out to be
the actual way to get real production values for things that were
previously only reconstructed from published papers - not just a
theoretical possibility, but something done for cell 8C this session by
running the GUI and manually expanding the printed argument objects
(`print("Arguments to BULC-D", var_args_BULCD)`, `guiBULCD.rtf` line
7182) in the browser Console, since a plain copy-paste of Console text
only captures collapsed `Object (N properties)` placeholders, not their
contents.

**Real `customTransitionMatrix`, now in `configs/cell_8c_comparison.yaml`:**
```
[0.83,0.08,0.08]   [0.66,0.24,0.08]   [0.53,0.37,0.08]   [0.14,0.76,0.08]
[0.08,0.83,0.08]   [0.08,0.83,0.08]   [0.08,0.76,0.14]   [0.08,0.37,0.53]
[0.08,0.24,0.66]   [0.08,0.08,0.83]
```
Genuinely different from Willis (2022)'s thesis worked example that
every prior test in this project used - and unlike the thesis's
hand-picked weights, these rows actually sum to ~0.98-0.99 (real
conditional probabilities). Columns confirmed as
`[P(bin|decrease), P(bin|unchanged), P(bin|increase)]` by the shape
(row 0 dominated by column 0, row 9 by column 2, rows 4-5 - the
"unchanged" bins - both exactly `[0.08,0.83,0.08]`).

**Major finding: dampening is not one scalar in production - it's three
separate "levelers" plus two "minimum" floors:**
```
initializingLeveler: 0.7   transitionLeveler: 0.7   posteriorLeveler: 0.9
transitionMinimum: 0.1     posteriorMinimum: 0.0333...
```
`bulc.py`'s `dampen()` (Cardille & Fortin 2016's published single-`d`
formula, `dampened = d*raw + (1-d)/n_classes`) can't represent this -
it's a structural mismatch, not just a wrong number for
`dampening_factor`. Per this project's own standing rule ("don't guess
at this math, get the source first" - same discipline already applied to
`organizeBULCD_Inputs`), the right next step is fetching
`BULC-Module-Current/BULC-Minimal-Module-107`'s real source
(`alemlakes/r-2909-BULC-Releases` - already flagged as needed but
unfetched since this repo's original scaffold) rather than
reverse-engineering three formulas from one instance's numbers (some
numeric patterns are tempting - e.g. `transitionMinimum=0.1=1/10 bins`,
`posteriorMinimum≈transitionMinimum/3` - but that's speculation, not
reconstruction). **Decided: pause the cell 8C comparison run until that
source is fetched**, rather than approximate with a single leveler value.
`bulc_advanced_params.dampening_factor` in `configs/cell_8c_comparison.yaml`
remains `0.5` - explicitly flagged in the file as unvalidated, not a
considered choice. See
[decisions/0004](decisions/0004-dampening-factor-default-0.5.md)'s
"Open gap" note.

**Confirmed and fixed: unimodal's real regressor set is 3-term, not
Willis's simplified 2-term.** The same Console output printed
`harmonic names (Optical): ["constant","cos","sin"]` for this run's
unimodal-only modality selection - the full first-order harmonic
(constant + cosine + sine), not Willis (2022) eq. 6's simplified
constant+sine-only fit that `_select_modality_regressors()` implemented
until now. Fixed in `bulcd/inputs.py`: `_add_harmonic_terms()` was
missing a first-order `cos` band entirely (it had `cos2`/`cos3` for the
second/third harmonics but never first-order cosine), added; unimodal's
regressor list is now `["constant", "cos", "sin"]`. VERIFIED against
real Earth Engine at the cell 8C centroid: R2 improved from 0.039
(sin-only) to 0.149 (constant+cos+sin) - a real fit improvement from a
genuinely missing regressor, not noise. Bimodal/trimodal likely have the
same first-order gap (their regressor lists still only include `sin`,
not `cos`, at first order) but this is NOT yet confirmed by any live
run - left unchanged rather than guessed. Test renamed/updated:
`test_select_modality_regressors_unimodal_uses_full_first_order_harmonic`
in `tests/test_inputs.py`; all 32 tests still pass.
