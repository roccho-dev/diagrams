#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src"
rm -rf src/*/__pycache__ tests/__pycache__ tools/__pycache__
mkdir -p validation
python -m compileall -q src tools tests
python -m unittest discover -s tests -v 2>&1 | tee validation/test-local-preflight.log
python tools/build_proof.py 2>&1 | tee validation/build-local-preflight.log
python tools/verify_required_evidence.py --root . 2>&1 | tee validation/evidence-verify-local-preflight.log
if [[ $# -gt 0 ]]; then
  python tools/audit_proposal_readiness.py \
    --candidate . \
    --baseline "$1" \
    --out validation/local-preflight.json
else
  python tools/audit_proposal_readiness.py \
    --candidate . \
    --out validation/local-preflight.json
fi
python tools/verify_required_evidence.py --root . 2>&1 | tee validation/evidence-verify-after-audit.log
python - <<'PY'
from pathlib import Path
import json, re
root = Path('.')
text = '\n'.join(p.read_text(encoding='utf-8') for p in (root / 'src').rglob('*.py'))
assert not re.search(r'\bDVM\b|DiagramViewModel|\bRenderAst\b|\bRenderingIR\b', text)
assert len(list((root / 'generated').glob('*/model.drawio'))) == 13
assert not list((root / 'generated').rglob('dvm.json'))
report = json.loads((root / 'validation/local-preflight.json').read_text())
assert report['localPreflight'] == 'PASS'
assert report['mergeReadiness'] == 'NOT_PASSED'
print('LOCAL_PREFLIGHT_PASS')
PY
