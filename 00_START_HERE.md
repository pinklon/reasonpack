# ReasonPack Professional Reference Kit v1.1

ReasonPack turns one authorized YouTube source into a **durable, locally verifiable context package** that can be carried between people and AI tools without depending on a particular chat session, model, provider, or cloud service.

This reference kit has two jobs:

1. **Give you a useful tool you can install and run.**
2. **Demonstrate what a serious engineering handoff should contain.**

It is intentionally more complete than a typical “here is a script and a README” utility. The point is not documentation volume. The point is recipient independence: another engineer should be able to understand the product intent, install it, operate it, verify what it produced, diagnose common failures, challenge the design, and extend it without reconstructing the author’s intent from chat history.

## Five-minute path

If you only have five minutes:

1. Open `index.html` for the product tour.
2. Read `docs/PRODUCT_FEATURE_SET.md` to separate **CURRENT**, **NEXT**, and **NOT YET** capabilities.
3. Read `docs/ARCHITECTURE.md` for the system model.
4. Install using the script for your operating system under `install/`.
5. Run:

```bash
reasonpack doctor
reasonpack self-test
yt "https://www.youtube.com/watch?v=VIDEO_ID"
```

6. Verify any resulting package later with:

```bash
reasonpack verify "/path/to/Reasoning Pack"
```

## If you are evaluating the product

Read these in order:

- `docs/PRODUCT_FEATURE_SET.md` — what ships now and what does not.
- `docs/PRD.md` — problem, users, requirements, acceptance and risks.
- `docs/WHAT_GOOD_LOOKS_LIKE.md` — quality bar for product, pack and handoff.
- `docs/SUCCESS_METRICS.md` — how we would know adoption and reliability are real.
- `docs/VISION_STRATEGY.md` — why this is more interesting than a downloader.

## If you are installing or supporting it

- `docs/INSTALLATION.md`
- `docs/SUPPORT_MATRIX.md`
- `docs/DEPENDENCIES.md`
- `docs/USER_GUIDE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/OPERATING_MODEL.md`

## If you are reviewing or extending the design

- `docs/ARCHITECTURE.md`
- `docs/PACKAGE_CONTRACT.md`
- `docs/DECISIONS_AND_TRADEOFFS.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/SECURITY_RIGHTS.md`
- `docs/EXECUTION_PACKET_BRIDGE.md`
- `docs/ROADMAP.md`

## Important semantic boundary

A ReasonPack is a **context artifact**, not a claim that the source is true, lawful to redistribute, or semantically correct. Hashes prove byte identity. They do not prove factual accuracy. Transcript provenance records how text was obtained; it does not magically make automatic captions perfect.

The current runtime does **not** generate summaries, topic maps, embeddings, knowledge graphs, or automatic downstream AI work. Those are roadmap capabilities and are labeled as such.

## Distribution posture

This kit is a **reference distribution derived from active ReasonPack 1.0.0 behavior**. It adds cross-platform bootstrap scripts, documentation, diagrams, examples, aliases, and package-level integrity. It is not represented as a new canonical upstream release.

The generated product poster under `presentation/` is a vision illustration. The live product contract in `docs/PRODUCT_FEATURE_SET.md` is authoritative when the two differ.
