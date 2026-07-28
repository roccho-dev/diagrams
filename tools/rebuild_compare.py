from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def files(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): sha256_file(path) for path in sorted(root.rglob('*')) if path.is_file()}


def verify_proofs(root: Path) -> list[dict]:
    errors=[]
    sys.path.insert(0, str(ROOT / 'src'))
    from jsonl_diagram_core.io import canonical_json, sha256_text
    for proof_path in sorted((root / 'samples').glob('*/proof.json')):
        sample=proof_path.parent
        proof=json.loads(proof_path.read_text())
        expected={
            'eventsSha256': sha256_text((sample/'events.jsonl').read_text()),
            'modelSha256': sha256_text((sample/'model.drawio').read_text()),
            'svgSha256': sha256_text((sample/'diagram.svg').read_text()),
        }
        for key,value in expected.items():
            if proof.get(key)!=value: errors.append({'sample':sample.name,'field':key,'expected':value,'actual':proof.get(key)})
        content=dict(proof); actual=content.pop('proofSha256',None); expected_hash=sha256_text(canonical_json(content))
        if actual!=expected_hash: errors.append({'sample':sample.name,'field':'proofSha256','expected':expected_hash,'actual':actual})
    return errors


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--expected',default='generated/expression-suite')
    parser.add_argument('--require-engines',action='store_true')
    parser.add_argument('--run-d2-elk-smoke',action='store_true')
    args=parser.parse_args(argv)
    expected=(ROOT/args.expected).resolve()
    if not expected.exists():
        print(json.dumps({'ok':False,'error':f'expected dir missing: {expected}'}),file=sys.stderr); return 2
    with tempfile.TemporaryDirectory() as td:
        actual=Path(td)/'rebuilt'
        command=[sys.executable,str(ROOT/'examples/expression_suite/build_suite.py'),'--out',str(actual)]
        if args.require_engines: command.append('--require-engines')
        subprocess.run(command,cwd=ROOT,check=True)
        if args.run_d2_elk_smoke:
            subprocess.run(['node',str(ROOT/'examples/expression_suite/tools/d2_elk_smoke.mjs'),str(actual)],cwd=ROOT,check=True)
        left,right=files(expected),files(actual)
        missing=sorted(set(left)-set(right)); extra=sorted(set(right)-set(left)); changed=sorted(k for k in set(left)&set(right) if left[k]!=right[k])
        proof_errors=verify_proofs(actual)
        report={'schema':'RebuildCompareReport.v2','ok':not(missing or extra or changed or proof_errors),'filesCompared':len(set(left)|set(right)),'missing':missing,'extra':extra,'changed':changed,'proofErrors':proof_errors,'soleGeneratedCurrentState':'mxGraphModel'}
        print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if report['ok'] else 1


if __name__=='__main__': raise SystemExit(main())
