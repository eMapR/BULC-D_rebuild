# Decisions

One file per significant "why did we choose X over Y" call in this
project — context, decision, consequences. See `../findings.md` for the
dated experiment/validation log that most of these decisions are based
on, and `../../CLAUDE.md` for current stable project state.

- [0001 — Platform: Python + `earthengine-api`](0001-python-earthengine-platform.md)
- [0002 — Dedicated GEE Cloud Project](0002-dedicated-gee-cloud-project.md)
- [0003 — Continuous Evidence Stream + Global Expectation Baseline Window](0003-continuous-evidence-replaces-expectation-target-split.md)
- [0004 — Dampening Factor Default Changed from 1.0 to 0.5](0004-dampening-factor-default-0.5.md)
- [0005 — Recency Weighting: A Genuine Algorithmic Addition, Off by Default](0005-recency-weighting-extension.md)
- [0006 — Standard Public Datasets as Water/Forest Mask Substitutes](0006-standard-dataset-masks.md)

New decisions get the next number, `000N-short-title.md`, using the same
Context/Decision/Consequences shape.
