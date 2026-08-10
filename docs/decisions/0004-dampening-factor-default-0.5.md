# 0004 — Dampening Factor Default Changed from 1.0 to 0.5

**Status:** Decided/applied 2026-07-29

## Context

Cardille & Fortin (2016)'s dampening factor `d` (`0 < d ≤ 1`) flattens
each Bayesian update step toward uniform:
`dampened = d * raw_update_factor + (1 - d) / n_classes`. Their own
tested example used `d = 0.5`. `BULCAdvancedParams.dampening_factor`
originally defaulted to `1.0` (no dampening) — an unconsidered default,
not a validated one.

First live-EE testing (see `docs/findings.md` "First live-EE
verification") found `d=1.0` produces extreme overconfidence over many
sequential Events — at one test pixel, `d=1.0` vs `d=0.5` gave the same
classification but confidence differing by ~48 orders of magnitude,
exactly the failure mode Cardille & Fortin section 4.6 describes as the
reason the factor exists.

## Decision

Change `BULCAdvancedParams.dampening_factor`'s default from `1.0` to
`0.5` (matching the paper's own tested value) in `schema.py`, `loader.py`,
and `bulc.py`'s `run_bulc()` signature. `d=1.0` remains fully supported
by explicit config — it's just no longer the silent default.

## Consequences

A config that doesn't explicitly think about dampening no longer
silently runs with none. This is a real mitigant for compounding
overconfidence, not a complete fix for the related long-baseline
detection-lag problem — see [0005](0005-recency-weighting-extension.md).

**Open gap (found 2026-08-10, not yet reconciled):** real production
dampening is not one scalar — it's three separate "levelers"
(`initializingLeveler`/`transitionLeveler`/`posteriorLeveler`) plus two
minimum floors (see `docs/findings.md` "Real production BULC-D
parameters"). `bulc.py`'s `dampen()` is a structural simplification of
production behavior, not just a wrong number. Per this project's standing
rule (get the source, don't guess at the math), the right next step is
fetching `BULC-Module-Current/BULC-Minimal-Module-107`'s real source
(`alemlakes/r-2909-BULC-Releases`) rather than reverse-engineering three
formulas from one instance's numbers.
