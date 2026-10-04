# Requirements Traceability

This matrix connects the PRD to the current reference implementation and evidence. It is intentionally honest about where a requirement is enforced by executable tests versus code inspection or documentation policy.

## Evidence classes

- **Automated:** exercised by the included self-test/package test or verifier fixture.
- **Runtime enforced:** explicit code path exists; not every external/network behavior is covered by the synthetic offline fixture.
- **Documentation/operating contract:** a required product practice that is not yet mechanically enforced by the current runtime.
- **Roadmap:** not current.

| PRD requirement | Current mechanism | Evidence class | Notes |
|---|---|---|---|
| FR-001 source URL admission | `validate_url()` host allowlist | Automated + runtime enforced | self-test accepts YouTube and rejects example.com |
| FR-002 single-source scope | all yt-dlp calls include `--no-playlist` | Runtime enforced | should gain explicit static regression test in release CI |
| FR-003 inspect command | `inspect()` uses `--dump-single-json --skip-download` | Runtime enforced | requires network/source for full qualification |
| FR-004 media acquisition | `build()` downloads `source.%(ext)s` and requires non-empty source | Runtime enforced | external-source behavior depends on yt-dlp/YouTube |
| FR-005 normalized video | ffmpeg H.264/AAC/yuv420p/+faststart command | Runtime enforced | future integration test should inspect real normalized fixture |
| FR-006 normalized audio | ffmpeg audio extraction to AAC M4A | Runtime enforced | non-empty member required by verifier |
| FR-007 technical metadata | ffprobe JSON output | Runtime enforced | non-empty member required by verifier |
| FR-008 captions-first transcript | caption acquisition precedes fallback | Runtime enforced | source-dependent external path |
| FR-009 explicit Whisper fallback | requires `WHISPER_CLI` + `WHISPER_MODEL` | Runtime enforced | `doctor` validates configured paths |
| FR-010 transcript failure honesty | successful build requires non-empty `transcript.txt` | Runtime enforced | build returns failure when transcript cannot be established |
| FR-011 transcript provenance | `transcript-status.json` required | Runtime enforced + verifier | status content varies by path |
| FR-012 member manifest | Python manifest writer in `build()` | Runtime enforced | member hashes/sizes verified later |
| FR-013 checksum inventory | `SHA256SUMS.txt` generated after manifest | Runtime enforced | verifier re-hashes every listed member |
| FR-014 verification | `verify()` | Automated | sample fixture + self-test, including unexplained-file rejection |
| FR-015 dependency diagnostics | `doctor()` | Runtime enforced | full matrix depends on host environment |
| FR-016 self-test | `self_test()` | Automated | included package test invokes it |
| FR-017 convenience invocation | URL dispatch to `quick()`; `yt`/`rp` wrappers | Runtime enforced | output naming depends on source metadata |
| FR-018 no hidden external side effects | no upload/publish/AI/cookie code in runtime | Runtime inspection + operating contract | future static policy test recommended |
| NFR-001 inspectability | ordinary files + JSON/text/hash records | Design/runtime property | no proprietary reader required |
| NFR-002 portability | macOS/Linux/WSL installers | Package qualification | native Windows is not current |
| NFR-003 bounded dependencies | Bash/Python/yt-dlp/ffmpeg/ffprobe/SHA | Design/runtime property | optional Whisper isolated |
| NFR-004 integrity | fail-closed verifier | Automated | negative extra-file case included |
| NFR-005 local-first privacy | no upload/AI core; local transform/verify | Runtime inspection + policy | source acquisition necessarily uses network |
| NFR-006 documentation completeness | reference documentation set | Package-level test | package test checks required documents are present |

## Current evidence gaps worth improving

The reference kit is stronger than a lone script, but it is not pretending to have exhaustive integration coverage.

Useful R1 additions:

1. static test that every yt-dlp acquisition path retains `--no-playlist`;
2. real authorized network fixture for `inspect` and `build` in a controlled qualification environment;
3. ffprobe assertions against the normalized real fixture;
4. explicit captions-path and Whisper-path integration fixtures where redistribution permits;
5. installer idempotency tests per supported OS image;
6. static side-effect scan proving no upload/cookie/provider invocation enters the core;
7. machine-readable doctor receipt for support automation.

## Traceability rule for future changes

When a PR changes a PRD requirement:

- update the requirement text if semantics changed;
- update implementation;
- add or update test evidence;
- update this matrix;
- update CURRENT/NEXT posture if product capability changed.

Do not leave a requirement marked “current” when the enforcing code or evidence has been removed.
