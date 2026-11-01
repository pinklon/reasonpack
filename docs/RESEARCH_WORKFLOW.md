# ReasonPack research workflow

This is the local owner-facing entry point for preparing one verified source for GhostMesh deconstruction. It joins the existing source verifier, four editorial-depth profiles, long-form segmentation, evidence registry, and research composition without creating a second reasoning implementation.

## One command when evidence already exists

```sh
python3 ops/research-flow.py prepare \
  --pack "/private/path/verified-pack" \
  --out "/private/path/research-job-001" \
  --depth deep \
  --registry "/private/path/research-evidence.json"
```

The evidence registry must already be bound to the exact source manifest and transcript hashes. The command holds when those identities disagree.

## Two-phase flow when corroboration is not yet gathered

```sh
python3 ops/research-flow.py prepare \
  --pack "/private/path/verified-pack" \
  --out "/private/path/research-job-001" \
  --depth exhaustive
```

This verifies the source, admits the selected depth write-once, creates segment custody only when the transcript exceeds the inline threshold, and emits an editorial packet. It returns `awaiting-public-evidence-registry`. Separately collect legitimate primary/public corroboration into a registry bound to that packet. Then:

```sh
python3 ops/research-flow.py compose \
  --job "/private/path/research-job-001" \
  --registry "/private/path/research-evidence.json"
```

This produces `composition/model-prompt.json`, `composition/analysis-schema.json`, receipts and segment inputs when applicable. It never runs a model or publishes.

## Editorial depth

| Profile | Typical use |
| --- | --- |
| short | One clear mechanism with narrow stakes |
| standard | Ordinary multi-claim deconstruction |
| deep | Detailed tools, workflow architecture, alternatives and pilot |
| exhaustive | Reference-grade implementation inventory, evidence and counterarguments |

Long videos are not automatically exhaustive; depth is an editorial decision. A long transcript is segmented by bytes without a total-duration ceiling. Segment limits protect the model context window, not the amount of source material acquired.

## Boundaries

- Source pack stays immutable; the research job is outside the pack.
- Reusing an existing output path fails visibly. `compose` resumes a prepared job.
- Source capture, public evidence collection, model reasoning, independent review and publication are distinct stages.
- Generated claims must still be validated with the existing composer and the selected Reader/publishing contracts. A complete file set does not establish factual truth.
- No credential access, background worker, network research, model invocation, release, or dispatch is granted here.
- The workflow remains CLI-based. A visual guided interface and automatic model execution are not claimed as current.
