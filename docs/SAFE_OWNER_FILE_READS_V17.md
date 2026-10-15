# ReasonPack privileged owner file-read hardening v17

SOURCE ONLY, NOT INSTALLED. Current host PR #17 unit stays disabled. No root ledger, trusted Gmail signer, keys, video execution, email or billing is authorized by this change.

## Independent finding
A targeted read-only adversarial review of the already-installed PR #17 root ExecStartPre handler found a previously missed privileged-read boundary. The helper called pathname-based reader functions on files inside a worker-writable job directory. An adversary could symlink those files to root-only paths or replace them with unbounded huge files, FIFOs and other devices, causing root-level reads or denial of service. Signed authorization itself remained fail-closed, but unsafe root input handling blocked commissioning.

## Corrected root-only read contract

The new acquisition-safe-owner-io module traverses every directory component starting from the root using pinned directory file descriptors with O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC. It opens the fixed SHA-256 job subdirectory by name relative to the pinned root tree, then reads only four explicitly allowed members via the pinned job directory descriptor: admission.json (40,000 bytes maximum), supervision.json (65,536), launch-grant.json (8,192), and launch-grant.sig (4,096).

Each file open uses O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC with fstat of the open descriptor before any data read, a bounded read and a post-read length confirmation. Symlinks, FIFOs, devices, directories, oversized files, truncated files, unapproved names, and any symlinked ancestor path are denied. Even if the worker renames the entire job folder, the helper reads only from the original pinned directory.

The privileged pre-start now constructs registered-state checks from the bounded bytes and calls signed.verify_from_bytes on those exact snapshots. It no longer invokes pathname-based guard.state(job) or signed.verify_for_job(job) as root. The existing Ed25519 digest/signature authorization, owner-only SQLite single-use claim, systemd MainPID check and sealed worker admission all remain in place.

## Tests and activation hold

New test-acquisition-safe-owner-io.py covers ordinary pinned reads, symlinked sensitive source, oversize payload, nonblocking FIFO, directory member, symlinked parent/job, rename replacement race, fixed-name allowlist and root source API contract. Add to hosted CI, run the full inherited suite, and repeat independent review.

Do not enable or start the existing PR #17 unit after creating any owner ledger until the safe-reader source has a separately approved root-owned immutable release and new reviewed systemd template installed. The negative missing-ledger witness from the prior PR #17 release remains valid, but it is not permission to use that vulnerable code for a successful grant.
