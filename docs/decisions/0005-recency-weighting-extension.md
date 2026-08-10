# 0005 — Recency Weighting: A Genuine Algorithmic Addition, Off by Default

**Status:** Decided/implemented 2026-07-30

## Context

Even at `dampening_factor=0.5`, a pathological case surfaced: a pixel
with 14 years of stable baseline evidence followed by 9 years of extreme,
sustained disturbance evidence still classified as "unchanged" with
99.99999999936% confidence (see `docs/findings.md` "Major finding: long
stable baselines can mask real disturbance"). A dampening sweep down to
`d=0.02` reduced the overconfidence but never flipped the classification
to the correct answer — dampening alone was confirmed insufficient for
this failure mode.

This is a structural property of naive sequential Bayesian updating over
long, mostly-stable evidence streams (see
[0003](0003-continuous-evidence-replaces-expectation-target-split.md)),
directly in tension with the project's goal of using the full multi-decade
Landsat archive as evidence — more archive means longer baselines, which
makes this worse, not better.

## Decision

Add `discount()` to `bulc.py`, and a new optional `recency_factor`
parameter to `run_bulc()`/`run_bulcd()` (threaded through
`BULCAdvancedParams.recency_factor`, validated to `0 < recency_factor ≤ 1`).
After each Bayesian update step, the posterior is raised to the power
`recency_factor` and renormalized
(`posterior^gamma / sum(posterior^gamma)`), causing each step's influence
on the running posterior to decay geometrically relative to the most
recent step.

**This is NOT part of Cardille & Fortin (2016) or Willis (2022)** — a
genuine departure from the reconstructed classic method, not a port of
anything in the reference material.

**Default stays `recency_factor=1.0` (off).** At `gamma=1.0` this is an
exact no-op, so the engine remains faithful to the reconstructed classic
method unless a caller explicitly opts in — required by the "preserve the
Bayesian updating core" modernization goal. Unlike
[0004](0004-dampening-factor-default-0.5.md)'s `dampening_factor` (whose
`0.5` default matches a published tested value), there is no published
value for `recency_factor` anywhere in the reference material — it is
validated against one stark failure case plus three regression checks,
not broadly validated, so it must be turned on deliberately per-config,
not assumed as a new silent default.

## Consequences

At `gamma=0.98`, the long-baseline case flips to the correct
classification while the two unambiguous test cases (stable, B&B fire)
stay correctly classified with high confidence — see `docs/findings.md`
"Recency weighting" for the full validation table. It also measurably
(but not completely) reduces the ~12-year detection lag found in "Year of
change... a major lag finding" — monotonically closer to the true
ignition date as `recency_factor` decreases, but not exact even at 0.95.
Anyone using `disturbance_mask_for_year()`/`year_of_change()` needs to
know this lag exists before trusting a specific year's map, especially at
the library default.
