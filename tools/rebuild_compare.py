from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def rel_files(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): sha256_file(p) for p in sorted(root.rglob('*')) if p.is_file()}


def verify_sample_proofs(root: Path) -> list[dict]:
    errors = []
    sys.path.insert(0, str(ROOT / 'src'))
    from jsonl_diagram_core.io import canonical_json, sha256_text
    for proof_path in sorted((root / 'samples').glob('*/proof.json')):
        sample_dir = proof_path.parent
        proof = json.loads(proof_path.read_text(encoding='utf-8'))
        events_text = (sample_dir / 'events.jsonl').read_text(encoding='utf-8')
        dvm = json.loads((sample_dir / 'dvm.json').read_text(encoding='utf-8'))
        svg = (sample_dir / 'diagram.svg').read_text(encoding='utf-8')
        checks = {
            'eventsSha256': sha256_text(events_text),
            'dvmSha256': sha256_text(canonical_json(dvm)),
            'svgSha256': sha256_text(svg),
        }
        for key, expected in checks.items():
            if proof.get(key) != expected:
                errors.append({'sample': sample_dir.name, 'field': key, 'expected': expected, 'actual': proof.get(key)})
        proof_without_self = dict(proof)
        actual_proof_hash = proof_without_self.pop('proofSha256', None)
        expected_proof_hash = sha256_text(canonical_json(proof_without_self))
        if actual_proof_hash != expected_proof_hash:
            errors.append({'sample': sample_dir.name, 'field': 'proofSha256', 'expected': expected_proof_hash, 'actual': actual_proof_hash})
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected', default='generated/expression-suite')
    parser.add_argument('--require-engines', action='store_true')
    parser.add_argument('--run-d2-elk-smoke', action='store_true')
    args = parser.parse_args(argv)
    expected = (ROOT / args.expected).resolve()
    if not expected.exists():
        print(json.dumps({'ok': False, 'error': f'expected dir missing: {expected}'}, indent=2), file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as td:
        actual = Path(td) / 'rebuilt'
        cmd = [sys.executable, str(ROOT / 'examples' / 'expression_suite' / 'build_suite.py'), '--out', str(actual)]
        if args.require_engines:
            cmd.append('--require-engines')
        subprocess.run(cmd, cwd=ROOT, check=True)
        if args.run_d2_elk_smoke:
            subprocess.run(['node', str(ROOT / 'examples' / 'expression_suite' / 'tools' / 'd2_elk_smoke.mjs'), str(actual)], cwd=ROOT, check=True)
        expected_files = rel_files(expected)
        actual_files = rel_files(actual)
        missing = sorted(set(expected_files) - set(actual_files))
        extra = sorted(set(actual_files) - set(expected_files))
        changed = sorted(k for k in set(expected_files) & set(actual_files) if expected_files[k] != actual_files[k])
        proof_errors = verify_sample_proofs(actual)
        report = {
            'schema': 'RebuildCompareReport.v1',
            'ok': not (missing or extra or changed or proof_errors),
            'expected': str(expected),
            'filesCompared': len(set(expected_files) | set(actual_files)),
            'missing': missing,
            'extra': extra,
            'changed': changed,
            'proofErrors': proof_errors,
            'requireEngines': bool(args.require_engines),
            'd2ElkSmoke': bool(args.run_d2_elk_smoke),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
