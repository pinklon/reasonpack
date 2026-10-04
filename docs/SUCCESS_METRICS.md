# Success Measures

## Measurement posture

These are **proposed product measures and quality gates**, not claims about historical production performance. The reference runtime contains no adoption telemetry, and this package will not invent metrics merely to make a dashboard look inhabited.

Where possible, measure from explicit local test/build receipts or team-reported usage until a justified telemetry design exists.

## 1. Reliability measures

### Pack verification integrity

**Metric:** percentage of accepted qualification fixtures that pass exact pack verification.

**Target:** 100% for maintained release fixtures.

A release with a fixture that cannot verify should not ship as qualified.

### Silent hash drift

**Metric:** number of cases where changed bytes are accepted without manifest/checksum update.

**Target:** 0.

### Silent transcript success

**Metric:** number of builds classified successful without a non-empty transcript and transcript-status evidence.

**Target:** 0.

### Untracked-file acceptance

**Metric:** number of unexplained regular files accepted by `verify`.

**Target:** 0.

### Self-test health

**Metric:** supported environments passing `reasonpack self-test` after installation.

**Target:** 100% of environments claimed as supported for a release.

## 2. Usability measures

### Time to first verified pack

Measure from a clean supported host where approved package repositories/network access are available.

Suggested target:

- dependency/bootstrap + doctor/self-test: under 10 minutes for a typical technical user;
- first source build time is tracked separately because it depends materially on source duration, network and CPU.

Do **not** use a single “under two minutes” marketing target for all videos. That would confuse source/runtime cost with UX quality.

### Author-assistance rate

**Metric:** percentage of first-time technical users who require direct author intervention to complete install + self-test + first build.

Desired direction: down over successive releases.

### Command-path simplicity

A routine user should normally need:

```text
install → doctor → self-test → yt URL
```

The existence of detailed docs should not lengthen the happy path.

## 3. Portability measures

### OS support qualification

Track separately:

- macOS installer qualification;
- Linux distribution/package-manager qualification;
- Windows/WSL bootstrap qualification;
- future native Windows qualification.

“Works on Windows” must not be used as shorthand when only WSL is qualified.

### Downstream readability

A completed pack should be usable as ordinary local files without ReasonPack running.

Measure by confirming that manifest, transcript, metadata and normalized media can be opened by standard tools on supported environments.

## 4. Evidence quality measures

### Provenance completeness

For a successful pack, require:

- source URL;
- source metadata;
- transcript-status path;
- tool version evidence where available;
- member byte count;
- member SHA-256;
- checksum inventory.

### Evidence truthfulness

Count instances where a system or user incorrectly claims more than evidence supports, such as labeling captions “verified transcript” or treating hash verification as content truth.

Target: 0 in maintained documentation and automated output.

## 5. Privacy and security measures

### Automatic external side effects

Target for current core:

- automatic upload: 0;
- automatic publication: 0;
- telemetry emission: 0;
- browser-cookie import: 0;
- automatic downstream AI execution: 0.

### Secret material in pack

The canonical pack should not need API keys or browser credentials. Any future credential-bearing workflow belongs outside the source-evidence artifact.

## 6. Adoption measures

Until a justified telemetry model exists, gather deliberately lightweight evidence:

- number of explicit installs known to the team;
- packs built for real work;
- repeat users;
- verification failures by category;
- downstream workflows that reused a pack instead of reacquiring the source;
- qualitative developer feedback;
- cases where a pack prevented source/context reconstruction.

The most meaningful early adoption signal is **repeat use without author involvement**.

## 7. Strategic measures

ReasonPack is strategically valuable if it reduces repeated source preparation.

Potential later measures:

- frequency of one pack reused across multiple AI surfaces;
- avoided duplicate transcription/acquisition events;
- percentage of derived artifacts that retain an exact source-pack reference;
- percentage of governed work packets that reuse existing context artifacts instead of re-ingesting sources.

These should only be instrumented when the measurement cost and privacy tradeoff are justified.

## 8. Release scorecard

A release candidate should answer:

| Area | Release question |
|---|---|
| Reliability | Do fixtures, self-test and verifier all pass? |
| Portability | Are every claimed OS/runtime paths actually qualified? |
| Evidence | Does transcript and member provenance remain explicit? |
| Security | Did any new credential/network side effect enter the core? |
| UX | Can a new user reach a verified pack without undocumented steps? |
| Docs | Do current behavior and roadmap remain clearly separated? |

A release is not “good” because the executable runs on the author’s laptop. It is good when the recipient can operate it with the documented contract intact.
