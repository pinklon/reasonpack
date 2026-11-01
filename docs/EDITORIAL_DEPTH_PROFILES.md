# ReasonPack editorial depth profiles

A depth profile controls the **analysis request**, not source acquisition, evidence quality, publication permission or automated model execution. Profiles are defined in `ops/depth-profile.py` and are bound into the immutable workflow and generated prompt.

| Profile | Use when | What it requires |
| --- | --- | --- |
| `short` | A narrow source or single mechanism | Core claim, decisive evidence, objection, consequence and useful source locations |
| `standard` (default) | A normal multi-claim source | Mechanism mapping, evidence roles, tradeoffs, GhostMesh application, descriptive jump labels |
| `deep` | Dense tooling, architecture or consequential workflow | End-to-end setup, tools, integrations, trust boundaries, claim audit, alternatives and a falsifiable pilot |
| `exhaustive` | A reference-grade or high-consequence treatment | Materially complete implementation inventory, cue and evidence maps, contradictions, risk/cost/performance tests and adoption decisions |

Selection is **editorial judgment**. Duration alone is not sufficient. Escalate when substantial implementation detail or consequential claims deserve it. Do not impose artificial word counts, citation quotas or metadata-byte caps based on the profile. Existing safety and source-integrity bounds remain independent.

For a newly admitted Reader workflow:

```sh
python3 ops/reader-pipeline.py init --depth deep \
  --admission ADMISSION.json --root PRIVATE_JOBS \
  --envelope SIGNED_ENVELOPE.json --allow-sender APPROVED_SENDER
```

The selected `depth_profile` is pinned in `workflow.json`. Reusing the same job ID with a different depth fails. `compose` carries it to the generated model prompt and `composition-receipt.json`; `analysis` rejects a mismatched composition. For manual composition without the workflow, use `python3 ops/research-composer.py prepare --depth deep ...`.

Older jobs lacking a profile use `standard`, preserving backwards compatibility. No profile lets a model attest source truth, invoke tools or publish. Every profile requires meaningful, unique, source-specific timestamp/section labels; do not repeat broad headings for multiple jump points.

For David Ondrej's 85-minute coding-workflow investigation (`F8rc-ULd4_4`), `deep` is the minimum appropriate choice; `exhaustive` is optional if the goal is a reproducible reference dossier. This is an editorial recommendation, not proof that an earlier job was initialized with this runtime field.

Because the production Reader workflow currently lives in the unmerged PR #27, these changes are staged as a stacked PR and are **not operationally active** until that base implementation and this change are accepted, merged and deployed to the worker that launches jobs.
