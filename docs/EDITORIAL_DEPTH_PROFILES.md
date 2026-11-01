# ReasonPack editorial depth profiles

A depth profile controls the **analysis request**, not source acquisition, evidence quality, publication permission or automated model execution. Profiles are defined in `ops/depth-profile.py`. In this isolated source-only candidate, manual composition binds the selected profile into the generated prompt and receipt. Immutable job-state binding remains in the separate, unmerged Reader pipeline and is not claimed here.

| Profile | Use when | What it requires |
| --- | --- | --- |
| `short` | A narrow source or single mechanism | Core claim, decisive evidence, objection, consequence and useful source locations |
| `standard` (default) | A normal multi-claim source | Mechanism mapping, evidence roles, tradeoffs, GhostMesh application, descriptive jump labels |
| `deep` | Dense tooling, architecture or consequential workflow | End-to-end setup, tools, integrations, trust boundaries, claim audit, alternatives and a falsifiable pilot |
| `exhaustive` | A reference-grade or high-consequence treatment | Materially complete implementation inventory, cue and evidence maps, contradictions, risk/cost/performance tests and adoption decisions |

Selection is **editorial judgment**. Duration alone is not sufficient. Escalate when substantial implementation detail or consequential claims deserve it. Do not impose artificial word counts, citation quotas or metadata-byte caps based on the profile. Existing safety and source-integrity bounds remain independent.

For manual source-only composition, use `python3 ops/research-composer.py prepare --depth deep ...` with an already verified research input and evidence register. The selected profile is embedded in the generated model prompt and `composition-receipt.json`. `validate` checks the returned analysis against the pinned composition. No local job-admission or retry authority is provided by this command.

The original stacked Reader workflow (`ops/reader-pipeline.py` in PR #31) additionally pins `depth_profile` in `workflow.json` and rejects reusing a job ID with a changed depth. That workflow is deliberately not copied into this source-only candidate because its initialization is coupled to the privileged signed-email gateway.

Older jobs lacking a profile use `standard`, preserving backwards compatibility. No profile lets a model attest source truth, invoke tools or publish. Every profile requires meaningful, unique, source-specific timestamp/section labels; do not repeat broad headings for multiple jump points.

For David Ondrej's 85-minute coding-workflow investigation (`F8rc-ULd4_4`), `deep` is the minimum appropriate choice; `exhaustive` is optional if the goal is a reproducible reference dossier. This is an editorial recommendation, not proof that an earlier job was initialized with this runtime field.

This isolated candidate is not a worker installation or a complete admission pipeline. Do not claim mesh-wide commissioning, immutable retry enforcement, model execution or publication from its tests. Close those separately under [Control Tower #1135](https://github.com/pinklon/shareplane-control-tower/issues/1135), using an independent clean-room replay after authorized integration.
