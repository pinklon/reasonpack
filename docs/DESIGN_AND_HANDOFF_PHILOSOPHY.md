# Design and Handoff Philosophy

## The package is part of the product

Internal tooling often dies in the gap between “works on my machine” and “another capable person can use it without me.”

This kit treats handoff quality as an engineering property.

The goal is not exhaustive documentation. It is **minimum sufficient durable context**.

## What information deserves to survive

Preserve information when losing it would force the next person to re-reason a meaningful decision:

- why the product exists;
- what it does today;
- what it intentionally does not do;
- architecture and trust boundaries;
- package/interface contracts;
- dependencies and install mutations;
- expected failure semantics;
- acceptance criteria;
- security/rights constraints;
- success measures;
- key tradeoffs;
- extension boundaries.

Do not document every shell statement twice. Source code already preserves implementation detail.

## Different documents have different reader jobs

A good package supports multiple depths:

### Five-minute evaluator

Needs product tour, feature posture, value proposition and architecture map.

### New user

Needs installation, doctor/self-test, normal commands and troubleshooting.

### Operator/support owner

Needs dependency/support matrix, failure classes, update/removal model and security boundaries.

### Developer

Needs architecture, package contract, design decisions, tests and extension rules.

### Product/engineering manager

Needs PRD, vision, roadmap, success metrics, risks and what-good-looks-like.

Trying to make one README serve all five readers usually produces either a wall of text or a useless brochure.

## Documentation quality test

A document is useful when it changes what the recipient can correctly decide or do.

Good documentation contains semantics such as:

- **because** — rationale;
- **must / must not** — invariant;
- **means** — interpretation;
- **if / then** — operating behavior;
- **current / next** — lifecycle posture;
- **evidence** — how a claim is checked.

A page with only headings and bullets may look organized while preserving almost no reasoning.

## Precision over ceremony

Professional does not mean bureaucratic.

We do not need:

- a 50-page template because the governance office has one;
- duplicate requirement prose in six places;
- fake KPI history;
- diagrams that introduce concepts the code does not implement.

We do need the recipient to understand the system accurately.

## Handoff acceptance question

The final test is simple:

> If the original author disappears for a month, can another strong engineer operate and evolve the product without inventing its intent?

If not, more of the important context needs to become durable.
