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

## BULC-Minimal-Module-107 obtained, `posterior_leveler` fix (2026-08-10)

Direct follow-up to "Real production BULC-D parameters" above. User's
plan (from "let's continue" earlier this session): run cell 8C through
both the legacy GUI and this rebuild, compare outputs. First real
comparison surfaced a stark discrepancy - the rebuild's render came back
~95% "decrease" (red), the GUI's came back ~90% "unchanged" (green) with
scattered noise - looking almost inverted, not just differently
confident. User's own instinct ("they almost seem inverse") turned out
to be the right thread to pull.

**Diagnostic process, cheapest-explanation-first:**
- Checked `engine.py`'s bin-to-matrix-row and matrix-column-to-class
  ordering by hand and by direct trace (`_bin_zscore()`/
  `_bin_to_update_factors()` at real points/dates) - both correct, not
  an indexing bug.
- Sampled real z-score medians at the cell centroid and two solid-red
  points: all near-zero to slightly POSITIVE (0.06 to 0.52) - which per
  the transition matrix should favor "unchanged," if anything leaning
  "increase." Yet `final_probabilities` at every point was `decrease`
  with extreme confidence (`0.9999999999999998` vs. `10^-16` to
  `10^-112` for the other two classes) - a real contradiction between
  input data and output, not a tuning issue.
- User then fetched **`BULC-Minimal-Module-107`'s actual source**
  (`alemlakes/r-2909-BULC-Releases`, `BULC-Module-Current/
  BULC-Minimal-Module-107`) directly from the GEE Code Editor - saved to
  `legacy/BULC-Minimal-Module-107.txt` (1267 lines).

**The real source revealed a genuine missing mechanism, not a guess.**
`afn_hiddenBULCIterateWithOptions` (the real per-Event loop) does TWO
dampening operations per step, not one:
```js
// 1. Standard Bayes update - matches bulc.py's bayes_update() exactly
posteriorProbsValidPixels1D = currentProbs.multiply(transitionArrayImageRescaledAndDampened)
    .divide(currentProbs.arrayDotProduct(transitionArrayImageRescaledAndDampened))

// 2. A SECOND dampening step, applied to the POSTERIOR, EVERY STEP:
posteriorProbsValidPixels1D = afn_dayIRebalancingV3(posteriorProbsValidPixels1D, posteriorLeveler, posteriorMinimum)
// afn_dayIRebalancingV3: probStackToLevel.multiply(balanceFactor).add(minimumProbToAddDaily)
```
`bulc.py` only ever implemented step 1 (matching production's separate
`transitionLeveler`/`transitionMinimum` dampening of the transition
table, which `dampening_factor` already modeled correctly). Step 2 -
re-dampening the POSTERIOR after every single Bayes update - was never
implemented at all. The numbers confirm both steps share one formula:
`posteriorMinimum (0.0333...) = (1 - posteriorLeveler(0.9)) / 3`,
`transitionMinimum (0.1) = (1 - transitionLeveler(0.7)) / 3` - exactly
`dampen()`'s existing shape, `d*raw + (1-d)/n_classes`.

**Mechanism, and why it explains the inversion:** without step 2,
nothing bounds how extreme the running posterior can get across many
sequential steps - small, even non-adversarial biases compound
multiplicatively over ~350 steps (cell 8C's 2024-2025 evidence window)
into runaway, uninterpretable confidence at the edge of float64
precision. Production's `posteriorLeveler` continuously re-injects
uniform mass at every single step, structurally preventing this. A
diagnostic per-step trace (`_bin_zscore()`/`_bin_to_update_factors()` at
real dates) confirmed individual steps compute correctly (mild z-scores
→ bins 4/5 → `unchanged` favored 0.76-0.83, exactly as expected) -
ruling out the per-step math and pointing squarely at the missing
per-step regularization as the accumulation-level bug.

**Fix implemented:**
- `bulc.py`: `dampen()` generalized (renamed param `update_factors` ->
  `image`, already fully generic) and reused for BOTH steps -
  `run_bulc()` gained a new `posterior_leveler` parameter, applied via
  `dampen(posterior, posterior_leveler)` immediately after
  `bayes_update()`, before `discount()`.
- `bulcd/config/schema.py`/`loader.py`: new `BULCAdvancedParams.posterior_leveler`
  field, validated `0 < x <= 1` same as `dampening_factor`/`recency_factor`.
  Defaults to `1.0` (no-op) - same rollout discipline as
  `dampening_factor`'s own history (see
  [decisions/0004](decisions/0004-dampening-factor-default-0.5.md)):
  implement with a safe default first, validate empirically, THEN decide
  a considered default via its own decision record. New: see
  [decisions/0007](decisions/0007-posterior-leveler-regularization.md).
- `bulcd/engine.py`: `run_bulcd()` passes `advanced.posterior_leveler`
  through.
- `configs/cell_8c_comparison.yaml`: updated with the REAL confirmed
  values - `dampening_factor: 0.7` (= `transitionLeveler`),
  `posterior_leveler: 0.9` (= `posteriorLeveler`).
- 2 new tests (`test_posterior_leveler_defaults_to_off`,
  `test_posterior_leveler_must_be_in_valid_range`); 34 total, all pass.

**VALIDATED against real Earth Engine, same three points as the original
inversion finding:** confidence is now bounded and sane -
`{decrease: 0.914, unchanged: 0.043, increase: 0.043}` at the centroid
(was `{decrease: 0.9999999999999998, unchanged: 1.3e-16, increase:
4.2e-84}`) - a dramatic, confirmed fix for the runaway-confidence bug.

