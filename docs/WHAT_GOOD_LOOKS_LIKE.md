# What Good Looks Like

This document is the quality bar, not a list of implementation tasks.

## 1. Good source handling

A good ReasonPack begins with a source whose identity is explicit.

Good means:

- source URL is recorded;
- source host is inside the admitted boundary;
- one invocation means one source;
- source metadata is preserved;
- acquisition failures remain visible;
- technical accessibility is never treated as redistribution permission.

Bad looks like:

- a mystery MP4 with no source record;
- browser-cookie scraping hidden in a convenience command;
- a playlist downloaded because the URL happened to point at one;
- a local filename being treated as provenance.

## 2. Good transcript handling

Good means the recipient can answer:

> “Where did this text come from?”

The answer should be either source captions or a recorded local speech-inference path.

Good does **not** mean pretending automatic captions are perfect. Transcript provenance and transcript accuracy are different qualities.

## 3. Good artifact integrity

A good pack has:

- non-empty required members;
- explicit byte counts;
- SHA-256 for every tracked member;
- independent checksum inventory;
- no unexplained regular files;
- a verifier that fails on drift.

The verifier is not a spell that makes content trustworthy. It is a precise answer to a precise question: “Are these the bytes we recorded?”

## 4. Good user experience

A capable user should not need the author standing beside them.

A good handoff makes these tasks obvious:

- install;
- check dependencies;
- self-test;
- inspect a source;
- build a pack;
- find the output;
- verify it later;
- understand common failures;
- remove or update the tool.

The happy path should be short. The explanation behind it should still exist for people who need to reason about the system.

## 5. Good failure behavior

A good tool says **no** when the evidence contract cannot be satisfied.

Examples:

- no transcript path → fail;
- invalid Whisper configuration → doctor fails;
- hash mismatch → verify fails;
- unexplained file → verify fails;
- unsupported URL → reject.

A failed job with a clear reason is more useful than a successful job with fabricated completeness.

## 6. Good architecture

Good architecture keeps these layers separate:

- source acquisition;
- normalization;
- transcript generation;
- evidence packaging;
- derived reasoning;
- downstream execution;
- storage/publication.

The first four form the current ReasonPack core. The others are integrations or future layers.

## 7. Good portability

The artifact should remain useful even when the original machine is gone.

That means:

- ordinary files;
- documented formats;
- hashes;
- no hidden database requirement;
- no dependency on one AI vendor;
- no requirement to call back to a ReasonPack service to read the pack.

## 8. Good security and rights posture

Good means:

- no secret/cookie import by default;
- no automatic upload;
- no telemetry merely because it is fashionable;
- local Whisper stays local;
- pack classification follows the sensitivity of its source;
- rights are a user/organizational decision, not inferred from download success.

## 9. Good product discipline

The package must distinguish:

- what exists now;
- what is planned next;
- what is explicitly not part of the product.

A roadmap bullet is not a shipped feature. A poster is not a contract. A demo is not production telemetry.

## 10. Good engineering handoff

The recipient should be able to answer all of the following without calling the author:

1. What problem does this solve?
2. Who is it for?
3. What exactly does it do today?
4. What does it deliberately not do?
5. What are its dependencies?
6. How do I install it on my OS?
7. What files does it create and why?
8. How do I prove a pack has not changed?
9. What are the important trust boundaries?
10. What failures are expected and how do I diagnose them?
11. How is success measured?
12. What decisions shaped the design?
13. How can it evolve without becoming a monolith?
14. Where does it fit with broader AI execution patterns?

If the package answers those questions, documentation has done useful work. If it merely repeats function names, it has not.
