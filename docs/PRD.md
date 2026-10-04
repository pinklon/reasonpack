# Product Requirements Document — ReasonPack Reference Runtime

## 1. Product summary

ReasonPack is a local developer utility for turning one authorized YouTube source into a portable, provenance-preserving, integrity-verifiable context package suitable for later human review or AI-assisted reasoning.

The product is not trying to be the best media downloader. It is trying to make useful external information **easier to carry forward than to rediscover and re-explain**.

## 2. Problem statement

Video contains valuable technical, educational and strategic information, but ordinary video consumption has weak continuity for serious AI-assisted work:

- the useful content is trapped behind a player and timeline;
- teams repeatedly revisit or retranscribe the same source;
- source metadata and transcript provenance are easily separated from derived analysis;
- different AI tools have different upload/runtime constraints;
- local transformations are often performed ad hoc with no durable byte identity;
- a later recipient cannot tell which transcript/media version the original analysis used.

The result is repeated context reconstruction and weak evidence lineage.

## 3. Target users

### Primary

- software engineers and architects;
- development managers;
- researchers and technical analysts;
- trainers / enablement leads;
- AI-native knowledge workers who move work between multiple reasoning tools.

### Secondary

- teams creating internal learning artifacts;
- reviewers who need to verify source material used by someone else;
- automation owners that need a stable input artifact before downstream execution.

## 4. Jobs to be done

A user should be able to:

1. inspect one YouTube source before downloading it;
2. acquire the source without accidentally expanding into a playlist;
3. normalize media into broadly usable local formats;
4. obtain a transcript through an explicit evidence path;
5. understand whether the transcript came from source captions or local speech inference;
6. preserve source and technical metadata;
7. seal member sizes and SHA-256 identities;
8. give the package to another person or tool;
9. later verify that the package was not silently changed;
10. know when the tool could not produce a valid pack.

## 5. Product goals

### G1 — portable context

Produce ordinary files that can be inspected without a ReasonPack service or proprietary database.

### G2 — provenance before synthesis

Preserve source identity and transcript path before adding future derived summaries or interpretations.

### G3 — explicit failure

Prefer a failed/incomplete build over a falsely complete evidence package.

### G4 — recipient independence

A competent technical recipient should be able to install, operate and verify the product from the package itself.

### G5 — composability

Keep downstream AI execution, storage and publication optional so the core can plug into different environments.

## 6. Non-goals for the current version

ReasonPack v1 is not required to:

- support arbitrary video sites;
- authenticate to private YouTube accounts;
- download playlists;
- automatically summarize or interpret content;
- guarantee transcript factual accuracy;
- determine copyright/redistribution rights;
- provide cloud storage or team synchronization;
- route work to an AI model;
- provide native Windows execution outside WSL;
- guarantee bit-identical reacquisition from a changing remote source;
- provide production SLA/support commitments.

## 7. Functional requirements

### FR-001 — source URL admission

The runtime shall reject URLs outside the configured YouTube host allowlist before acquisition.

### FR-002 — single-source scope

Acquisition and caption operations shall use no-playlist behavior by default.

### FR-003 — inspect command

The runtime shall support metadata inspection without media download.

### FR-004 — media acquisition

The runtime shall download one source media representation and verify that a non-empty local source file exists before normalization continues.

### FR-005 — normalized video

A successful build shall contain non-empty `video.mp4` encoded as H.264 with broadly compatible pixel format and MP4 fast-start layout.

### FR-006 — normalized audio

A successful build shall contain non-empty `audio.m4a`.

### FR-007 — technical metadata

A successful build shall contain `ffprobe.json` created from the normalized video.

### FR-008 — captions-first transcript

The runtime shall attempt English subtitles/automatic captions before speech-to-text fallback.

### FR-009 — optional Whisper fallback

Local Whisper shall only run when the operator explicitly supplies a valid executable and model path.

### FR-010 — transcript failure honesty

A successful build shall not be emitted without a non-empty `transcript.txt`. Missing captions plus missing/invalid fallback shall remain an explicit failure.

### FR-011 — transcript provenance

A successful build shall include `transcript-status.json` identifying the transcript path.

### FR-012 — member manifest

A successful build shall include member path, byte count and SHA-256 for each tracked pack member.

### FR-013 — independent checksum file

A successful build shall include `SHA256SUMS.txt` covering manifest and tracked members.

### FR-014 — verification

The verifier shall reject missing required files, empty required files, incorrect sizes, incorrect hashes and unexplained regular files.

### FR-015 — diagnostics

`reasonpack doctor` shall expose missing required dependencies and invalid optional Whisper configuration.

### FR-016 — self-test

`reasonpack self-test` shall exercise positive verification and prove that unexplained files are rejected.

### FR-017 — convenience invocation

The reference distribution shall support `yt URL` / `reasonpack URL` quick flow without removing the explicit `build URL OUT_DIR` command.

### FR-018 — no hidden external side effects

The runtime shall not automatically upload, publish, invoke downstream AI, import browser cookies, or emit telemetry.

## 8. Non-functional requirements

### NFR-001 — inspectability

Pack members and documentation should remain usable with ordinary filesystem and text tools.

### NFR-002 — portability

Reference installation shall target macOS and common Linux distributions directly, with Windows supported through WSL in this release.

### NFR-003 — bounded dependency surface

Core runtime dependencies shall remain understandable and individually replaceable.

### NFR-004 — integrity

Verification failure shall be loud and actionable rather than automatically “repairing” expected hashes.

### NFR-005 — local-first privacy posture

Transformation, transcript fallback and verification should run locally. Network use is required for source acquisition only unless a later feature explicitly changes that contract.

### NFR-006 — documentation completeness

The distribution shall explain purpose, current capability, architecture, dependencies, installation, operations, troubleshooting, security/rights, roadmap and success measures.

## 9. Acceptance criteria for this reference kit

A supported technical user should be able to:

1. unpack the kit;
2. understand CURRENT vs future capability without reading the shell source;
3. run the correct OS installer;
4. open a new shell and pass `reasonpack doctor`;
5. pass `reasonpack self-test`;
6. verify the included synthetic example;
7. build one authorized public source when network/source availability permits;
8. verify the resulting pack later;
9. explain what each canonical member is for;
10. explain at least three things a SHA-256 verification does **not** prove.

## 10. Product risks

### Remote-source volatility

YouTube formats, metadata, captions and site behavior change. Mitigation: keep acquisition behind `yt-dlp`, record tool/version evidence, and preserve completed packs when exact evidence matters.

### Rights misuse

Technical access may be mistaken for redistribution permission. Mitigation: rights boundary is explicit throughout the package; no auto-publication exists.

### Transcript overconfidence

Automatic captions or Whisper inference may contain errors. Mitigation: preserve provenance and do not label transcript as verified truth.

### Dependency drift

`yt-dlp` and `ffmpeg` change rapidly. Mitigation: doctor/version capture, self-test, future compatibility matrix and release qualification.

### Scope creep

The product could become a media platform, knowledge graph, AI orchestration system and cloud registry all at once. Mitigation: keep derived context, storage and execution as adapters/layers with separate contracts.

## 11. Open product questions

- Should the canonical pack eventually have one top-level content identity in addition to member hashes?
- What is the minimum useful signed-manifest model for team handoff?
- Should source captions be preserved in original format(s) beyond one selected VTT?
- What derived-context schema is useful without contaminating the source-evidence layer?
- When is native Windows support worth the maintenance cost versus WSL?
- What enterprise proxy/certificate configuration can be supported without accepting browser credential import?

These are product decisions, not hidden assumptions in v1.
