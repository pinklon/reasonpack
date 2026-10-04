# Developer Guide

## Read this before changing the core

The most important thing to preserve is not Bash syntax. It is the boundary between **source evidence**, **derived reasoning**, and **downstream execution**.

## Code map

```text
bin/reasonpack
    current reference runtime / command router

bin/yt
bin/rp
    thin convenience launchers

install/
    operator-owned dependency/bootstrap paths

examples/sample-reasonpack/
    synthetic verifier fixture

tests/test-package.sh
    package syntax/self-test/example qualification

docs/
    product/architecture/operating semantics
```

## Core commands

The implementation routes:

- `doctor`
- `inspect`
- `build`
- `verify`
- `self-test`
- URL as quick build

Keep command failure explicit. Do not catch errors merely to return zero with a friendly message.

## Development invariants

### Invariant 1 — source boundary stays explicit

Do not expand the allowlist without product/security/rights review and tests.

### Invariant 2 — successful pack requires transcript evidence

Do not make `transcript.txt` optional merely to improve completion rates.

### Invariant 3 — verification fails closed

Do not auto-regenerate checksums when verification detects changed bytes.

### Invariant 4 — canonical pack stays source-evidence oriented

New AI-generated summaries/topics belong in a derived layer unless the package schema is explicitly versioned and the semantic contract changes.

### Invariant 5 — credentials stay outside

Do not add browser-cookie/private-account convenience to the existing core without a new authority design.

### Invariant 6 — no downstream provider requirement

The pack should remain useful without Codex/Claude/Copilot/SharePlane.

## Test before change

Baseline:

```bash
bash -n bin/reasonpack install/*.sh
./bin/reasonpack self-test
./bin/reasonpack verify examples/sample-reasonpack
./tests/test-package.sh
```

For changes to acquisition/normalization/transcription, add a real authorized qualification source in an appropriate test environment. Do not put copyrighted test media into the reference package merely for convenience.

## Adding a new source provider

Do not simply loosen `validate_url`.

A source adapter should define:

- admitted host(s);
- metadata contract;
- single-source vs batch semantics;
- media acquisition behavior;
- caption/subtitle behavior;
- credential posture;
- rights/terms considerations;
- failure cases;
- qualification tests.

Then decide whether the schema should still be named `ghostmesh-reasoning-pack-v1` or needs a source-neutral successor.

## Adding derived summaries/topics

Recommended architecture:

```text
verified ReasonPack
      ↓ exact input hashes
Derived Context Artifact
      ├── summary.md
      ├── topics.json
      ├── citations.json
      └── derivation-receipt.json
```

Do not inject the derived files into the existing verified pack and then silently update checksums. That destroys the source/interpretation boundary.

## Adding storage

A storage adapter should:

1. verify locally before upload;
2. copy exact bytes;
3. record storage locator separately from pack identity;
4. verify remote size/hash by full readback when the storage API permits;
5. never infer sharing rights;
6. avoid making a provider URL the semantic artifact identity.

## Adding Execution Packet support

See `EXECUTION_PACKET_BRIDGE.md`.

The adapter should consume a verified ReasonPack as input evidence and add job semantics outside it.

## Release checklist

- update feature posture if behavior changed;
- update package contract if members/schema changed;
- update architecture/tradeoff docs for meaningful decisions;
- run local tests;
- qualify claimed OS paths;
- rebuild `MANIFEST.json` and `SHA256SUMS.txt`;
- confirm poster/marketing copy does not claim roadmap features as current;
- verify the complete distribution archive after creation.

## Code style philosophy

The current runtime is deliberately small and dependency-light. Prefer:

- explicit shell/Python standard-library logic;
- readable failure boundaries;
- adapter calls to mature tools;
- few hidden state surfaces;
- no background daemon;
- no silent dependency installation at runtime.

If the shell implementation becomes difficult to test safely, that is a signal to consider a more structured implementation language rather than adding increasingly clever Bash.
