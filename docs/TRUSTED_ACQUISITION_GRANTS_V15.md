# ReasonPack trusted acquisition launch grants v0.15

**SOURCE ONLY. NOT INSTALLED. NO SIGNER PRIVATE KEY OR SIGNING SERVICE CREATED.**
This change addresses a real authorization failure mode: the prior
`acquisition-cgroup-runner.py` verified that `admission.json` had the expected
schema, that source URL/video ID were well formed, and that locally stored
supervision hashes agreed. It did **not** independently prove that a trusted
Gmail actor issued that admission. An actor with write access to a job directory
could create self-consistent JSON and cause a real downloader to run.

## New boundary

Every real acquisition attempt now requires an external, separately signed
`launch-grant.json` and detached OpenSSH signature `launch-grant.sig`.
The runner checks this **under the existing job lock and before** changing
attempt state or launching the fixed backend. Signature verification uses
the system OpenSSH verifier, with:

- fixed namespace `ghostmesh.reasonpack.acquisition.v1` and principal
  `ghostmesh-reasonpack-admission`;
- a root-owned **public key only** registry at
  `/etc/ghostmesh/reasonpack/approved_signers`, requiring exact root-owned,
  nonsymlink, nongroup-writable ancestors and one explicitly designated
  `ssh-ed25519` public key;
- strictly canonical JSON bytes, with exactly one source job ID, exact
  video URL/video ID, SHA-256 of the admission byte stream, SHA-256 of the
  validated signed-Gmail-gateway envelope, source-only scope, 64-hex nonce,
  exact installed immutable release commit and issued/expiry timestamps;
- finite *launch authorization* validity of up to 24 hours. **There is no
  maximum video duration or total acquisition runtime limit.**
- no private signer key passed to the model, downloader, untrusted request,
  ReasonPack worker, or installed release.

Changing the job ID, source video, Gmail-envelope identity, exact admission
bytes, installed release, signature, signing key, date, or signer principal
rejects the launch. Unrecognized fields and noncanonical serialization are
also denied.

## How a grant may eventually be issued

An independently protected Gmail-admission signer, **owned by the existing
Collab Gmail authentication/journal writer**, must first verify the current
provider-assigned Gmail message/thread identity, existing normalized HMAC
envelope, sender allowlist, one already-journaled admission and the exact
immutable release that will execute the job. Only then may it sign the
canonical grant bytes using a private key that the `ghostmesh` worker can
**never read**. The source candidate does **not** create that signer,
private key, key distribution mechanism, or authority, and contains no live
mail connector. Do not generate a key in the service-user-owned workspace.

The privileged owner separately installs only its public key into
`/etc/ghostmesh/reasonpack/approved_signers`, with protected ancestors.
The current installed `bf2f560...` release has not changed and continues to
refuse structurally invalid requests; this proposed source version additionally
refuses even a perfectly formatted job without an authenticated signature.

A signature is evidence of **which key approved what bytes**, not proof of
the signer's correctness. Full replay/fresh-spend prevention will also need
an owner-protected issuance/consumption ledger outside the worker-writable
job root. The existing worker `attempts=0` and lock prevent ordinary
re-entry but are not an owner-grade anti-replay ledger. This remains a
separate mandatory commissioning gate.

## Qualification and limitations

`tests/test-acquisition-signed-grant.py` uses disposable synthetic Ed25519
test keys in private temporary directories to validate actual OpenSSH
signatures. It exercises valid/invalid signatures, other signers, changed
source media, changed job ID, changed immutable release, altered gateway
receipt, expired grant, malformed scope, unexpected fields, noncanonical bytes
and uncommissioned production public signer state.

No real Gmail messages, signing keys, video downloads, provider requests,
model calls, privileged installs, systemd unit changes, or public releases
are performed by these tests. A passing synthetic signature test never
implies a real trusted Gmail signer exists or that it was authorized.

## Future gated order

1. Exact-head source CI and independent security review.
2. Trusted Gmail admission/signer key custody and issue-specific authority
   through the existing writer, with independent signed-gateway receipt.
3. Root-protected public key registry and durable external grant issuance/
   consumption ledger, verified one-time use and revocation semantics.
4. Review new immutable source release, staged/installed rollback and exact
   cgroup service containment witness.
5. Owner-only real video ReasonPack and all-segment research, followed by
   one witnessed response from the existing Gmail sender.

No repeated global wall-clock limit for multi-hour videos, second Gmail
poller, credential export, public publishing, or customer billing is authorized.

## Race-free worker handoff

Independent review of the first source commit found a P1 time-of-check/time-of-use
hole: after signature verification, the worker reread the original
worker-writable admission from disk. An attacker could replace the video
between those two reads. The parent now places the exact verified admission
bytes in a kernel anonymous \`memfd\`, applies irreversible
\`F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL\`, and transfers
that descriptor to the child via \`pass_fds\`. The child checks its seals,
size, authenticated job identifier, then uses only that snapshot for choosing
the video/source URL. The disk record is *never* reread as source authority.
Neither the parent nor child can mutate the sealed byte stream.

A read-only reviewer also identified a fixed October 15 timestamp in
a signature test that would break future hosted CI. The fixture now uses
UTC at test execution and preserves explicit offset-aware expiry controls.

\`tests/test-acquisition-sealed-admission.py\` verifies live Linux memfd
seals, cross-subprocess read-only transfer, forged on-disk video replacement,
unsealed/pipe rejection and exact parent-child source binding. This does not
authorize any real acquisition until an independent Gmail signer is trusted.

## Running-state JSON correction

Second independent read-only review found a P1 escaped-newline mistake in
the supervised running-state write. It appended a literal backslash-n after
the JSON, so the worker would reject the state's extra trailing bytes before
acquisition. The source now emits an actual newline in both durable state
writes. An AST-level regression verifies no stray literal backslash-n
constants are present and that the status receipt remains valid JSON.
