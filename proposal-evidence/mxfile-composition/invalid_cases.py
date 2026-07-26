"""Table-driven invalid single-page mxfile fixtures used only by proof/tests."""

from __future__ import annotations

INVALID_CASES: tuple[tuple[str, str, bytes], ...] = (
    (
        "malformed_xml",
        "invalid_xml",
        b'<mxfile><diagram id="broken" name="Broken"><mxGraphModel></diagram></mxfile>',
    ),
    (
        "unknown_encoding",
        "invalid_xml",
        b'<?xml version="1.0" encoding="X-UNKNOWN"?><mxfile compressed="false"><diagram id="x" name="X"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "deeply_nested_model",
        "xml_nesting_too_deep",
        (
            b'<mxfile compressed="false"><diagram id="deep" name="Deep"><mxGraphModel>'
            + (b'<x>' * 1200)
            + (b'</x>' * 1200)
            + b'</mxGraphModel></diagram></mxfile>'
        ),
    ),
    (
        "non_mxfile_root",
        "invalid_root",
        b'<root><diagram id="x" name="x"><mxGraphModel /></diagram></root>',
    ),
    (
        "zero_diagrams",
        "single_page_required",
        b'<mxfile compressed="false" pages="0" />',
    ),
    (
        "multiple_diagrams",
        "single_page_required",
        b'<mxfile compressed="false"><diagram id="a" name="A"><mxGraphModel /></diagram><diagram id="b" name="B"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "missing_model",
        "single_model_required",
        b'<mxfile compressed="false"><diagram id="x" name="X" /></mxfile>',
    ),
    (
        "compressed_page_text",
        "compressed_page_payload",
        b'<mxfile compressed="false"><diagram id="x" name="X">7Zabc</diagram></mxfile>',
    ),
    (
        "compressed_root",
        "compressed_input",
        b'<mxfile compressed="true"><diagram id="x" name="X"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "missing_page_id",
        "missing_page_id",
        b'<mxfile compressed="false"><diagram name="X"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "empty_page_id",
        "empty_page_id",
        b'<mxfile compressed="false"><diagram id="  " name="X"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "missing_page_name",
        "missing_page_name",
        b'<mxfile compressed="false"><diagram id="x"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "empty_page_name",
        "empty_page_name",
        b'<mxfile compressed="false"><diagram id="x" name="  "><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "unexpected_root_child",
        "unexpected_root_child",
        b'<mxfile compressed="false"><metadata /><diagram id="x" name="X"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "forbidden_dtd",
        "forbidden_dtd",
        b'<!DOCTYPE mxfile [<!ENTITY x "boom">]><mxfile compressed="false"><diagram id="x" name="&x;"><mxGraphModel /></diagram></mxfile>',
    ),
    (
        "forbidden_utf16_dtd",
        "forbidden_dtd",
        ('<?xml version="1.0" encoding="UTF-16"?>'
         '<!DOCTYPE mxfile [<!ENTITY x "boom">]>'
         '<mxfile compressed="false"><diagram id="x" name="&x;">'
         '<mxGraphModel /></diagram></mxfile>').encode("utf-16"),
    ),
)

BY_NAME = {name: (code, data) for name, code, data in INVALID_CASES}
