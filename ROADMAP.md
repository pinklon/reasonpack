# Roadmap

ReasonPack should stay small. Features earn their way in only when they strengthen acquisition, evidence quality, portability, or verification.

## Near term

- Linux/macOS integration tests with synthetic media fixtures.
- Structured `--json` status output for automation.
- Configurable media profiles: compact, standard, visual-detail.
- Deterministic archive packaging (`.zip` / `.tar.zst`) with package-level digest.
- Better timestamp preservation for local Whisper output.
- Optional thumbnail and chapter metadata preservation.
- `reasonpack diff` for manifest/evidence comparison.

## Agent workflows

- Stable machine-readable receipts for agent orchestration.
- Explicit pack-size budgets for model/file-upload surfaces.
- Bounded keyframe extraction without making generated summaries authoritative.
- MCP/skill wrappers that invoke the CLI rather than duplicating it.

## Non-goals

- DRM or access-control bypass.
- Browser-cookie harvesting.
- Hidden credential use.
- Automatic redistribution or publishing.
- Turning transcripts or model summaries into source truth.
