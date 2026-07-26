#!/usr/bin/env python3
"""Deterministically compose ordered single-page draw.io mxfiles.

The composer treats each input ``mxGraphModel`` as opaque. It validates every
input before serializing or writing output, then creates only the outer
``mxfile`` document and ordered ``diagram`` sequence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


class CompositionError(ValueError):
    """Fail-closed input or output contract violation."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ValidatedPage:
    source: str
    page_id: str
    name: str
    diagram: ET.Element
    diagram_digest: str
    model_digest: str


@dataclass(frozen=True)
class PageReceipt:
    page_id: str
    name: str
    diagram_digest: str
    model_digest: str


@dataclass(frozen=True)
class CompositionReceipt:
    kind: str
    page_count: int
    page_order: tuple[str, ...]
    pages: tuple[PageReceipt, ...]
    output_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "output_sha256": self.output_sha256,
            "page_count": self.page_count,
            "page_order": list(self.page_order),
            "pages": [
                {
                    "diagram_digest": page.diagram_digest,
                    "model_digest": page.model_digest,
                    "name": page.name,
                    "page_id": page.page_id,
                }
                for page in self.pages
            ],
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _meaningful_text(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value


def _structural_value(element: ET.Element) -> dict[str, object]:
    """Return a deterministic semantic XML representation.

    Attribute order and indentation-only text are not semantic XML content.
    Child order, element names, meaningful text, and all attributes are kept.
    """

    if element.tag is ET.Comment:
        tag = "#comment"
    elif element.tag is ET.ProcessingInstruction:
        tag = "#processing-instruction"
    elif isinstance(element.tag, str):
        tag = element.tag
    else:
        raise CompositionError("unsupported_xml_node", "unknown XML node")

    return {
        "attributes": sorted(element.attrib.items()),
        "children": [_structural_value(child) for child in list(element)],
        "tag": tag,
        "tail": _meaningful_text(element.tail),
        "text": _meaningful_text(element.text),
    }


def structural_digest(element: ET.Element) -> str:
    payload = json.dumps(
        _structural_value(element),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256_bytes(payload)


class _ForbiddenXmlConstruct(Exception):
    """Internal signal from Expat handlers; never crosses the public API."""


def _reject_forbidden_xml_constructs(data: bytes, source: str) -> None:
    """Reject DTD/entity constructs independent of the XML byte encoding."""

    parser = expat.ParserCreate()

    def reject(*_args: object) -> None:
        raise _ForbiddenXmlConstruct

    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.UnparsedEntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    try:
        parser.Parse(data, True)
    except _ForbiddenXmlConstruct as exc:
        raise CompositionError("forbidden_dtd", source) from exc
    except (expat.ExpatError, LookupError):
        # ElementTree below owns the public malformed-XML diagnostic.
        return


def parse_single_page(data: bytes, source: str = "<memory>") -> ValidatedPage:
    """Parse and validate one uncompressed single-page native mxfile."""

    _reject_forbidden_xml_constructs(data, source)
    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        root = ET.fromstring(data, parser=parser)
    except (ET.ParseError, LookupError) as exc:
        raise CompositionError("invalid_xml", f"{source}: {exc}") from exc

    if root.tag != "mxfile":
        raise CompositionError("invalid_root", f"{source}: expected mxfile")

    compressed = root.get("compressed")
    if compressed not in (None, "false", "0"):
        raise CompositionError(
            "compressed_input",
            f"{source}: expected an uncompressed mxfile",
        )

    if _meaningful_text(root.text) is not None:
        raise CompositionError("unexpected_root_text", source)

    root_children = list(root)
    if any(child.tag != "diagram" for child in root_children):
        raise CompositionError("unexpected_root_child", source)
    if len(root_children) != 1:
        raise CompositionError(
            "single_page_required",
            f"{source}: found {len(root_children)} diagrams",
        )

    diagram = root_children[0]
    if _meaningful_text(diagram.tail) is not None:
        raise CompositionError("unexpected_root_text", source)
    if "id" not in diagram.attrib:
        raise CompositionError("missing_page_id", source)
    page_id = diagram.attrib["id"]
    if page_id.strip() == "":
        raise CompositionError("empty_page_id", source)

    if "name" not in diagram.attrib:
        raise CompositionError("missing_page_name", source)
    name = diagram.attrib["name"]
    if name.strip() == "":
        raise CompositionError("empty_page_name", source)

    if _meaningful_text(diagram.text) is not None:
        raise CompositionError(
            "compressed_page_payload",
            f"{source}: diagram contains text instead of mxGraphModel",
        )

    diagram_children = list(diagram)
    if len(diagram_children) != 1 or diagram_children[0].tag != "mxGraphModel":
        raise CompositionError(
            "single_model_required",
            f"{source}: expected exactly one mxGraphModel",
        )

    model = diagram_children[0]
    if _meaningful_text(model.tail) is not None:
        raise CompositionError("unexpected_diagram_text", source)
    try:
        diagram_copy = copy.deepcopy(diagram)
        diagram_digest = structural_digest(diagram)
        model_digest = structural_digest(model)
    except RecursionError as exc:
        raise CompositionError("xml_nesting_too_deep", source) from exc

    return ValidatedPage(
        source=source,
        page_id=page_id,
        name=name,
        diagram=diagram_copy,
        diagram_digest=diagram_digest,
        model_digest=model_digest,
    )


def load_pages(input_paths: Sequence[Path]) -> tuple[ValidatedPage, ...]:
    if not input_paths:
        raise CompositionError("empty_input", "at least one page is required")

    pages: list[ValidatedPage] = []
    for path in input_paths:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CompositionError("input_read_failed", f"{path.name}: {exc}") from exc
        pages.append(parse_single_page(data, source=path.name))

    seen: set[str] = set()
    duplicates: list[str] = []
    for page in pages:
        if page.page_id in seen and page.page_id not in duplicates:
            duplicates.append(page.page_id)
        seen.add(page.page_id)
    if duplicates:
        raise CompositionError(
            "duplicate_page_id",
            ",".join(sorted(duplicates)),
        )

    return tuple(pages)


def _serialize(root: ET.Element) -> bytes:
    # C14N 2.0 fixes attribute ordering and empty-element spelling across runs.
    raw = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    canonical = ET.canonicalize(xml_data=raw, with_comments=True)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + canonical
        + "\n"
    ).encode("utf-8")


def compose_pages(pages: Sequence[ValidatedPage]) -> tuple[bytes, CompositionReceipt]:
    if not pages:
        raise CompositionError("empty_input", "at least one page is required")

    ids = [page.page_id for page in pages]
    if len(ids) != len(set(ids)):
        raise CompositionError("duplicate_page_id", "input page IDs are not unique")

    root = ET.Element(
        "mxfile",
        {
            "compressed": "false",
            "pages": str(len(pages)),
        },
    )
    for page in pages:
        diagram = copy.deepcopy(page.diagram)
        diagram.tail = None
        root.append(diagram)

    output = _serialize(root)
    receipt = verify_composition(output, pages)
    return output, receipt


def verify_composition(
    output: bytes,
    expected_pages: Sequence[ValidatedPage],
) -> CompositionReceipt:
    """Verify output document identity, order, and opaque model preservation."""

    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        root = ET.fromstring(output, parser=parser)
    except ET.ParseError as exc:
        raise CompositionError("invalid_output_xml", str(exc)) from exc

    if root.tag != "mxfile":
        raise CompositionError("invalid_output_root", root.tag)
    if root.attrib != {
        "compressed": "false",
        "pages": str(len(expected_pages)),
    }:
        raise CompositionError(
            "invalid_output_attributes",
            json.dumps(root.attrib, sort_keys=True),
        )
    if _meaningful_text(root.text) is not None:
        raise CompositionError("unexpected_output_text", "mxfile")

    diagrams = list(root)
    if any(_meaningful_text(diagram.tail) is not None for diagram in diagrams):
        raise CompositionError("unexpected_output_text", "diagram tail")
    if any(diagram.tag != "diagram" for diagram in diagrams):
        raise CompositionError("unexpected_output_child", "mxfile")
    if len(diagrams) != len(expected_pages):
        raise CompositionError(
            "output_page_count_mismatch",
            f"expected {len(expected_pages)}, found {len(diagrams)}",
        )

    receipts: list[PageReceipt] = []
    for index, (diagram, expected) in enumerate(zip(diagrams, expected_pages)):
        page_id = diagram.get("id")
        name = diagram.get("name")
        if page_id != expected.page_id:
            raise CompositionError(
                "page_order_or_id_mismatch",
                f"index {index}: expected {expected.page_id}, found {page_id}",
            )
        if name != expected.name:
            raise CompositionError(
                "page_name_mismatch",
                f"{expected.page_id}: expected {expected.name!r}, found {name!r}",
            )
        if diagram.attrib != expected.diagram.attrib:
            raise CompositionError(
                "page_attributes_mutated",
                expected.page_id,
            )
        if _meaningful_text(diagram.text) is not None:
            raise CompositionError("compressed_page_payload", expected.page_id)

        children = list(diagram)
        if len(children) != 1 or children[0].tag != "mxGraphModel":
            raise CompositionError("single_model_required", expected.page_id)

        try:
            diagram_digest = structural_digest(diagram)
            model_digest = structural_digest(children[0])
        except RecursionError as exc:
            raise CompositionError("xml_nesting_too_deep", expected.page_id) from exc
        if diagram_digest != expected.diagram_digest:
            raise CompositionError("diagram_mutated", expected.page_id)
        if model_digest != expected.model_digest:
            raise CompositionError("model_mutated", expected.page_id)

        receipts.append(
            PageReceipt(
                page_id=expected.page_id,
                name=expected.name,
                diagram_digest=diagram_digest,
                model_digest=model_digest,
            )
        )

    return CompositionReceipt(
        kind="mxfile.composition.receipt.v1",
        page_count=len(expected_pages),
        page_order=tuple(page.page_id for page in expected_pages),
        pages=tuple(receipts),
        output_sha256=sha256_bytes(output),
    )


def atomic_write(path: Path, data: bytes) -> None:
    """Atomically replace output without leaving partial files."""

    parent = path.parent
    if not parent.is_dir():
        raise CompositionError("output_parent_missing", str(parent))

    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=parent,
        )
    except OSError as exc:
        raise CompositionError("output_temp_create_failed", f"{path}: {exc}") from exc

    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise CompositionError("output_write_failed", f"{path}: {exc}") from exc
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def compose_files(
    input_paths: Sequence[Path],
    output_path: Path,
) -> CompositionReceipt:
    """Validate all inputs, compose, verify, then atomically emit output."""

    pages = load_pages(input_paths)
    output, receipt = compose_pages(pages)
    atomic_write(output_path, output)
    return receipt


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compose ordered single-page draw.io mxfiles into one mxfile."
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("inputs", nargs="*", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        receipt = compose_files(args.inputs, args.output)
    except CompositionError as exc:
        print(_json_dump({"code": exc.code, "detail": exc.detail}), file=sys.stderr)
        return 2
    print(_json_dump(receipt.to_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
