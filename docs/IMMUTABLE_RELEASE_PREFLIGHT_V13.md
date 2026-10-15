# ReasonPack exact-release owner preflight v0.13

State: SOURCE-ONLY. No root actions, no installer invocation, no live systemd change, no model run, no provider call and no Gmail/Slack message.

## What changed

The acquisition real worker previously referenced a globally installed mutable CLI path. That was inconsistent with an immutable systemd instance release, because a unit could be rolled back while its CLI continued from a separate, newer location.

`ops/acquisition-real-worker.py` now binds the binary to `REPO/bin/reasonpack`, where REPO is resolved from the real worker's own code path. The SHA-256 is still pinned to the reviewed streamed CLI. The runner and worker must load from the **same immutable source release** and may not independently switch a CLI outside that tree.

The new `ops/release-preflight.py` prepares an owner-inspectable proposal. It:
- Requires a completely clean Git worktree and an explicitly supplied exact 40-hex HEAD, refusing aliases like `main` or `HEAD` and refusing any changed or untracked files.
- Confirms that worker's CLI path is within the same release and its embedded CLI SHA matches the local binary.
- Validates the source-only systemd template with its fixed instance controls and checks the unmanaged `launch-real` path is absent.
- Renders the exact unit referencing a future immutable path `/opt/ghostmesh/reasonpack/releases/<commit40>`. It never resolves to a mutable `current` symlink.
- Emits `ghostmesh-reasonpack-acquire@.service` and `preflight-receipt.json` into a private, atomic output directory, bound to the exact commit and SHA-256 of the unit, CLI, worker and runner.
- Leaves `installer_executed=false`, `systemd_unit_installed=false`, `worker_started=false`, `network_requested=false`, `owner_authorization_bound_to_hash=false`, `cgroup_kill_witness=NOT_ATTESTED` and `rollback_witness=NOT_ATTESTED`.

## Example after hosted exact-head qualification

```bash
python3 ops/release-preflight.py \
  --exact-commit "$(git rev-parse HEAD)" \
  --out /protected/reasonpack-candidates/owner-install-review-001
```

This is **not** an installer. The proposal does not stage a release on systemd, create privileged directories or start a source download. It requires a separately qualified owner-controlled administrative operator with exact hash approval.

## Remaining commissioning gates

1. Independently review this branch and pass hosted CI. The current VPS local `main` has ten unpushed GhostMesh-authored native worker/acquisition-broker commits. Do not overwrite or relocate that ownership.
2. Verify the release snapshot is immutable and not owned/writable by the service user. A `ghostmesh`-writable release directory is not a trusted immutable authority even with a committed source hash.
3. The privileged installer needs to verify the candidate and its signed owner approval, provision a protected per-job directory, render the unit and perform a root-owned `systemctl daemon-reload` only after source and rollback preparation. This capability **is not included** in this PR.
4. Test the **actual** cgroup effect using an authorized synthetic subprocess that creates an independent session. Verify that `systemctl stop`/SIGKILL removes every child and that no auto-retry or orphan remains. Source-only tests cannot establish this.
5. Only after that, consider an isolated real-video acquisition, verified source package, provider/resource receipts and no duplicate job run. Keep installed legacy intake and global two-hour timeout untouched until separate reviewed switchover.
6. The model executor, independent semantic review, Gmail exactly-once writer, cost telemetry (#86), delivery witness (#117), private Reader and customer payment flow still require separate commissioning.

A public ReasonPack Reader or actual customer payment is not authorized by any part of this preflight.

## Verification

`python3 tests/test-release-preflight.py` exercises exact-commit path generation, source pinning, immutable render contents, nonproduction proposal receipts, dirty/mismatched source denial and rejection of mutable/external CLI references.

Rollback of the source-only proposal is simply discarding this feature branch or its noninstalled review package. An actual installed release demands independently tested host rollback.

## Independent review correction

The first read-only review found that importing source policy modules could create Python bytecode files inside the source worktree, invalidating its clean-checkout requirement. The preflight now disables bytecode writes before any source imports. A separate subprocess test runs the source imports without PYTHONDONTWRITEBYTECODE and verifies that no new repository bytecode files appear. Review package generation remains repeatable against the same unchanged source commit.

## Root-controlled release path correction

A live host path inspection found that /srv/ghostmesh/workspaces/runtime is
owned and writable by the ghostmesh service account. A root-owned nested
release directory under that parent would remain replaceable by that account,
so it cannot be treated as immutable. This source branch instead anchors the
future owner-installed release in **/opt/ghostmesh/reasonpack/releases**,
beneath a root-controlled /opt. The preflight rejects existing symlinked,
non-root-owned or group/world-writable ancestor directories. It accepts
absent descendant directories only because it does not create or install them.
The privileged owner installer must create each as root-owned and reverify
all components before publishing any unit.
