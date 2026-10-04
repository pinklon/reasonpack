#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash -n \
  "$ROOT/bin/reasonpack" \
  "$ROOT/install/install-macos.sh" \
  "$ROOT/install/install-linux.sh" \
  "$ROOT/install/install-wsl.sh"

"$ROOT/bin/reasonpack" self-test
"$ROOT/bin/reasonpack" verify "$ROOT/examples/sample-reasonpack"

python3 - "$ROOT" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
required_docs={
 'ARCHITECTURE.md','DEPENDENCIES.md','DESIGN_AND_HANDOFF_PHILOSOPHY.md',
 'EXECUTION_PACKET_BRIDGE.md','INSTALLATION.md','PRD.md','PRODUCT_FEATURE_SET.md',
 'ROADMAP.md','SECURITY_RIGHTS.md','SUCCESS_METRICS.md','TROUBLESHOOTING.md',
 'USER_GUIDE.md','VISION_STRATEGY.md','WHAT_GOOD_LOOKS_LIKE.md',
 'PACKAGE_CONTRACT.md','OPERATING_MODEL.md','DECISIONS_AND_TRADEOFFS.md',
 'SUPPORT_MATRIX.md','DEVELOPER_GUIDE.md','DOCUMENTATION_MAP.md',
 'REQUIREMENTS_TRACEABILITY.md','FEATURE_CURRENT_NEXT_NOT_YET.md'
}
actual={p.name for p in (root/'docs').glob('*.md')}
missing=required_docs-actual
assert not missing, f'missing reference docs: {sorted(missing)}'
manifest=json.loads((root/'MANIFEST.json').read_text())
assert manifest['schemaVersion']=='reasonpack-reference-kit.v1'
assert manifest['version'].startswith('1.1')
print(f"PASS documentation contract ({len(required_docs)} required docs)")
PY

python3 - "$ROOT" <<'PY'
import hashlib, pathlib, sys
root=pathlib.Path(sys.argv[1])
for line in (root/'SHA256SUMS.txt').read_text().splitlines():
    expected, rel=line.split('  ',1)
    p=root/rel
    assert p.is_file(), f'missing package member: {rel}'
    actual=hashlib.sha256(p.read_bytes()).hexdigest()
    assert actual==expected, f'package checksum drift: {rel}'
print('PASS reference-kit checksum inventory')
PY

echo "PASS reference kit tests"
