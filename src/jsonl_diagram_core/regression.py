from __future__ import annotations
from typing import Any
JsonObj = dict[str, Any]
def compare_hash_manifest(expected: dict[str, str], actual: dict[str, str]) -> JsonObj:
    missing=sorted(set(expected)-set(actual)); added=sorted(set(actual)-set(expected)); changed=sorted(k for k in set(expected)&set(actual) if expected[k]!=actual[k])
    return {"schema":"GoldenRegressionResult.v1","ok":not(missing or added or changed),"missing":missing,"added":added,"changed":changed}
