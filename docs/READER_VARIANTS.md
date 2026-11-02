# ReasonPack Reader variants

The canonical v1.1.1 skill is a routing overlay. Its executable renderer lives in the versioned 1.1.0 runtime. The `evidence-led` variant is opt-in; no existing classic Reader is silently reformatted.

## Render a private evidence-led Reader

```sh
python3 ops/reader-edition.py \
  --pack /private/verified-source-pack \
  --analysis /private/reviewed-analysis.json \
  --out /private/new-reader-edition \
  --variant evidence-led
```

Omit `--variant` for the unchanged classic output. Every invocation verifies the closed pack, validates the analysis schema, writes an immutable edition, and records source/analysis/HTML SHA-256 values. Private rendering never publishes or sends email.

## Evidence-led presentation contract

- Preserve canonical source, evidence and original GhostMesh thesis layers.
- Show a top and bottom GhostMesh/Readers banner, canonical links, theme control, mobile navigation, provenance and original author attribution.
- Present local claim/assessment search. A single embedded handler is permitted under the page's explicit CSP; network and external scripts remain denied. The distinct public Reader search form may navigate to the canonical Reader archive, while SharePlane Works keeps its own search. No unverified unified index is claimed.
- Render claim-to-source corroboration links only from registered citations supplied in analysis. A link does not convert partial/unknown status into support.
- Render related SharePlane Works only when the analysis includes an approved canonical URL, title and pinned source commit. Do not derive Works from keyword similarity and do not invent missing relationships.
- Do not publish private media, full transcripts, private research packets, source captions or confidential credentials.
- Keep article layout variety opt-in; wrapper and evidence obligations remain invariant.

## Qualification source RP40

The first real-source candidate is David Ondrej `9tOu4r-FiQI`, tracked in `pinklon/reasonpack#40`.

- Source manifest SHA-256: `26ad4f21f40ded4ea80c6cf1040e4303144a11a4c660051ced5a52d66a77d663`.
- Evidence registry SHA-256: `3f468a510587875d3bde0f664099bb3635750c91c60c1e65eb77e228fa2e5a88`.
- Three segments reconciled, explicitly **unreviewed**.
- Analysis has 20 claims and verified seeking cues from local Whisper.
- Canonical evidence-led renderer was exercised on the verified pack, not merely a synthetic fixture.
- No approved SharePlane Work relationships are in this candidate. Rendering an empty list is correct, not a failure to invent them.

## Gate to release

Run the existing Reader tests, the evidence-led tests, full repository checks and a real-source render. Independently inspect desktop/mobile, light/dark and search interaction. Confirm link/anchor integrity, theme, CSP and no private-source leakage. Require editorial review, approved public Work relationships (if any), repository review, exact-head CI and separately authorized public deployment.

A private rendering receipt is not source-truth attestation, owner approval or production release.