**Not fully resolved - a real, separate gap remains.** The plurality
classification at all three points is STILL `decrease`, not `unchanged`
like the GUI's render. `afn_buildStartProbs`/`afn_createPriorsFromLandcoverMap`
in the real source show production starts from a real `baseLandCoverImage`
- one-hot encoded per pixel, then leveled by `initializingLeveler` (also
confirmed 0.7) - NOT a flat uniform prior like this rebuild's
`engine.run_bulcd()` currently constructs (`1/n_classes` per class,
always). What `baseLandCoverImage` actually contains for a BULC-D run
specifically isn't given in `BULC-Minimal-Module-107` itself - plausibly
"assume unchanged" as the default starting hypothesis (which would
explain the GUI's stronger unchanged-leaning result), but that's
inference, not confirmed - would need `organizeBULCD_Inputs`'s source
(still missing) or the BULC-D caller script to see how it's actually
constructed. Flagged here, not yet investigated further - re-export to
`projects/bulcd-python-rebuild/assets/bulcd_cell8c_comparison_v2` in
progress at time of writing to see the corrected map spatially before
deciding next steps.

## initializing_leveler, real organizeBULCD_Inputs source, z-score fixes (2026-08-10)

Direct continuation, same session. User fetched two more real source
files from the GEE Code Editor:

**`afn_BULCD` (`6002.B2-BULCD-Module`, `r-2903-Dev`)** - turned out not
to construct `baseLandCoverImage` itself; it just passes
`BULCargumentDictionaryPlus` through to `runBULCAlgorithm`, only
overriding `eventsAsImageCollection`/`defaultStudyArea`. This redirected
the search to whatever supplies `BULCargumentDictionaryPlus` in the
first place.

**`6003.3c-BULC-AdvancedParameters` (`getBULCParameterDictionary()`,
`r-2903-Dev`)** - the real source of `customTransitionMatrix` and all
three levelers, confirmed. Critically:
```js
var baseLandCoverImage = ee.Image(2) // default is "nothing has changed".
```
A hardcoded constant - `getBULCParameterDictionary()` takes zero
arguments, so this can't be per-AOI/per-run data. One-hot encoded to the
"unchanged" class (2nd of `[1,2,3]`) and leveled by `initializingLeveler`
(confirmed 0.7) via the same `dampen()`-shaped formula as everything
else, giving a real starting prior of `[0.1, 0.8, 0.1]`
(decrease/unchanged/increase) - not this rebuild's previous flat
`[0.333, 0.333, 0.333]`.

**Implemented**: `BULCAdvancedParams.initializing_leveler` (new field,
`schema.py`/`loader.py`, validated `0 <= x <= 1` - inclusive of 0, unlike
the other three levelers, since 0 is the meaningful "flat uniform, no
informed prior" value here). `engine.run_bulcd()` now builds a one-hot
"unchanged" image and runs it through `bulc.dampen()` instead of a flat
`1/n_classes` constant. 2 more tests (36 total, all pass).

**VALIDATED, and genuinely surprising:** rerunning the same three points
with `initializing_leveler=0.7` produced numbers **identical to the
decimal** to the flat-uniform-prior run. Reasoned through why: with
`posterior_leveler=0.9` applied at *every* one of ~350 sequential steps,
any single step's influence (including the very first prior) decays by
roughly `0.9^N` - by step 350 that's `~6e-17`. The starting prior is
completely washed out within the first few dozen steps for a sequence
this long, so `initializing_leveler` genuinely cannot matter here. Real,
confirmed, mathematically sound - not a bug - but it means the
starting-prior theory does NOT explain the remaining "decrease" vs.
"unchanged" disagreement with the GUI after all.

**User then fetched a third file: `afn_organizeBULCD_Inputs`
(`6002.A2b.3-BULCD-Module-organizeBULCD_Inputs`, `r-2903-Dev`)** - the
module CLAUDE.md has flagged as missing since this project's original
scaffold, source of the entire expectation/target harmonic-fit and
z-score layer. Confirms the legacy really is a discrete two-collection
design (fit only on `expectationCollection`, scored only on
`targetCollection`) - this rebuild's continuous full-stream scoring is a
confirmed, deliberate divergence (see
[decisions/0003](decisions/0003-continuous-evidence-replaces-expectation-target-split.md)),
not something to reconcile. Two concrete formula corrections fell out of
it:
- **Z-score denominator**: `expectationPeriodSD.max(ZScoreDenominatorFactor)`
  - a FLOOR/clamp, not the additive epsilon
  (`residual_stddev + denominator_factor`) this used to implement. Also
  confirmed: the result is clamped to `[-10, 10]` (low practical impact
  given this project's `bin_cuts` already collapse anything beyond `±2`
  into the outermost bin, but implemented for fidelity).
- **`residual_stddev`**: plain `ee.Reducer.sampleStdDev()` (`n-1`
  denominator) over per-image residuals, not this rebuild's regression
  residual-standard-error convention (`n - num_regressors`). OLS
  residuals sum to ~0 given the design always includes a constant term,
  so the two formulas differ only in denominator.

Both fixed in `bulcd/inputs.py` (`_zscore_image()`, `_fit_expectation_model()`).
VALIDATED against real Earth Engine: `residual_stddev` at the cell 8C
centroid came back `0.0503` - barely above the `0.05` floor, meaning the
new formula gives roughly HALF the old denominator there
(`max(0.05,0.0503)=0.0503` vs. the old `0.0503+0.05=0.1003`) - a real,
meaningful change to z-score magnitude. **Rerunning the same three
points again produced numbers unchanged to the decimal from the
`initializing_leveler` test.** Same underlying reason: `posterior_leveler`'s
per-step regularization dominates the long-run outcome; the bin
*composition* over ~350 steps, not any single step's exact magnitude,
drives the final classification.

**Net conclusion after three confirmed, validated fixes: the remaining
"decrease" vs. "unchanged" disagreement with the GUI is NOT explained by
the posterior-overconfidence bug, the starting prior, or the z-score
denominator formula - all three are now correct and none moved the
classification.** `afn_organizeBULCD_Inputs` doesn't reference
`dayStepSize` anywhere either - it lives inside a third, still-unfetched
module (`afn_gatherCollectionsAndReduce`,
`CommonCode2:515.ImageCollectionFilteringAndGathering/515-gatherCollections27b`).
Given three tuning-level fixes all failed to move the needle, the more
likely remaining explanation is something at the evidence-composition
level (which images actually get included/weighted) rather than a
fourth formula tweak - `dayStepSize`'s real role is the most concrete
lead, but not yet confirmed.

## dayStepSize confirmed and implemented - first fix that actually moved the needle (2026-08-10)

Direct continuation, same session. User fetched `515-gatherCollections27b`
(`CommonCode2:515.ImageCollectionFilteringAndGathering/515-gatherCollections27b`)
- the real `afn_gatherCollectionsAndReduce`, source of `dayStepSize`.

**`dayStepSize` is a temporal binning/aggregation window, not a
sampling/thinning parameter:**
```js
var listOfMillis = ee.List.sequence(startDateMillis, endDateMillis, dayStepSizeMillis)
function afn_nestedDay(binStartMillis) {
    var start = ee.Date(binStartMillis)
    var end = ee.Date(binStartMillis).advance(dayStepSize, 'day')
    // ...gathers ALL images from ALL active sensors within [start, end)...
    var dailyAnswer = multiSensorTimeSlice.median().rename([bandName_reduction])
```
Production divides the whole DOY/year range into `dayStepSize`-day bins,
gathers every image from every enabled sensor landing in each bin,
cloud-masks/reduces them individually (already correctly implemented on
our side), then takes the MEDIAN across the entire bin - collapsing
however many raw images fell in that window into exactly ONE combined
"Event." That single combined image per bin, not each raw image, is what
becomes one step in the sequential Bayesian fold.

**This was a genuine, confirmed structural gap, not a missing formula
tweak.** `bulcd/inputs.py`'s `assemble_evidence_collection()` previously
treated every single cloud-free image as its own independent Event -
~350 raw images for cell 8C's DOY 74-288 window, versus production's real
`dayStepSize=3` producing roughly `(215/3)*2 ≈ 143` Events over the same
data. Given how sensitive the classification already proved to be to the
*number* of compounding sequential steps (that's exactly why
`posterior_leveler` mattered so much), running more than twice as many
updates as production over the same underlying evidence was a real,
substantial difference - not a minor implementation detail.

**Implemented**: new `_evidence_date_and_doy_bounds()` (union of all
enabled sensors' resolved year/DOY ranges, matching production's
`groupStartDOY`/`groupEndDOY`/`whichYears` - a combined window across
sensors, not per-sensor) and `_bin_evidence_by_day_step()` in
`bulcd/inputs.py`, wired into `assemble_evidence_collection()` after the
existing per-sensor gather/merge/sort step. Empty bins reproduce
production's "dummy image" safeguard (which prevents `.median()` from
collapsing to a zero-band result) via a self-masked placeholder image
unioned into every bin before reducing.

**Implementation note, a real EE performance lesson:** the first version
used `.map()` over the bin list with an independent `.filterDate()`
inside each bin (each of ~140 bins re-scanning the full 352-image
collection). This built a computation graph large enough to hit "User
memory limit exceeded" even for a single-point `reduceRegion` query -
worse than any prior full-cell operation in this project. Rewrote using
`ee.Join.saveAll()` - the standard, efficient EE idiom for "group
elements of one collection by date-range membership in another" - which
resolved it completely; the rewritten version ran a full point-based
`run_bulcd()` query in well under the earlier version's failure point.

**VALIDATED against real Earth Engine, same three points as every prior
check in this thread - and this is the FIRST of the four fixes in this
whole investigation (posterior_leveler, initializing_leveler, z-score
denominator, now dayStepSize) that actually moved the classification,**
not just left it identical to the decimal:

| Point | Before (per-image Events) | After (day_step_size-binned Events) |
|---|---|---|
| centroid | decrease 0.914 / unchanged 0.043 | decrease 0.820 / unchanged **0.127** |
| red_pt_1 | decrease 0.911 / unchanged 0.045 | decrease 0.836 / unchanged **0.109** |
| red_pt_2 | decrease 0.914 / unchanged 0.043 | decrease 0.904 / unchanged 0.052 |

`unchanged` roughly tripled at two of the three points. Binned evidence
count came back 123 (vs. 352 raw images before), same order of magnitude
as the ~143 hand-estimated above. Still `decrease`-dominant everywhere -
not a full flip to match the GUI's mostly-green render - but real,
meaningful, confirmed movement, unlike the three earlier fixes that
validated correctly but changed nothing. Whatever remains of the
disagreement is now a smaller gap than before this fix, and the most
promising remaining candidates are the still-open modality-resolution
bug and `interpret.py`'s possibly-wrong `year_of_change()` definition
(see below) rather than anything already covered by these four fixes.

## Two more files: modality resolution is additive (not priority-based), and interpret.py's real design (2026-08-10)

Same session, two more files fetched: `502.7-1h5-HarmonicFunctions`
(`CommonCode2:/502.7-Harmonics/502.7-1h5-HarmonicFunctions`) and
`6002.C2-BULCD-Module-analyzeOutputs` (the real `afn_interpretBULCDResult`,
`r-2902-Dev` - a different repo than the `r-2903-Dev` files fetched
earlier). Per user's explicit sequencing choice (dayStepSize first, these
after), the modality/R2/config-transcription fixes below were implemented
and validated later the same session - see "Modality/R2 fixes
implemented" at the end of this entry. `interpret.py`'s redesign remains
unimplemented, a separate follow-up.

