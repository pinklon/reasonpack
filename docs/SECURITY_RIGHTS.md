# Security, Rights, Privacy and Data Handling

## Security posture in one sentence

ReasonPack is a **local source-acquisition and evidence-packaging utility**, not an authentication bypass, rights engine, cloud service, or secret-bearing agent.

## 1. Source rights

Use ReasonPack only for material you own or are authorized or legally permitted to download and analyze.

A successful `yt-dlp` request proves technical accessibility. It does not prove:

- redistribution rights;
- public-domain status;
- training/reuse permission;
- employer authorization;
- compliance with a platform’s terms for a particular use.

Those decisions remain with the user/organization.

## 2. Private/authenticated content

The current reference runtime does not import:

- browser cookies;
- saved sessions;
- account credentials;
- OAuth tokens;
- API keys.

Do not bolt those onto the command line as a convenience shortcut and still describe the security posture as unchanged.

Private-source support would require a separate threat model, credential lifecycle and data-classification design.

## 3. Network behavior

Network access is expected for:

- source inspection;
- media acquisition;
- caption acquisition.

Normal transform/verify/self-test work is local after dependencies/source material are present.

The core performs no automatic pack upload, analytics callback or downstream AI invocation.

## 4. Local data sensitivity

A pack may contain:

- full video/audio;
- full transcript;
- source metadata;
- technical metadata.

Therefore the pack should inherit at least the sensitivity/classification of the source material.

Do not place a sensitive pack into a consumer-sync folder merely because `REASONPACK_ROOT` supports arbitrary local paths.

## 5. Transcript privacy

Local Whisper fallback keeps inference local in this design. That is useful for privacy, but it does not automatically make the workflow compliant with every enterprise data-handling policy.

Validate:

- local model approval;
- endpoint storage policy;
- source classification;
- retention requirements.

## 6. Integrity versus authenticity

SHA-256 verifies byte identity against the pack’s own recorded values.

The current package is not cryptographically signed by an organizational identity. Therefore:

- hashes detect accidental/unauthorized byte change relative to the recorded manifest;
- they do not independently prove who originally created the pack.

Signed release/attestation support is a roadmap item.

## 7. Integrity versus truth

A transcript can be byte-perfect and wrong.

A source video can be byte-perfect and misleading.

A manifest can be internally consistent and still describe material the user had no right to redistribute.

Keep these trust questions separate:

```text
byte integrity ≠ authenticity ≠ semantic truth ≠ rights authority
```

## 8. Temporary media handling

The build downloads a temporary source media carrier, creates normalized members, then removes the temporary carrier after successful processing.

If the build terminates unexpectedly, inspect the output directory before sharing it. An incomplete run may leave working material that is not part of a valid closed pack.

`reasonpack verify` is the final authority for whether the directory satisfies the current package contract.

## 9. Pack sharing

Before sharing a pack:

1. verify it;
2. confirm source sharing/redistribution authority;
3. inspect `source.json` for metadata you may not intend to distribute;
4. consider whether full video/audio are necessary for the recipient;
5. use an approved transfer/storage mechanism.

ReasonPack does not automatically sanitize source metadata for external publication.

## 10. Enterprise rollout checklist

Validate:

- YouTube access policy;
- acceptable-use and copyright policy;
- endpoint storage and retention;
- proxy/TLS requirements;
- approved software sources;
- WSL policy;
- optional Whisper model approval;
- support ownership;
- update mechanism;
- data-loss-prevention treatment of generated packs.

## 11. Secure extension rule

Any future capability that introduces credentials, cloud writes, automatic sharing, private-source access or model execution should be treated as a **new authority boundary**, not a cosmetic feature addition.
