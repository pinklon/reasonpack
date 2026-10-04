# Roadmap

The roadmap is organized around **earned complexity**. A feature enters only when it solves a demonstrated user or governance problem without collapsing ReasonPack into a monolith.

## R0 — current reference capability

Status: implemented in this kit.

- single YouTube URL admission;
- metadata/source acquisition;
- normalized MP4 + audio;
- captions-first transcript;
- optional local Whisper fallback;
- transcript provenance status;
- ffprobe technical metadata;
- member byte/hash manifest;
- independent checksum file;
- closed-pack verification;
- doctor / inspect / build / verify / self-test;
- convenience `yt URL` flow;
- macOS/Linux/Windows-WSL bootstrap;
- no telemetry, automatic upload, private credential import, or AI execution.

## R1 — release engineering and operational maturity

Goal: make distribution safer for a small team before adding shiny derived features.

Candidate work:

- automated CI fixture suite across claimed OS/runtime variants;
- explicit semantic versioning and compatibility policy;
- updater/uninstaller lifecycle;
- richer machine-readable doctor/diagnostic receipt;
- dependency compatibility matrix;
- signed release artifacts/checksums;
- enterprise proxy/custom CA guidance;
- clearer partial-build cleanup/recovery behavior;
- installer idempotency tests.

Exit condition: another team can install/update/remove the utility using maintained release artifacts without author intervention.

## R2 — derived context layer

Goal: make packs faster to reason over without contaminating source evidence.

Candidates:

- source-grounded summary;
- topics/concepts;
- chapter/timestamp index;
- keyframe selection;
- named-entity extraction;
- compact agent-context representation.

Hard requirement: derived outputs must record the exact ReasonPack/member identities they used and must not silently enter the canonical source pack.

Exit condition: derived artifacts can be regenerated/reviewed independently while the source-evidence layer remains unchanged.

## R3 — team portability and signed identity

Candidates:

- signed release manifest;
- exact copy/readback helper for approved storage systems;
- pack registry/search adapter;
- retention/version conventions;
- team-readable provenance summaries.

Hard requirement: storage location must not become semantic artifact identity.

## R4 — Execution Packet adapter

Goal: turn a verified context artifact into optional governed work without coupling ReasonPack to one executor.

Candidates:

- select exact pack/member inputs;
- generate a packet skeleton;
- collect objective/authority/acceptance/stop semantics;
- execute through compatible adapters;
- normalize execution receipts.

Hard requirement: credentials remain external and ReasonPack source bytes remain unchanged.

## R5 — native Windows, if earned

Native Windows support should be added only when real adoption justifies maintaining a second runtime path.

Options should be evaluated rather than assumed:

- native Python implementation;
- PowerShell wrapper around native tools;
- packaged runtime;
- continued WSL as sufficient enterprise path.

## Explicitly deferred temptations

Do not build these merely because they look adjacent on an architecture diagram:

- bespoke cloud sync;
- proprietary model API gateway;
- knowledge graph built into ReasonPack;
- custom browser login/cookie capture;
- background monitoring daemon;
- social/publication layer.

Each may be a valid separate product. None is required to prove ReasonPack’s core value.
