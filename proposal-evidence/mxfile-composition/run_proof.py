#!/usr/bin/env python3
"""Generate deterministic executable proof artifacts for mxfile composition."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Iterable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import composer  # noqa: E402
from invalid_cases import BY_NAME, INVALID_CASES  # noqa: E402

VALID = HERE / "fixtures" / "valid"
MINIMUM_NEGATIVE_CASES = 15


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def parse_xml(data: bytes) -> ET.Element:
    parser = ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
    )
    return ET.fromstring(data, parser=parser)


def valid_paths(count: int) -> list[Path]:
    return [VALID / f"page-{index:02d}.drawio" for index in range(1, count + 1)]


def expect_error(
    name: str,
    expected_code: str,
    action: Callable[[], object],
) -> dict[str, object]:
    try:
        action()
    except composer.CompositionError as exc:
        if exc.code != expected_code:
            raise AssertionError(
                f"{name}: expected {expected_code}, received {exc.code}"
            ) from exc
        return {
            "evidence": {"error_code": exc.code},
            "name": name,
            "status": "PASS",
        }
    raise AssertionError(f"{name}: expected CompositionError")


def serialize_tree(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def mutate_and_expect_rejection(
    output: bytes,
    pages: tuple[composer.ValidatedPage, ...],
    mutation: Callable[[ET.Element], None],
) -> str:
    root = parse_xml(output)
    mutation(root)
    changed = serialize_tree(root)
    try:
        composer.verify_composition(changed, pages)
    except composer.CompositionError as exc:
        return exc.code
    raise AssertionError("mutated output was accepted")


def static_dependency_check() -> dict[str, object]:
    local_modules = {"composer", "check_changed_paths", "invalid_cases"}
    allowed_special = {"__future__"}
    import_roots: dict[str, list[str]] = {}
    unexpected: dict[str, list[str]] = {}

    for path in sorted(HERE.rglob("*.py")):
        relative = path.relative_to(HERE).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
        import_roots[relative] = sorted(roots)
        invalid = sorted(
            root
            for root in roots
            if root not in sys.stdlib_module_names
            and root not in local_modules
            and root not in allowed_special
        )
        if invalid:
            unexpected[relative] = invalid

    if unexpected:
        raise AssertionError(f"non-stdlib imports: {unexpected}")

    composer_source = (HERE / "composer.py").read_text(encoding="utf-8")
    forbidden_tokens = (
        "events.jsonl",
        "DocumentIR",
        "PageIR",
        "postMessage",
        "dvm-elimination",
        "mxgraph_core",
    )
    found = sorted(token for token in forbidden_tokens if token in composer_source)
    if found:
        raise AssertionError(f"forbidden coupling tokens: {found}")

    return {
        "forbidden_coupling_tokens_found": found,
        "import_roots_by_file": import_roots,
        "non_stdlib_imports": unexpected,
        "status": "PASS",
    }


def positive_cases(output_dir: Path) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for count in (1, 2, 5):
        pages = composer.load_pages(valid_paths(count))
        output, receipt = composer.compose_pages(pages)
        path = output_dir / f"composed-{count}.drawio"
        composer.atomic_write(path, output)
        readback = composer.verify_composition(path.read_bytes(), pages)
        if readback.to_dict() != receipt.to_dict():
            raise AssertionError(f"{count}-page receipt changed after readback")
        results.append(
            {
                "name": f"compose_{count}_page",
                "output_file": path.name,
                "receipt": receipt.to_dict(),
                "status": "PASS",
            }
        )
    return results


def negative_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []

    cases.append(
        expect_error(
            "empty_input_list",
            "empty_input",
            lambda: composer.load_pages([]),
        )
    )
    for name, code, data in INVALID_CASES:
        cases.append(
            expect_error(
                name,
                code,
                lambda data=data, name=name: composer.parse_single_page(data, name),
            )
        )

    page_one = VALID / "page-01.drawio"
    cases.append(
        expect_error(
            "duplicate_page_id",
            "duplicate_page_id",
            lambda: composer.load_pages([page_one, page_one]),
        )
    )

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "existing.drawio"
        invalid = Path(directory) / "malformed.drawio"
        invalid.write_bytes(BY_NAME["malformed_xml"][1])
        sentinel = b"sentinel-output\n"
        output.write_bytes(sentinel)
        result = expect_error(
            "invalid_input_no_partial_output",
            "invalid_xml",
            lambda: composer.compose_files([page_one, invalid], output),
        )
        if output.read_bytes() != sentinel:
            raise AssertionError("invalid input replaced existing output")
        if list(Path(directory).glob(".*.tmp")):
            raise AssertionError("invalid input left a temporary file")
        result["evidence"] = {
            **result["evidence"],  # type: ignore[arg-type]
            "existing_output_preserved": True,
            "temporary_files": 0,
        }
        cases.append(result)

    pages = composer.load_pages(valid_paths(2))
    old_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    try:
        os.environ["SOURCE_DATE_EPOCH"] = "0"
        first, _ = composer.compose_pages(pages)
        os.environ["SOURCE_DATE_EPOCH"] = "9999999999"
        second, _ = composer.compose_pages(pages)
    finally:
        if old_epoch is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = old_epoch
    if first != second:
        raise AssertionError("output depends on SOURCE_DATE_EPOCH")
    root = parse_xml(first)
    forbidden_time_attributes = {
        "agent",
        "created",
        "date",
        "modified",
        "time",
        "timestamp",
    }
    present = sorted(forbidden_time_attributes.intersection(root.attrib))
    if present:
        raise AssertionError(f"wall-clock attributes present: {present}")
    cases.append(
        {
            "evidence": {
                "forbidden_time_attributes_present": present,
                "source_date_epoch_independent": True,
            },
            "name": "timestamp_independence",
            "status": "PASS",
        }
    )

    page1 = composer.load_pages(valid_paths(1))
    page1_output, _ = composer.compose_pages(page1)
    page3 = composer.load_pages([VALID / "page-03.drawio"])
    page3_output, _ = composer.compose_pages(page3)

    mutation_codes = {
        "cell_id": mutate_and_expect_rejection(
            page1_output,
            page1,
            lambda root: root.find(".//mxCell[@id='region:company']").set(  # type: ignore[union-attr]
                "id", "region:mutated"
            ),
        ),
        "cell_attribute": mutate_and_expect_rejection(
            page3_output,
            page3,
            lambda root: root.find(".//object[@id='object:agent']").set(  # type: ignore[union-attr]
                "owner", "CPO"
            ),
        ),
        "geometry": mutate_and_expect_rejection(
            page1_output,
            page1,
            lambda root: root.find(
                ".//mxCell[@id='region:company']/mxGeometry"
            ).set("x", "41"),  # type: ignore[union-attr]
        ),
        "user_object": mutate_and_expect_rejection(
            page3_output,
            page3,
            lambda root: root.find(".//object[@id='object:agent']").set(  # type: ignore[union-attr]
                "revision", "r8"
            ),
        ),
    }
    cases.append(
        {
            "evidence": {"rejection_codes": mutation_codes},
            "name": "model_mutations_rejected",
            "status": "PASS",
        }
    )

    ordered_pages = composer.load_pages(valid_paths(2))
    ordered_output, _ = composer.compose_pages(ordered_pages)
    changed_root = parse_xml(ordered_output)
    first_diagram, second_diagram = list(changed_root)
    changed_root.remove(first_diagram)
    changed_root.remove(second_diagram)
    changed_root.append(second_diagram)
    changed_root.append(first_diagram)
    changed_output = serialize_tree(changed_root)
    cases.append(
        expect_error(
            "changed_page_order_rejected",
            "page_order_or_id_mismatch",
            lambda: composer.verify_composition(changed_output, ordered_pages),
        )
    )

    if len(cases) < MINIMUM_NEGATIVE_CASES:
        raise AssertionError(
            f"expected at least {MINIMUM_NEGATIVE_CASES} negative cases, found {len(cases)}"
        )
    return cases


def build_summary(
    positives: list[dict[str, object]],
    negatives: list[dict[str, object]],
) -> dict[str, object]:
    all_positive = all(case["status"] == "PASS" for case in positives)
    all_negative = all(case["status"] == "PASS" for case in negatives)
    if not all_positive or not all_negative:
        raise AssertionError("proof case failure")

    page_receipts = [
        page
        for case in positives
        for page in case["receipt"]["pages"]  # type: ignore[index]
    ]
    preservation = all(
        page["diagram_digest"] and page["model_digest"]  # type: ignore[index]
        for page in page_receipts
    )
    if not preservation:
        raise AssertionError("missing structural digest")

    dependency = static_dependency_check()
    gates = [
        {"gate": "G1", "name": "valid_composition_1_2_5", "status": "PASS"},
        {"gate": "G2", "name": "input_order_preserved", "status": "PASS"},
        {"gate": "G3", "name": "page_identity_preserved", "status": "PASS"},
        {"gate": "G4", "name": "model_structural_digests_equal", "status": "PASS"},
        {"gate": "G5", "name": "deterministic_bytes", "status": "PASS"},
        {"gate": "G6", "name": "single_page_semantic_identity", "status": "PASS"},
        {"gate": "G7", "name": "duplicate_ids_rejected", "status": "PASS"},
        {"gate": "G8", "name": "invalid_inputs_fail_closed", "status": "PASS"},
        {"gate": "G9", "name": "no_event_or_jsonl_authority", "status": "PASS"},
        {"gate": "G10", "name": "no_persisted_document_ir", "status": "PASS"},
        {"gate": "G11", "name": "pr7_import_isolation", "status": "PASS_LOCAL"},
        {"gate": "G12", "name": "stdlib_dependency_floor", "status": "PASS"},
        {
            "gate": "G13",
            "name": "existing_repository_checks",
            "status": "REQUIRES_REPOSITORY_CI",
        },
        {
            "gate": "G14",
            "name": "delete_and_rebuild_byte_identity",
            "status": "VERIFIED_BY_RUN_ALL",
        },
    ]

    return {
        "claim_ceiling": (
            "Isolated proof only: ordered native single-page mxfiles compose into "
            "one deterministic multi-page mxfile without another authority or "
            "persisted document IR. Canonical integration is not claimed."
        ),
        "dependency_check": dependency,
        "external_gate": "G13 existing repository checks must run on the actual PR head and integration tree.",
        "gates": gates,
        "kind": "mxfile.composition.proof.v1",
        "negative_case_count": len(negatives),
        "negative_cases": negatives,
        "positive_case_count": len(positives),
        "positive_cases": positives,
        "preproof_status": "PASS",
    }


def write_manifest(output_dir: Path, names: Iterable[str]) -> None:
    lines: list[str] = []
    for name in sorted(names):
        data = (output_dir / name).read_bytes()
        lines.append(f"{digest(data)}  {name}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(output_dir: Path) -> dict[str, object]:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise ValueError(f"output directory is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True)

    positives = positive_cases(output_dir)
    negatives = negative_cases()
    summary = build_summary(positives, negatives)
    summary_path = output_dir / "proof-summary.json"
    summary_path.write_bytes(json_bytes(summary))
    artifact_names = [
        *(case["output_file"] for case in positives),
        summary_path.name,
    ]
    write_manifest(output_dir, artifact_names)  # type: ignore[arg-type]
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run(args.output_dir)
    except (AssertionError, composer.CompositionError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"preproof_status": summary["preproof_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
