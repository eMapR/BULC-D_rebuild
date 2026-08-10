# 0008 — `dayStepSize` Is a Temporal Binning Window, Not a Sampling Parameter

**Status:** Implemented 2026-08-10

## Context

`EvidenceConfig.day_step_size` (legacy `dayStepSize`) existed as a parsed
config field since this project's early scaffold, confirmed as a real
GUI parameter (`3` for the cell 8C comparison run), but was never
actually used anywhere in `bulcd/inputs.py` — dead configuration. Its
real role was unknown until the user fetched
`515-gatherCollections27b`'s real source
(`CommonCode2:515.ImageCollectionFilteringAndGathering/515-gatherCollections27b`,
the real `afn_gatherCollectionsAndReduce`).

The real source shows `dayStepSize` divides the evidence date range into
fixed-width bins, gathers every image from every enabled sensor landing
in each bin, and takes the median across the whole bin — collapsing
however many raw images fell in a window into exactly one "Event."
`assemble_evidence_collection()` instead treated every single cloud-free
image as its own independent Event: ~350 raw images for cell 8C's DOY
74–288 window, versus production's real ~143 Events at `day_step_size=3`
over the same data — more than twice as many sequential Bayesian updates
over the same underlying evidence.

This surfaced during a live GUI-vs-rebuild comparison for cell 8C (see
`docs/findings.md`), after three earlier confirmed fixes
([0007](0007-posterior-leveler-regularization.md)'s `posterior_leveler`,
`initializing_leveler`, and the z-score denominator formula) all
validated correctly but left the classification unchanged to the
decimal — ruling out further tuning-level explanations and pointing at
evidence composition instead.

## Decision

Implement the real binning mechanism: `_evidence_date_and_doy_bounds()`
computes the union (not intersection) of every enabled sensor's resolved
year/DOY range, matching production's combined `groupStartDOY`/
`groupEndDOY`/`whichYears`. `_bin_evidence_by_day_step()` bins the merged
per-sensor evidence stream into `day_step_size`-day windows and
median-combines each bin into one image, using `ee.Join.saveAll()` to
group images by date-range membership efficiently. Empty bins reproduce
production's "dummy image" safeguard (preventing `.median()` from
collapsing to a zero-band result) via a self-masked placeholder image
unioned into every bin before reducing.

**Engineering note:** the first implementation used `.map()` over the
bin list with an independent `.filterDate()` call inside each bin — each
of ~140 bins re-scanning the full evidence collection independently.
This built a computation graph large enough to hit "User memory limit
exceeded" even for a single-point query, worse than any prior full-cell
operation in this project. `ee.Join.saveAll()` — the standard EE idiom
for grouping one collection's elements by a condition against another —
resolved this completely.

## Consequences

VALIDATED against real Earth Engine at the three points used throughout
this investigation: this is the **first of four confirmed fixes that
actually moved the classification**, not just validated correctly and
left the numbers identical. `unchanged` roughly tripled at two of three
points (e.g. centroid: `decrease 0.914/unchanged 0.043` →
`decrease 0.820/unchanged 0.127`). Still `decrease`-dominant everywhere —
not a full flip to match the GUI's mostly-`unchanged` render — but real,
meaningful movement. See `docs/findings.md` "dayStepSize confirmed and
implemented" for the full validation table.

Remaining candidates for the rest of the gap: modality-resolution being
additive rather than priority-based (confirmed wrong, not yet fixed —
see `docs/findings.md`), and R²'s adjusted-formula difference (diagnostic
only, unlikely to matter here). Neither is expected to be as large as
this fix, given cell 8C's specific config only ever exercises the
`unimodal`-alone regressor path either way.
