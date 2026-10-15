# ReasonPack systemd-cgroup containment contract v0.12

Status: **source-only template and guarded foreground runner, not installed, not commissioned**. No cgroup was created, no systemd unit was enabled or started, and no new YouTube network acquisition occurred.

## Why a service cgroup is necessary

A ReasonPack acquisition can invoke yt-dlp, FFmpeg, codecs and helpers. A worker that spawns an independent process session does not reliably contain the subprocess tree: killing the parent can leave active network and disk writes behind, and retrying then duplicates acquisition.

The host uses unified cgroup v2. The GhostMesh user is not delegated writable cgroup control. Source code therefore must NOT pretend that ordinary process-group signals confer containment.

## Source behavior

The source includes:

- `ops/systemd/ghostmesh-reasonpack-acquire@.service`: **unrendered, owner-installed template**. Its immutable release placeholder is intentionally unresolved and cannot safely be activated as delivered. The owner installer must substitute an exact reviewed, pinned immutable release path and atomically install the unit through the authorized infrastructure lane.
- `ops/acquisition-cgroup-runner.py`: checks Linux `/proc/self/cgroup` for the **exact** job-hash systemd instance before accepting any work. A copied script executed directly under SSH, cron, a shell or a different service refuses acquisition. The job identifier is exactly 64 lowercase hexadecimal characters. It never accepts a caller-supplied backend command.
- The runner validates a pre-existing registered job and its source SHA, durably claims one worker attempt under a file lock before launching the hardcoded `acquisition-real-worker.py`, records its PID/start ticks and only then releases the child's gate. It then **waits in the foreground** throughout acquisition. This allows systemd to own the lifetime of its full cgroup. Completion still requires independent package re-verification; no worker exit code or progress heartbeat is success by itself.
- The direct asynchronous `acquisition-supervisor.py launch-real` CLI has been removed. This closes the unmanaged runner path introduced in prior source-only PR #11. Synthetic fixture launch remains available for offline development.
- Unit policy: `Type=exec`, non-root `User=ghostmesh`, `KillMode=control-group`, `SendSIGKILL=yes`, memory/task/CPU ceilings, namespace/hardening restrictions, no restart, **no arbitrary video-duration limit**, private temp/home protection, and write permission only to `/srv/ghostmesh/workspaces/runs/reasonpack-jobs/%i`. All instance/job roots must already be provisioned through the owner-approved release mechanism.

## Essential release gates

1. **Owner/installer**: review and sign the exact source commit, substitute the immutable release path in the template and run `systemd-analyze verify` on the rendered service. The provided placeholder must never be installed as a working unit. The installation/root/job preparation must be performed by the existing owner-controlled privileged infrastructure lane; the GhostMesh service account cannot make arbitrary systemd changes.
2. **Protected job receipt**: a service that can write its own job files cannot independently prove a prior external Gmail authentication merely by hashing those files. The owner must preserve signed admission custody across the privileged launcher boundary, with write protections against source-role forgery and readback anchored to the trusted gateway.
3. **Cgroup witness test**: use a synthetic backend that deliberately creates a new process group. Confirm it is still in the same service cgroup; stop the service and verify every child exited and no orphan remains. Confirm process count, memory and CPU ceilings and that a failed unit cannot self-restart. A test run under `systemd-run --scope` outside an exact approved job unit is **not** sufficient.
4. **Source and rollback**: before a real provider call, pin the streamed CLI runtime `1.0-refkit.2`, verify the exact source/manifest sha, test immutable release rollback and distinguish verified package output from independent public origin or semantic truth. The existing local-main acquisition broker and its ten unpushed commits remain owned by their current orchestrator. Do not overwrite them.
5. **Commissioning**: connect the now-contained worker through the single incumbent GhostMesh mail/mission lane. Do not create a second Gmail/Slack poller or an unbounded owner spend path. Model execution, source corroboration, witnessed send, private Reader hosting and telemetry contracts remain separate gates.

## Verification

`python3 tests/test-acquisition-cgroup-contract.py` checks unit policy, exact cgroup matching, invalid IDs, prohibited non-cgroup execution, non-root restrictions, per-job writable scope, no global duration cutoff, hard resource controls and absence of Gmail/Slack service creation.

The earlier ReasonPack supervisor tests must still pass with direct real launch disabled. This suite is a **source contract**, not actual cgroup/kill behavior evidence.

No Production services, deployments, installed binaries, credentials, databases, emails, payments or public sites are changed by this PR.

Rollback for this source-only stage: remove/close the feature branch. A future installed service requires a separate tested release rollback, unit cleanup and journal reconciliation.

## Worker defense in depth

The real worker CLI now independently checks its own exact \`/proc/self/cgroup\` service identity and canonical dedicated job-root path **before** it reads the launch gate or makes any provider call. This closes a direct executable bypass of the guarded foreground launcher. The old unmanaged \`launch-real\` subcommand is removed from the source supervisor.

The unit's writable path is **instance-specific** (\`reasonpack-jobs/%i\`) rather than the whole job collection. \`ExecStart\` and \`WorkingDirectory\` contain a mandatory \`@IMMUTABLE_RELEASE_DIR@\` source placeholder. A reviewed, owner-only installer must resolve that to an exact immutable release directory before activation; it cannot follow the mutable \`current\` pointer.
