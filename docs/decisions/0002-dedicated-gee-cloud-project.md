# 0002 — Dedicated GEE Cloud Project

**Status:** Decided 2026-07-29

## Context

Running any real Earth Engine code needs a registered GEE cloud project.
The sibling GeoTimeSeries project's `eastern-cascades-bugnet` project was
considered as a reuse option.

## Decision

`bulcd` uses its own dedicated project, **`bulcd-python-rebuild`** — not
`eastern-cascades-bugnet`. Registered for Earth Engine access and
confirmed working via `ee.Initialize(project="bulcd-python-rebuild")`.

## Consequences

Isolates this project's Earth Engine usage/billing from GeoTimeSeries.
Unblocked real testing against live Earth Engine for the first time (see
`docs/findings.md` "First live-EE verification").