**Modality-priority resolution: our "richest shape wins" assumption was
wrong.** Real `afn_determineHarmonicIndependentsViaModalityDictionary`:
```js
if (vm.constant) { var harmonicList = ee.List(['constant']) }
if (vm.linear) { harmonicList = harmonicList.add('t') }
if (vm.unimodal) { harmonicList = harmonicList.add('cos').add('sin') }
if (vm.bimodal) { harmonicList = harmonicList.add('cos2').add('sin2') }
if (vm.trimodal) { harmonicList = harmonicList.add('cos3').add('sin3') }
```
This is ADDITIVE - every true flag's terms concatenate onto the list, not
"pick the richest one." `bulcd/inputs.py`'s `_select_modality_regressors()`
currently picks exactly one branch and returns early
(trimodal > bimodal > unimodal > linear > constant). For cell 8C
specifically (only `unimodal` relevant, and our unimodal branch already
hardcodes `"constant"` regardless of the flag's own value) this produces
the same result either way - didn't affect any of this session's cell 8C
numbers - but it's a confirmed, real bug for any config with multiple
simultaneous flags. Also confirms `constant` must be `true` for this
function to even run without erroring (`harmonicList` is only
initialized inside `if (vm.constant)`), matching the real
`BULCargumentDictionaryPlus` Console dump from earlier in this session
(`constant: true, unimodal: true` together) -
`configs/cell_8c_comparison.yaml` currently has `constant: false`, a
transcription error on the assistant's part, queued to fix alongside the
additive-resolution rewrite.

**R2 formula, also confirmed and different from ours.** Real
`afn_getRMSEandR2`:
```js
var dof = n.subtract(Independents.length())
var rss = rmsr.pow(2).multiply(n)          // rmsr = regression reducer's own RMS-residual output
var sSquared = rss.divide(dof)
var yVariance = imageCollection.select(dependent).reduce(ee.Reducer.sampleVariance())
var rSquareAdj = ee.Image(1).subtract(sSquared.divide(yVariance))
```
Production computes ADJUSTED R2 (dof-corrected residual variance over
sample variance of y), not this rebuild's plain `1 - SS_res/SS_tot`. R2
is diagnostic-only (doesn't feed the Bayesian engine itself), so lower
priority than the z-score fixes already made, but a real, now-fixable
discrepancy.

**Modality/R2 fixes implemented (2026-08-10, later same session).**
`_select_modality_regressors()` rewritten to be additive (`constant`
always included as the base - production would crash without it, and
every real confirmed run has it true anyway - then `t`/`cos+sin`/
`cos2+sin2`/`cos3+sin3` appended per whichever flags are true, in
production's own order). `_fit_expectation_model()`'s R2 rewritten to
the confirmed adjusted formula, reusing the `linearRegression` reducer's
own `residuals` output (RMS residual) directly instead of manually
re-deriving sum-of-squared-residuals - a simplification as well as a
fix. `configs/cell_8c_comparison.yaml`'s `modality.constant` corrected
from `false` to `true`. 2 tests updated (`test_select_modality_regressors_*`),
36 total, all pass.

**VALIDATED against real Earth Engine, same three points as every check
in this thread: numbers came back IDENTICAL to the decimal to the
post-dayStepSize-fix values.** Exactly as predicted before implementing -
R2 never feeds the Bayesian engine at all, and cell 8C's config only
ever exercises the unimodal-alone regressor path regardless of whether
`constant` is separately true (the old "richest wins" logic already
hardcoded `"constant"` into the unimodal branch). Real, confirmed bugs,
correctly fixed, but classification-inert for this specific config -
useful confirmation that the remaining GUI-vs-rebuild gap sits elsewhere
(most likely still-missing pieces like `BULCD-AnalysisParameters-v5` or
the cloud-masking module, or simply normal pixel-level variance between
two now-much-more-similar but not bit-identical implementations).

**`interpret.py`'s `year_of_change()` may have the wrong definition
entirely.** Real `afn_interpretBULCDResult`'s timing logic:
```js
var highChangeProb = prob1.gt(timingThreshold)          // per-timestep boolean, prob1 = decrease band
var changeIndices = highChangeProb.multiply(indicesIm)  // step index where crossed, else 0
// ...MAX-fill zeros, then reduce(min) = the FIRST index that ever crossed...
var firstChange = changeIndices.reduce(ee.Reducer.min())
```
Production's real "when did it change" is simply the FIRST timestep
where probability ever crossed a threshold - no requirement that the
classification stay flipped through to the present. This rebuild's
`year_of_change()` requires an UNBROKEN RUN reaching the last Event - a
meaningfully stricter, different definition, and a very plausible actual
explanation for the previously-documented 12-year detection lag finding
(see "Year of change" above) - production doesn't wait for sustained
reclassification, it just asks "did the probability ever cross a line."
There's also a separate, simpler `wasItEver`/`howOftenWasIt` mechanism
(did probability ever cross a threshold anywhere in the stack, with NO
run-length requirement at all) that directly covers the "changed, then
recovered" case `interpret.py`'s own docstring flags as explicitly
unhandled. Also notable: production cross-checks the Bayesian
probability threshold against the RAW index means themselves
(`expectationPeriodSummaryValue`/`targetPeriodSummaryValue` thresholds,
part of the still-missing `BULCD-AnalysisParameters-v5`) before calling
something a confirmed "large drop" - a real design pattern (don't trust
the probability alone) this rebuild doesn't currently have an equivalent
of.

**`BULCD-AnalysisParameters-v5` obtained (2026-08-10, later same
session)** - the last missing parameter file, found by the user directly
(not via Code Editor navigation this time). Real values:
`dropThresholdToDenoteChange: 0.59`, `gainThresholdToDenoteChange: 0.39`
(asymmetric - easier to flag "gain" than "drop"), `expPeriodMeanThreshold: 0.5`,
`targetPeriodMeanThreshold: 0.4`, `wasItEverType: 'down'`,
`wasItEverComparison: 'gt'`, `wasItEverValue: 0.3`, `timingThreshhold: 0.3`
(same value reused for both `wasItEver` and the timing/first-crossing
logic), `maxExportPixels: 1e13` (matches this rebuild's existing
`ExportConfig.max_pixels` default exactly - a nice independent
confirmation). Per the file's own comment, these are all *post-run*
thresholds applied to `finalBULCprobs`/`probabilityStackThroughTime` -
they don't affect `run_bulcd()`'s output at all, only `interpret.py`'s
still-unimplemented redesign. Not yet used in code.

## Cloud masking was wrong for every sensor - fixed, still inert (2026-08-10)

Re-reading `515-gatherCollections27b.txt` (already fetched, saved from
the `dayStepSize` investigation) surfaced two more real, previously
unchecked discrepancies, found without any new fetching:

**Landsat: production uses two different cloud-mask functions, this
rebuild used one unified one for all four sensors.**
`afn_cloudMaskIC_L5andL7` checks only QA_PIXEL bits 3 (cloud shadow) and
4 (cloud). `maskSrCloudsL8andL9` checks bits 0-4 (fill, dilated cloud,
cirrus, cloud, cloud shadow) via `bitwiseAnd(0b11111)` PLUS a separate
`QA_RADSAT` saturation mask entirely. `_mask_landsat_clouds()` checked
bits `{1,3,4}` for every sensor - an extra, incorrect bit-1 check for
L5/L7, and missing bit-0/bit-2/the saturation mask entirely for L8/L9.

**Sentinel-2: production doesn't use s2cloudless at all.** It uses
Google Cloud Score+ (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`, band
`cs` >= 0.60) - confirmed as the *only* live path for any year >= 2015
(a comment notes this was switched over in an Oct 2024 update: "cloudscore
now used for 2015+"), which covers every year this rebuild's configs
use. The s2cloudless community recipe (cloud-probability join + NIR
dark-pixel shadow projection) implemented when S2 support was first
added is a completely different algorithm, not a parameter variant.

**Fixed**: split `_mask_landsat_clouds()` into
`_mask_landsat_clouds_l5_l7()`/`_mask_landsat_clouds_l8_l9()`, dispatched
by sensor code. Replaced S2's entire cloud-mask implementation with
Cloud Score+ via `.linkCollection()` (matching production's own real
code path, `linkedS2AndCloudScorePlusIC`) - genuinely simpler than the
s2cloudless recipe it replaced. Removed `S2CloudMaskConfig`/
`SensorEvidenceConfig.s2_cloud_mask` entirely (the legacy `s2cloudless`
dictionary in `BULCD-InputParameters-v5` is vestigial in production's
real, currently-running code - confirmed by the source itself, not
inferred). 1 test removed (`test_s2_cloud_mask_rejected_for_non_s2_sensor`,
no longer applicable), 1 updated; 35 total, all pass.

**VALIDATED against real Earth Engine, same three points as every check
in this thread: numbers moved only slightly - nowhere near the
`dayStepSize` fix's clear shift.** E.g. centroid: `decrease 0.8198/unchanged
0.1271` -> `decrease 0.8195/unchanged 0.1274` (~0.03 percentage points).
Real, confirmed, correctly-fixed bugs across every one of cell 8C's three
enabled sensors, but essentially inert for this specific config/AOI -
the fifth of eight total fixes this session (after the three that were
also inert: `initializing_leveler`, the z-score formula, modality/R2) to
validate correctly without moving the classification. `dayStepSize`
remains the only fix in this entire investigation that produced a real,
measurable shift.

**Assessment at this point:** seven real, source-confirmed bugs fixed
across the whole Bayesian core and evidence-assembly pipeline this
session, six new production source files obtained. Cell 8C is closer to
the GUI's render than when this investigation started (dayStepSize alone
moved `unchanged` from ~4% to ~13% at two of three points) but still
`decrease`-dominant, not a match. Given how consistently every fix since
`dayStepSize` has validated correct but changed nothing, further
single-formula fixes are unlikely to close the remaining gap by
themselves - the two candidates still genuinely unfetched
(`BULCD-ExportParameters-v5`, and whatever `512.BULC-D CloudMasking`
actually contains, though it appears to be dead code in the confirmed
live path) are lower-confidence leads than anything found so far. This
may be the point of diminishing returns for this specific investigation
thread.

## Root cause found: two mask-propagation bugs, not a formula mismatch (2026-08-10)

Per the user's direction ("I would like to continue hunting for the
problem", then "yes, trace it"), rather than settling for the assessment
above, did a full step-by-step trace of the Bayesian fold. First surfaced
a real but secondary visual artifact (a Sentinel-2 MGRS tile-overlap
seam at cell 8C's boundary, both sides still majority-red - confirmed
real via footprint geometry, confirmed NOT the primary cause since it
didn't explain the AOI-wide red bias). Then, per "use python to help
you": pulled the real per-step z-score bin sequence at the cell 8C
centroid (123 steps, 2024-06 through 2025-mid, via
`organized.lof_zscore` + `_bin_zscore()`) into a local JSON file and
hand-simulated `bulc.run_bulc()`'s fold in plain Python - first attempt
used two separate `aggregate_array()` calls to pull dates and bins
independently, which (not caught immediately) silently returned
misaligned pairs under load; fixed by extracting both values from the
SAME `FeatureCollection` feature via `.getInfo()`, querying in quarterly
chunks rather than one large range.

With correctly-aligned data (69 valid steps, 54 masked/no-data - 44% of
the full 123-step sequence), a Python simulation treating masked steps
as true no-ops (skip entirely, prior carries forward unchanged) produced
`unchanged ≈ 90.6%` - matching the evidence's own bin distribution and
the GUI's expected render. Forcing the simulation to instead replicate
the pipeline's real (at-the-time) masking behavior reproduced the
observed `decrease`-dominant discrepancy almost exactly. This isolated
the entire remaining gap to mask handling specifically, not any further
formula/parameter mismatch - a real turning point after seven fixes that
had each validated correct but moved nothing.

Direct EE queries then confirmed two distinct bugs, both now fixed (full
writeup: [decisions/0009](decisions/0009-masking-bugs-resolve-the-classification-gap.md)):

1. **`engine.py`'s `_bin_to_update_factors()`**: its `.where()` chain
   doesn't propagate the input bin image's mask - confirmed directly at
   a known-masked date (2024-03-17, cell 8C centroid), it returned
   `[0.83, 0.08, 0.08]` (bin 1's row, the single most extreme "decrease"
   value in the whole matrix) instead of staying masked. Every one of
   the 54 masked/no-data steps was silently injected as maximum-
   confidence "decrease" evidence. Fix: `.updateMask(binned_image.mask())`
   on the return value.
2. **`bulc.py`'s `run_bulc()`**: `bayes_update()` used to call
   `.unmask(prior)` immediately, before `posterior_leveler`'s `dampen()`
   ran - so a no-data step's already-restored-to-prior posterior still
   got pulled partway toward uniform. Confirmed against the real
   `BULC-Minimal-Module-107` source (`legacy/BULC-Minimal-Module-107.txt`
   lines 590-600): production rebalances the masked, valid-pixel-only
   slice FIRST, then merges onto the untouched prior via `.where(...)` -
   rebalance-then-merge, not merge-then-rebalance. Fix: `bayes_update()`
   no longer unmasks; `_step()` now applies `dampen()`/`discount()` to
   the still-masked posterior (both mask-preserving arithmetic, so
   correct no-ops there) and calls `.unmask(prior)` exactly once, at the
   end.

**VALIDATED against real Earth Engine, same three cell 8C points used
throughout this investigation.** Bug 1 alone, for the first time in this
investigation, flipped all three points to `unchanged`-dominant:

| Point | Before (7 prior fixes only) | After bug 1 | After bug 1 + bug 2 |
|---|---|---|---|
| centroid | decrease 0.82 / unchanged 0.13 | decrease 0.128 / unchanged 0.739 | decrease 0.044 / **unchanged 0.906** |
| red_pt_1 | decrease-dominant | decrease 0.097 / unchanged 0.805 | decrease 0.043 / **unchanged 0.914** |
| red_pt_2 | decrease-dominant | decrease 0.203 / unchanged 0.628 | decrease 0.112 / **unchanged 0.833** |

35/35 tests still pass (this masking behavior isn't unit-testable
without a live EE session - same caveat as the rest of this codebase's
image-math logic).

Both bugs share one root cause worth generalizing: EE's `.where()` does
not propagate a masked *condition*'s mask onto its output, and
`.unmask(x)` unconditionally fills masked pixels regardless of whether
that's semantically correct at that specific point in a multi-step
chain. This explains, in hindsight, why every one of the seven earlier
fixes (posterior_leveler, initializing_leveler, z-score formula,
dayStepSize, modality, R2, cloud masking) validated correct but left the
classification almost untouched except for dayStepSize: none of them
touched mask handling, so all were real, correct improvements running
downstream of these two bugs' systematically wrong "decrease" signal on
every no-data day. Likely the resolution of this entire investigation
thread - still only validated at three points, not a full-AOI visual
comparison against the actual GUI render.

## Expectation/target split restored, and a real cell 8C asset export (2026-08-11)

The user relayed explicit direction from their boss: match the legacy
GUI's structure as closely as possible, not just its formulas. A
clarifying question confirmed this means **full structural parity** -
reversing [decisions/0003](decisions/0003-continuous-evidence-replaces-expectation-target-split.md),
which had collapsed the legacy's discrete expectation-period/target-period
comparison into one continuous, indefinite evidence stream (previously
documented as the modernization's *primary* objective, straight from the
Vision doc). See [decisions/0010](decisions/0010-restore-expectation-target-split-for-gui-parity.md)
for the full decision.

Confirmed directly from `legacy/BULCD-InputParameters-v5.txt` (lines
61-253): `expectationCollectionParameters` and `targetCollectionParameters`
are two structurally identical per-sensor dictionaries, genuinely
different between periods in the real example (e.g. L5's
`CloudCoverThreshold` is 45 in expectation vs. 15 in target).
`EvidenceConfig` now holds `expectation`/`target`, each a new
`EvidencePeriodConfig`; `organize_inputs()` fits the harmonic model on
the expectation collection but scores z-scores over the target
collection only, restoring the legacy's literal one-shot comparison
instead of scoring the entire archive. `engine.py`/`bulc.py` needed no
logic changes - both already just consume whatever z-score stream
`organize_inputs()` hands them.

Every existing config (`configs/example.yaml`, `configs/cell_8c_comparison.yaml`)
and every `scripts/debug_*.py`/`export_year_disturbance_map.py` script
that hardcoded the old flat `EvidenceConfig(sensors=..., expectation_first_year=...)`
shape was updated to the new two-period shape. `cell_8c_comparison.yaml`'s
rewrite used the exact real values its own header comments already
documented (expectation: 2024, target: 2025, both DOY 74-288, cloud 70),
so it's a mechanical restructuring, not new research. Several debug
scripts needed a real judgment call about what target window to test
against now that "extend the evidence window to the present" is no
longer valid - documented inline in each. `scripts/debug_long_baseline_disturbance.py`'s
original premise (demonstrating a long-continuous-stream compounding
failure, [decisions/0005](decisions/0005-recency-weighting-extension.md)'s
motivating case) is now structurally moot under the restored split and
was rewritten to test a related but different question instead. All 33
tests pass after rewriting the config-shape-dependent ones.

**Open follow-up, flagged in decisions/0010:** `bulcd/interpret.py`'s
`year_of_change()`/`disturbance_mask_for_year()` were built to search a
long multi-year `classification_stack`, now typically just the target
period's short single-season Event sequence - their semantics haven't
been reconsidered for that shape.

**Revalidated 2026-08-11 against the real GUI with side-by-side renders
AND a computed diff image: a spatially coherent gap, not just noise.**
The session's real GEE export of cell 8C's `final_probabilities`
(`scripts/export_cell_8c_comparison.py`, task id
`T7HB4PIODQR5L7H4GGIHEETS`, to
`projects/bulcd-python-rebuild/assets/bulcd_cell8c_comparison_final_probabilities`)
was compared by the user directly against the legacy GUI's actual render
for cell 8C - both R=decrease/G=unchanged/B=increase RGB thumbnails over
the same region - then diffed via `gui_image.subtract(rebuild_image)` in
GEE, rendered with the same RGB convention. The restored expectation/target
split (this entry) narrowed the gap from the earlier continuous-stream
design (every prior cell 8C validation, decisions/0009 and earlier, ran
under that old design) but didn't fully close it.

Eyeballing the two renders side by side first suggested a fairly small
gap: the two large, contiguous, geographically obvious disturbance
features - a dense red/blue cluster in the center-north of the cell, and
a diagonal red string following a valley/road corridor near Longmire -
line up closely between GUI and rebuild, same locations and shapes, with
the rebuild's `unchanged` regions looking mostly clean aside from
scattered red flecking.

**The subtract() image told a more complete story.** It's dominated by a
large-scale, roughly diagonal, spatially COHERENT split - not scattered
noise: the west/upper-left portion of the cell is strongly red (GUI's
`decrease` band exceeds the rebuild's there by a wide margin), the
east/lower-right portion is strongly dark blue/navy (GUI's `increase`
band exceeds the rebuild's), and the valley/road corridor near Longmire
shows green (GUI's `unchanged` exceeds the rebuild's slightly there,
consistent with both agreeing that corridor is disturbed). In plain
terms: the GUI calls substantially more `decrease` on the west side and
more `increase` on the east side than the rebuild does, across large
contiguous areas - not just isolated speckle, and a materially different
(and more concerning) picture than the side-by-side renders alone
suggested. **Caveat:** a raw `subtract()` with no `abs()` only shows
where the GUI's per-band value exceeds the rebuild's (positive
difference) - pixels where the rebuild scored HIGHER than the GUI render
as black, indistinguishable from true agreement, so this image likely
under-represents total disagreement and shows only one direction of it.

Importantly, the gap is NOT attributable to a known approximation:
`configs/cell_8c_comparison.yaml`'s `dampening_factor`/`posterior_leveler`/
`initializing_leveler` are all confirmed real production values (see
that config's own header comments), not placeholders -
`scripts/run_cell_8c_comparison.py` and `scripts/export_cell_8c_comparison.py`
previously carried a stale docstring/print statement claiming otherwise
(true before `BULC-Minimal-Module-107` was obtained on 2026-08-10, false
since), fixed alongside this entry.

The diagonal shape of the split roughly tracks the cell's own tilted
(Landsat-swath-like) orientation, which is suggestive but NOT confirmed
as causal.

**Hypothesis (a) - per-sensor coverage/tiling boundary - RULED OUT
2026-08-11.** `scripts/debug_cell_8c_sensor_coverage.py` (new) built a
target-period-only, single-sensor `EvidencePeriodConfig` for each of
L8/L9/S2 via the real `assemble_evidence_collection()`, counted valid
day_step_size-bin observations per pixel, and rendered an RGB composite
(R=L8, G=L9, B=S2 counts). Whole-cell means: L8 ≈ 11.4, L9 ≈ 12.9, S2 ≈
26.7 valid bins (S2's higher revisit rate, as expected) - but spatially,
the composite showed a mottled, semi-uniform pattern (S2 dominant almost
everywhere, scattered patchiness), no boundary lining up with the diff's
diagonal split. Sensor coverage is not the cause.

Remaining, still-unconfirmed candidates at the time: (b) a real
geographic/land-management gradient (e.g. Mount Rainier NP boundary near
Longmire vs. more actively managed land to the west) that both GUI and
rebuild partially detect but weight differently - not a bug, a
sensitivity difference; (c) snow/phenology contamination correlated with
elevation, given the wide DOY 74-288 window and Rainier's elevation
gradient; (d) some other still-unconfirmed formula/parameter difference
that happens to manifest as a regional bias rather than a uniform shift.

**Hypothesis (c) PARTIALLY SUPPORTED 2026-08-12 - explains the EAST half
of the gap, not the whole thing.** `scripts/debug_cell_8c_expectation_fit_quality.py`
(new) called `organize_inputs()` directly (real, unchanged - no engine
code needed, it already returns `expectation_r2`/`expectation_residual_stddev`)
and rendered those plus the target period's mean z-score spatially, plus
elevation/aspect from `USGS/SRTMGL1_003`, over the same cell 8C region -
then compared west-half vs. east-half means (split at the AOI's own
longitude median) and inspected the rendered thumbnails directly (not
just the aggregate numbers).

West / east numbers: `expectation_r2` 0.360 / 0.397 (no real
difference); `expectation_residual_stddev` 0.054 / 0.073 (east ~35%
noisier); mean target-period z-score -0.032 / -0.138 (both negative -
the rebuild's own fit skews slightly `decrease`-leaning cell-wide - but
east is ~4x more negative than west); elevation 1012m / 1326m (east is
genuinely ~30% higher terrain, confirmed visually via the rendered DEM
thumbnail's branching valley/ridge pattern, not just two flat numbers);
aspect 174 / 187 degrees (both south-facing, essentially identical - NOT
a differentiator, ruled out). The rendered `mean_zscore` thumbnail
confirms this isn't a split-point artifact: the east two-thirds of the
cell is visibly, coherently blue (negative z-score) while the west third
is closer to neutral/faint red.

**This directly explains the EAST side of the original GUI-vs-rebuild
diff**: a more negative z-score there pushes the rebuild's own
classification toward `decrease` and away from `increase` - exactly the
direction of the diff on that side (GUI scores more `increase` in the
east than the rebuild does; a real negative z-score bias in the
rebuild's own output is a sufficient, demonstrated cause for the rebuild
under-calling `increase` there).

**It does NOT explain the WEST side.** The rebuild's own mean z-score
there is close to neutral (-0.032, not positive), so there's no
comparable bias pushing the rebuild away from `decrease` - the rebuild
simply isn't detecting as strong a `decrease` signal in the west as the
GUI apparently does. Still open as of this entry.

**"Wider/multi-year GUI expectation baseline" candidate - RULED OUT
2026-08-12.** Checked `guiBULCD.rtf` directly for what the Expectation
Period widget actually defaults to (both the per-sensor tabs, e.g.
`l8years_t` ~line 2948, and the "Cross-Sensors" panel actually used for
cell 8C's real run, `csyears_t` ~line 1042): it's a bank of individual
year checkboxes (2013-2025), every one `ui.Checkbox(year, false)` -
unchecked - with the backing list (`chosen`/
`crossSensorDictionary["year"]`) initialized to `[]`. There is no
built-in default expectation-year range at all - the GUI ships with
nothing selected, and the user must explicitly check which year(s)
apply (a genuine multi-select; a user could pick a contiguous range or a
scattered set of years). But the real cell 8C run's actual selection was
already pulled directly from the GUI's own Console output
(`BULCargumentDictionaryPlus`, see `configs/cell_8c_comparison.yaml`'s
header comment): a single year, 2024 - exactly what the config already
uses. There's no divergence to find here; the rebuild already matches
the real run's actual selection, not a guessed default. This closes off
that specific candidate - the west-side gap's cause is still
unidentified.

Elevation correlating with both the higher `residual_stddev` and the
more negative z-score bias in the same (east) region is consistent with
hypothesis (c)'s snow/phenology mechanism (a single-year, partial-DOY
74-288 harmonic fit is inherently more exposed to a bad early/late-season
snow read at higher elevation than a full-year or multi-year baseline
would be) - real, aligned evidence, but the correlation with elevation
is confirmed while snow/phenology as the specific physical cause of that
correlation remains a plausible, unconfirmed mechanism, not proven.

Bottom line: the EAST-side portion of cell 8C's diagonal gap has a real,
demonstrated cause inside this rebuild's own math (an elevation-
correlated negative z-score bias, not a GUI-side mystery). The WEST-side
portion remains genuinely open - not sensor coverage, not a leveler
placeholder, and not (by itself) the same z-score-bias mechanism. See
[decisions/0010](decisions/0010-restore-expectation-target-split-for-gui-parity.md)'s
matching entry for the full numbers and thumbnails referenced.
