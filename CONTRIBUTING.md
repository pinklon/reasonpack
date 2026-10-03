# Contributing

Keep ReasonPack boring in the best possible way: explicit inputs, deterministic orchestration, inspectable outputs, and fail-closed verification.

Before opening a pull request:

```bash
bash -n bin/reasonpack
bin/reasonpack self-test
python3 tests/test_contract.py
```

Changes to canonical evidence filenames, manifest schema, verification closure, URL scope, or transcription authority are contract changes and belong in `CHANGELOG.md`.
