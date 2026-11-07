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

## Private Reader

Render a validated analysis with the default Reader layout:

    reasonpack reader --pack PRIVATE_PACK --analysis VALIDATED_ANALYSIS.json --out PRIVATE_READER_DIR

When you have a complete editorial draft, pass it with
`--deconstruction-html DECONSTRUCTION.html`. The Reader embeds the full argument
and tables alongside the video, timed cues, and editorial relationships. The
validated analysis still supplies the opening brief and video navigation.

For a Markdown draft, omit its title heading (the Reader supplies it) and export
an HTML fragment with Pandoc:

    pandoc --from=gfm-raw_html --to=html5 --section-divs --id-prefix=full- BODY.md -o DECONSTRUCTION.html

Use HTTPS source links in the fragment. The renderer accepts article markup,
excludes active content, and records the fragment hash in the Reader receipt.

The standalone shell is pinned to GhostMesh Readers main c3fd13c70c0c6d1cf1f8a3b85faa9014ef69c880 and the latest published video Reader at that revision, A Model That Says Yes Is Not Necessarily a Model That Knows. The template includes the shared masthead, footer, appearance controls and an offline snapshot of public Reader titles and summaries. Playback is opt-in and the original YouTube links remain available. Update this pin from the current published video Reader when refreshing the shell. Rendering creates a private HTML draft.

Use repeatable `--continue-reading LABEL TITLE URL REASON` for proposed reading connections. The Reader places these under Continue the thinking and separates them from validated related Works and claim evidence.
