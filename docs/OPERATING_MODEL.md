# Operating Model

## Lifecycle

A ReasonPack has a simple lifecycle:

```text
candidate source
    ↓ inspect
admitted one-source request
    ↓ build
local pack candidate
    ↓ verify
verified ReasonPack
    ↓ optional copy/reuse
verified ReasonPack elsewhere
    ↓ optional derived work
separate analysis / Execution Packet / publication
```

## Roles

This reference package assumes lightweight roles rather than a formal service organization.

### User / source owner

Responsible for:

- choosing the source;
- confirming use is authorized;
- deciding source sensitivity;
- selecting output/storage location;
- deciding which downstream systems may consume the pack.

### Tool / runtime

Responsible for:

- enforcing source gate;
- performing documented transformations;
- recording evidence;
- failing when pack requirements cannot be satisfied;
- never silently expanding authority.

### Product maintainer

Responsible for:

- dependency compatibility;
- release tests;
- documentation correctness;
- current/roadmap distinction;
- security/rights posture;
- deciding when source/runtime scope expands.

## Normal operating procedure

### Before build

```bash
reasonpack doctor
```

For a new/unfamiliar source:

```bash
reasonpack inspect "URL"
```

### Build

```bash
yt "URL"
```

or explicit output:

```bash
reasonpack build "URL" OUT_DIR
```

### Acceptance

A build is accepted only when the final verifier succeeds.

The existence of `video.mp4` alone is not completion.

### Handoff

Before copying/sharing:

```bash
reasonpack verify PACK_DIR
```

After copying, verify again where practical.

### Derived work

Keep interpretation outside the canonical pack. Preserve a reference to pack/member hashes when derived work becomes important.

## Failure triage order

1. Does `reasonpack self-test` pass?
2. Does `reasonpack doctor` show all required dependencies?
3. Does `reasonpack inspect URL` succeed?
4. Did acquisition produce source media?
5. Which transcript path was attempted?
6. Does final verification identify drift or extra files?

This ordering prevents network/source failures from being confused with local package-verifier regressions.

## Update model

No auto-updater exists today.

Treat executable updates like a small tool release:

1. inspect change log;
2. install new candidate;
3. run doctor;
4. run self-test;
5. verify existing fixture/known pack;
6. build a qualification source if needed.

Existing ReasonPacks are data artifacts and should not be rewritten merely because the runtime updates.

## Support/escalation payload

A useful support request contains:

- OS/runtime;
- ReasonPack version;
- `reasonpack doctor` output;
- command class (`inspect`, `build`, `verify`);
- sanitized error output;
- whether self-test passes;
- source URL only if sharing it is appropriate;
- no credentials/cookies.

## Service posture

This reference kit is local developer tooling. It does not currently define:

- uptime SLA;
- central service owner/on-call;
- remote state recovery;
- centralized telemetry.

If adoption grows, those are product-operating-model decisions rather than assumptions to bury in the script.
