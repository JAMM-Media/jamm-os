# tests/test_s3_key_layout.py
"""Unit tests for the three _build_s3_key layouts. No database needed."""

from app.services.document_service import _build_s3_key

FIRM   = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CLIENT = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ENG    = "cccccccc-cccc-cccc-cccc-cccccccccccc"
DOC    = "dddddddd-dddd-dddd-dddd-dddddddddddd"
NAME   = "report.pdf"


def test_engagement_scope_key():
    key = _build_s3_key(FIRM, CLIENT, ENG, DOC, NAME)
    assert key == f"{FIRM}/{CLIENT}/{ENG}/{DOC}/{NAME}"


def test_client_scope_key():
    key = _build_s3_key(FIRM, CLIENT, None, DOC, NAME)
    assert key == f"{FIRM}/{CLIENT}/permanent/{DOC}/{NAME}"


def test_firm_library_scope_key():
    key = _build_s3_key(FIRM, None, None, DOC, NAME)
    assert key == f"{FIRM}/firm_library/{DOC}/{NAME}"


def test_no_none_in_any_scope():
    eng_key = _build_s3_key(FIRM, CLIENT, ENG, DOC, NAME)
    client_key = _build_s3_key(FIRM, CLIENT, None, DOC, NAME)
    lib_key = _build_s3_key(FIRM, None, None, DOC, NAME)
    for key in (eng_key, client_key, lib_key):
        assert "None" not in key, f"Literal 'None' found in key: {key}"
