#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from verify_required_evidence import verify_required_evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    return parser.parse_args()


def baseline_audit(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {'status': 'NOT_RUN', 'reason': 'baseline directory not supplied'}
    root = root.resolve()
    try:
        log = (root / 'diagnostics/unit-e2e.log').read_text(encoding='utf-8')
        counts = [int(value) for value in re.findall(r'Ran (\d+) tests', log)]
        tests = max(counts, default=0)
        quality = json.loads((root / 'diagram-gallery/artifact-quality-report.json').read_text(encoding='utf-8'))
        roundtrip = json.loads((root / 'semantic-roundtrip/semantic-roundtrip-report.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError) as exc:
        return {'status': 'FAIL', 'error': str(exc)}
    passed = (
        tests == 49
        and '\nOK\n' in log
        and quality.get('status') == 'PASS'
        and quality.get('sampleCount') == 13
        and quality.get('drawioNativeCount') == 13
        and quality.get('drawioImageExactCount') == 13
        and quality.get('svgCount') == 13
        and roundtrip.get('status') == 'PASS'
        and len(roundtrip.get('fixtures', [])) == 4
        and all(item.get('accepted') is True for item in roundtrip.get('fixtures', []))
    )
    return {
        'status': 'PASS' if passed else 'FAIL',
        'tests': tests,
        'sampleCount': quality.get('sampleCount'),
        'roundtripFixtures': len(roundtrip.get('fixtures', [])),
    }


def candidate_audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    logs = [
        root / 'validation/test-local-preflight.log',
        root / 'validation/test-final.log',
        root / 'validation/test-user-object.log',
    ]
    log_path = next((path for path in logs if path.is_file()), None)
    if log_path is None:
        return {'status': 'FAIL', 'error': 'candidate test log missing'}
    test_log = log_path.read_text(encoding='utf-8')
    counts = [int(value) for value in re.findall(r'Ran (\d+) tests', test_log)]
    tests = max(counts, default=0)
    proof = json.loads((root / 'validation/proof-report.json').read_text(encoding='utf-8'))
    models = sorted((root / 'generated').glob('*/model.drawio'))
    user_object_models = 0
    for model in models:
        if list(ET.parse(model).getroot().iter('object')):
            user_object_models += 1
    source_text = '\n'.join(path.read_text(encoding='utf-8') for path in (root / 'src').rglob('*.py'))
    forbidden = bool(re.search(r'\bDVM\b|DiagramViewModel|\bRenderAst\b|\bRenderingIR\b', source_text))
    evidence_errors = verify_required_evidence(root)
    passed = (
        tests >= 28
        and '\nOK\n' in test_log
        and proof.get('status') == 'PASS'
        and proof.get('sampleCount') == 13
        and len(models) == 13
        and user_object_models == 13
        and not forbidden
        and not evidence_errors
    )
    return {
        'status': 'PASS' if passed else 'FAIL',
        'tests': tests,
        'proofStatus': proof.get('status'),
        'sampleCount': proof.get('sampleCount'),
        'modelCount': len(models),
        'userObjectModels': user_object_models,
        'forbiddenSource': forbidden,
        'requiredEvidenceErrors': evidence_errors,
        'edgePathPrecisionCounts': proof.get('edgePathPrecisionCounts'),
    }


def main() -> int:
    args = parse_args()
    candidate = candidate_audit(args.candidate)
    baseline = baseline_audit(args.baseline)
    local_pass = candidate['status'] == 'PASS' and baseline['status'] in {'PASS', 'NOT_RUN'}
    report = {
        'schema': 'DvmEliminationLocalPreflight.v3',
        'status': 'PASS' if local_pass else 'FAIL',
        'localPreflight': 'PASS' if local_pass else 'FAIL',
        'mechanismProof': candidate['status'],
        'currentBaselineAudit': baseline['status'],
        'mergeReadiness': 'NOT_PASSED',
        'decisionAcceptance': 'NOT_RUN',
        'independentReview': 'NOT_RUN',
        'exactCanonicalCutover': 'NOT_RUN',
        'candidate': candidate,
        'baseline': baseline,
        'remainingMergeGates': [
            'accepted architecture decision bound to exact head',
            'independent review bound to exact head',
            'revised exact-head GitHub Actions green',
            'clean squashed submission',
        ],
        'remainingCutoverGates': [
            'pinned diagrams.net editor open-edit-save persistence',
            'all 13 exact canonical event logs and output parity',
            'repo-wide DVM/RenderAst/RenderingIR deletion',
            'temporary proof runtime retirement',
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'localPreflight', 'mechanismProof', 'currentBaselineAudit', 'mergeReadiness', 'exactCanonicalCutover')}, sort_keys=True))
    return 0 if local_pass else 1


if __name__ == '__main__':
    raise SystemExit(main())
