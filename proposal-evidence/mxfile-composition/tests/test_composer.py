from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import composer  # noqa: E402
from invalid_cases import INVALID_CASES  # noqa: E402


VALID = ROOT / "fixtures" / "valid"
COMPOSER = ROOT / "composer.py"


def parse_xml(data: bytes) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    return ET.fromstring(data, parser=parser)


class ComposerTests(unittest.TestCase):
    def valid_paths(self, count: int = 5) -> list[Path]:
        return [VALID / f"page-{index:02d}.drawio" for index in range(1, count + 1)]

    def load(self, count: int = 5) -> tuple[composer.ValidatedPage, ...]:
        return composer.load_pages(self.valid_paths(count))

    def _invalid_file(self, directory: str, name: str) -> Path:
        from invalid_cases import BY_NAME

        path = Path(directory) / f"{name}.drawio"
        path.write_bytes(BY_NAME[name][1])
        return path

    def assert_error(self, code: str, callable_, *args) -> composer.CompositionError:
        with self.assertRaises(composer.CompositionError) as context:
            callable_(*args)
        self.assertEqual(context.exception.code, code)
        return context.exception

    def test_valid_fixtures_parse(self) -> None:
        pages = self.load(5)
        self.assertEqual([page.page_id for page in pages], [f"page-{i:02d}" for i in range(1, 6)])
        self.assertTrue(all(len(page.model_digest) == 64 for page in pages))

    def test_valid_utf16_single_page_is_supported(self) -> None:
        text = (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<mxfile compressed="false"><diagram id="utf16" name="日本語">'
            '<mxGraphModel><root><mxCell id="0" /></root></mxGraphModel>'
            '</diagram></mxfile>'
        )
        page = composer.parse_single_page(text.encode("utf-16"), "utf16")
        output, receipt = composer.compose_pages((page,))
        self.assertEqual(receipt.page_order, ("utf16",))
        self.assertEqual(list(parse_xml(output))[0].get("name"), "日本語")

    def test_compose_one_two_and_five_pages(self) -> None:
        for count in (1, 2, 5):
            with self.subTest(count=count):
                pages = self.load(count)
                output, receipt = composer.compose_pages(pages)
                root = parse_xml(output)
                self.assertEqual(root.tag, "mxfile")
                self.assertEqual(root.attrib, {"compressed": "false", "pages": str(count)})
                self.assertEqual(len(list(root)), count)
                self.assertEqual(receipt.page_count, count)

    def test_input_order_is_output_order(self) -> None:
        paths = [VALID / "page-04.drawio", VALID / "page-01.drawio", VALID / "page-05.drawio"]
        pages = composer.load_pages(paths)
        output, receipt = composer.compose_pages(pages)
        ids = [diagram.get("id") for diagram in parse_xml(output)]
        self.assertEqual(ids, ["page-04", "page-01", "page-05"])
        self.assertEqual(list(receipt.page_order), ids)

    def test_page_identity_attributes_and_models_are_preserved(self) -> None:
        pages = self.load(5)
        output, receipt = composer.compose_pages(pages)
        diagrams = list(parse_xml(output))
        for expected, actual, page_receipt in zip(pages, diagrams, receipt.pages):
            self.assertEqual(actual.attrib, expected.diagram.attrib)
            self.assertEqual(composer.structural_digest(actual), expected.diagram_digest)
            self.assertEqual(composer.structural_digest(list(actual)[0]), expected.model_digest)
            self.assertEqual(page_receipt.diagram_digest, expected.diagram_digest)
            self.assertEqual(page_receipt.model_digest, expected.model_digest)

    def test_bendpoints_user_objects_layers_and_styles_survive(self) -> None:
        pages = self.load(5)
        output, _ = composer.compose_pages(pages)
        root = parse_xml(output)
        xml = ET.tostring(root, encoding="unicode")
        for marker in (
            'id="edge:a-b"',
            'as="points"',
            'owner="COO"',
            'custom="preserve-me"',
            'condition="change_requested=true"',
            'visible="0"',
            '<!--opaque-model-comment-->',
            'value="&lt;b&gt;release/v1&lt;/b&gt;&lt;br&gt;ready"',
        ):
            self.assertIn(marker, xml)

    def test_repeated_runs_are_byte_identical(self) -> None:
        pages = self.load(5)
        first, first_receipt = composer.compose_pages(pages)
        second, second_receipt = composer.compose_pages(pages)
        self.assertEqual(first, second)
        self.assertEqual(first_receipt.to_dict(), second_receipt.to_dict())

    def test_single_page_composition_is_semantically_identical(self) -> None:
        page = self.load(1)[0]
        output, _ = composer.compose_pages((page,))
        output_diagram = list(parse_xml(output))[0]
        self.assertEqual(composer.structural_digest(output_diagram), page.diagram_digest)
        self.assertEqual(composer.structural_digest(list(output_diagram)[0]), page.model_digest)

    def test_empty_input_is_rejected(self) -> None:
        self.assert_error("empty_input", composer.load_pages, [])
        self.assert_error("empty_input", composer.compose_pages, ())

    def test_invalid_fixture_contracts_fail_closed(self) -> None:
        for name, code, data in INVALID_CASES:
            with self.subTest(name=name):
                self.assert_error(code, composer.parse_single_page, data, name)

    def test_duplicate_page_ids_are_rejected(self) -> None:
        path = VALID / "page-01.drawio"
        self.assert_error("duplicate_page_id", composer.load_pages, [path, path])

    def test_invalid_input_never_creates_new_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.drawio"
            self.assert_error(
                "invalid_xml",
                composer.compose_files,
                [VALID / "page-01.drawio", self._invalid_file(directory, "malformed_xml")],
                output,
            )
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])

    def test_invalid_input_never_replaces_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.drawio"
            sentinel = b"existing-output-must-survive\n"
            output.write_bytes(sentinel)
            self.assert_error(
                "invalid_xml",
                composer.compose_files,
                [VALID / "page-01.drawio", self._invalid_file(directory, "malformed_xml")],
                output,
            )
            self.assertEqual(output.read_bytes(), sentinel)
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])

    def test_successful_write_is_verified_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.drawio"
            receipt = composer.compose_files(self.valid_paths(2), output)
            self.assertTrue(output.exists())
            pages = self.load(2)
            verified = composer.verify_composition(output.read_bytes(), pages)
            self.assertEqual(receipt.to_dict(), verified.to_dict())
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])

    def test_output_has_no_wall_clock_metadata(self) -> None:
        pages = self.load(2)
        old = os.environ.get("SOURCE_DATE_EPOCH")
        try:
            os.environ["SOURCE_DATE_EPOCH"] = "0"
            first, _ = composer.compose_pages(pages)
            os.environ["SOURCE_DATE_EPOCH"] = "9999999999"
            second, _ = composer.compose_pages(pages)
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old
        self.assertEqual(first, second)
        root = parse_xml(first)
        forbidden = {"modified", "created", "timestamp", "time", "date", "agent"}
        self.assertTrue(forbidden.isdisjoint(root.attrib))
        self.assertEqual(set(root.attrib), {"compressed", "pages"})

    def _mutate_output(self, output: bytes, mutation) -> bytes:
        root = parse_xml(output)
        mutation(root)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"

    def test_mutated_cell_id_is_rejected(self) -> None:
        pages = self.load(1)
        output, _ = composer.compose_pages(pages)

        def mutate(root: ET.Element) -> None:
            root.find(".//mxCell[@id='region:company']").set("id", "region:mutated")  # type: ignore[union-attr]

        mutated = self._mutate_output(output, mutate)
        self.assert_error("diagram_mutated", composer.verify_composition, mutated, pages)

    def test_mutated_attribute_is_rejected(self) -> None:
        pages = composer.load_pages([VALID / "page-03.drawio"])
        output, _ = composer.compose_pages(pages)

        def mutate(root: ET.Element) -> None:
            root.find(".//object[@id='object:agent']").set("owner", "CPO")  # type: ignore[union-attr]

        mutated = self._mutate_output(output, mutate)
        self.assert_error("diagram_mutated", composer.verify_composition, mutated, pages)

    def test_mutated_geometry_is_rejected(self) -> None:
        pages = self.load(1)
        output, _ = composer.compose_pages(pages)

        def mutate(root: ET.Element) -> None:
            root.find(".//mxCell[@id='region:company']/mxGeometry").set("x", "41")  # type: ignore[union-attr]

        mutated = self._mutate_output(output, mutate)
        self.assert_error("diagram_mutated", composer.verify_composition, mutated, pages)

    def test_removed_user_object_is_rejected(self) -> None:
        pages = composer.load_pages([VALID / "page-03.drawio"])
        output, _ = composer.compose_pages(pages)

        def mutate(root: ET.Element) -> None:
            model_root = root.find(".//mxGraphModel/root")
            obj = model_root.find("object[@id='object:agent']")  # type: ignore[union-attr]
            model_root.remove(obj)  # type: ignore[arg-type,union-attr]

        mutated = self._mutate_output(output, mutate)
        self.assert_error("diagram_mutated", composer.verify_composition, mutated, pages)

    def test_changed_page_order_is_rejected(self) -> None:
        pages = self.load(2)
        output, _ = composer.compose_pages(pages)
        root = parse_xml(output)
        first, second = list(root)
        root.remove(first)
        root.remove(second)
        root.append(second)
        root.append(first)
        changed = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        self.assert_error("page_order_or_id_mismatch", composer.verify_composition, changed, pages)

    def test_cli_empty_input_fails_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.drawio"
            result = subprocess.run(
                [sys.executable, str(COMPOSER), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(result.stderr)["code"], "empty_input")

    def test_cli_receipt_is_machine_readable_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.drawio"
            command = [
                sys.executable,
                str(COMPOSER),
                "--output",
                str(output),
                *(str(path) for path in self.valid_paths(2)),
            ]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            first_bytes = output.read_bytes()
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first_bytes, output.read_bytes())
            receipt = json.loads(first.stdout)
            self.assertEqual(receipt["page_order"], ["page-01", "page-02"])

    def test_output_parent_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing" / "out.drawio"
            self.assert_error(
                "output_parent_missing",
                composer.compose_files,
                self.valid_paths(1),
                output,
            )
            self.assertFalse(output.exists())

    def test_temp_creation_failure_is_machine_readable_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.drawio"
            with mock.patch.object(
                composer.tempfile, "mkstemp", side_effect=OSError("denied")
            ):
                self.assert_error(
                    "output_temp_create_failed",
                    composer.compose_files,
                    self.valid_paths(1),
                    output,
                )
            self.assertFalse(output.exists())

    def test_replace_failure_preserves_existing_output_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.drawio"
            sentinel = b"existing-output\n"
            output.write_bytes(sentinel)
            with mock.patch.object(
                composer.os, "replace", side_effect=OSError("denied")
            ):
                self.assert_error(
                    "output_write_failed",
                    composer.compose_files,
                    self.valid_paths(1),
                    output,
                )
            self.assertEqual(output.read_bytes(), sentinel)
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
