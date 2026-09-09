# tests/test_filesystem_phase2_access_gate.py
"""
Guard tests for Filesystem Phase 2: document access gate.

Spec reference: Filesystem Build Specification, Section 6.

Tests cover:
  1. Cross-engagement leak (same client, two engagements)
  2. Cross-tenant leak (firm A staff vs firm B documents)
  3. Firm owner and manager bypass engagement membership
  4. Trio enforcement on delete (administrator/manager/owner only)
  5. Parent-mismatch upload rejection (hardening A)
  6. Identical 404 bodies for not-found vs denied (hardening B)
  7. No document metadata in denied response (hardening C)
  8. AST endpoint-inventory guard -- every endpoint has a gate call (hardening E)
  9. firm_library scope readable by any staff regardless of membership
 10. Watched-fail verification of the AST guard
"""

import ast
import io
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash

_DOCS_PATH = Path(__file__).resolve().parent.parent / "app" / "api" / "documents.py"

_GATE_CALLS = frozenset([
    "assert_can_access_document",
    "assert_can_delete_document",
    "assert_can_upload_to_engagement",
    "filter_accessible_documents",
])


# ---------------------------------------------------------------------------
# Shared setup helpers
# ---------------------------------------------------------------------------

def _create_user(firm_id, role=UserRole.staff):
    email = f"user-{uuid.uuid4()}@test.com"
    password = "testpass123"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return email, password, user_id


def _add_member(firm_id, engagement_id, user_id, *, is_administrator=False):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=firm_id,
            engagement_id=engagement_id,
            user_id=user_id,
            is_administrator=is_administrator,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _login(test_client, email, password):
    r = test_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_client_and_engagement(test_client, headers, *, client_name=None, eng_name=None):
    cl = test_client.post(
        "/clients/",
        json={"name": client_name or f"Client-{uuid.uuid4()}"},
        headers=headers,
    )
    assert cl.status_code == 201, cl.text
    client_id = cl.json()["id"]

    eng = test_client.post(
        "/engagements/",
        json={"name": eng_name or f"Eng-{uuid.uuid4()}", "client_id": client_id},
        headers=headers,
    )
    assert eng.status_code == 201, eng.text
    return client_id, eng.json()["id"]


def _upload_doc(test_client, headers, client_id, engagement_id, filename="doc.txt"):
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = test_client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": (filename, io.BytesIO(b"content"), "text/plain")},
            headers=headers,
        )
    return r


# ---------------------------------------------------------------------------
# 1. Cross-engagement leak (same client, engagement A vs B)
# ---------------------------------------------------------------------------

def test_cross_engagement_list_denied(client, firm_a_owner):
    """Staff member of eng-A cannot see eng-B documents in list."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_a_id = _make_client_and_engagement(client, owner_headers)
    eng_b = client.post(
        "/engagements/",
        json={"name": "Eng B", "client_id": client_id},
        headers=owner_headers,
    )
    assert eng_b.status_code == 201
    eng_b_id = eng_b.json()["id"]

    r = _upload_doc(client, owner_headers, client_id, eng_b_id)
    assert r.status_code == 201
    eng_b_doc_id = r.json()["id"]

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_a_id, user_id)
    staff_headers = _login(client, email, password)

    r = client.get("/documents/", headers=staff_headers)
    assert r.status_code == 200
    returned_ids = [d["id"] for d in r.json()["items"]]
    assert eng_b_doc_id not in returned_ids, "Cross-engagement doc must not appear in list"


def test_cross_engagement_get_denied(client, firm_a_owner):
    """Staff member of eng-A gets 404 on a document belonging to eng-B."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_a_id = _make_client_and_engagement(client, owner_headers)
    eng_b = client.post(
        "/engagements/",
        json={"name": "Eng B", "client_id": client_id},
        headers=owner_headers,
    )
    eng_b_id = eng_b.json()["id"]
    r = _upload_doc(client, owner_headers, client_id, eng_b_id)
    doc_id = r.json()["id"]

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_a_id, user_id)
    staff_headers = _login(client, email, password)

    assert client.get(f"/documents/{doc_id}", headers=staff_headers).status_code == 404


def test_cross_engagement_download_denied(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_a_id = _make_client_and_engagement(client, owner_headers)
    eng_b = client.post(
        "/engagements/",
        json={"name": "Eng B", "client_id": client_id},
        headers=owner_headers,
    )
    eng_b_id = eng_b.json()["id"]
    r = _upload_doc(client, owner_headers, client_id, eng_b_id)
    doc_id = r.json()["id"]

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_a_id, user_id)
    staff_headers = _login(client, email, password)

    with patch("app.api.documents.s3_service.generate_presigned_url"):
        r = client.get(f"/documents/{doc_id}/download", headers=staff_headers)
    assert r.status_code == 404


def test_cross_engagement_audit_denied(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_a_id = _make_client_and_engagement(client, owner_headers)
    eng_b = client.post(
        "/engagements/",
        json={"name": "Eng B", "client_id": client_id},
        headers=owner_headers,
    )
    eng_b_id = eng_b.json()["id"]
    r = _upload_doc(client, owner_headers, client_id, eng_b_id)
    doc_id = r.json()["id"]

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_a_id, user_id)
    staff_headers = _login(client, email, password)

    assert client.get(f"/documents/{doc_id}/audit", headers=staff_headers).status_code == 404


# ---------------------------------------------------------------------------
# 2. Cross-tenant leak
# ---------------------------------------------------------------------------

def test_cross_tenant_get_denied(client, firm_a_owner, firm_b_owner):
    client_id, eng_id = _make_client_and_engagement(client, firm_a_owner["headers"])
    r = _upload_doc(client, firm_a_owner["headers"], client_id, eng_id)
    doc_id = r.json()["id"]

    assert client.get(f"/documents/{doc_id}", headers=firm_b_owner["headers"]).status_code == 404


def test_cross_tenant_download_denied(client, firm_a_owner, firm_b_owner):
    client_id, eng_id = _make_client_and_engagement(client, firm_a_owner["headers"])
    r = _upload_doc(client, firm_a_owner["headers"], client_id, eng_id)
    doc_id = r.json()["id"]

    with patch("app.api.documents.s3_service.generate_presigned_url"):
        r = client.get(f"/documents/{doc_id}/download", headers=firm_b_owner["headers"])
    assert r.status_code == 404


def test_cross_tenant_audit_denied(client, firm_a_owner, firm_b_owner):
    client_id, eng_id = _make_client_and_engagement(client, firm_a_owner["headers"])
    r = _upload_doc(client, firm_a_owner["headers"], client_id, eng_id)
    doc_id = r.json()["id"]

    assert client.get(f"/documents/{doc_id}/audit", headers=firm_b_owner["headers"]).status_code == 404


def test_cross_tenant_delete_denied(client, firm_a_owner, firm_b_owner):
    client_id, eng_id = _make_client_and_engagement(client, firm_a_owner["headers"])
    r = _upload_doc(client, firm_a_owner["headers"], client_id, eng_id)
    doc_id = r.json()["id"]

    with patch("app.api.documents.s3_service.delete_object"):
        r = client.delete(f"/documents/{doc_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404


def test_cross_tenant_list_empty(client, firm_a_owner, firm_b_owner):
    client_id, eng_id = _make_client_and_engagement(client, firm_a_owner["headers"])
    _upload_doc(client, firm_a_owner["headers"], client_id, eng_id)

    r = client.get("/documents/", headers=firm_b_owner["headers"])
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# 3. Firm owner and manager bypass engagement membership
# ---------------------------------------------------------------------------

def test_owner_can_access_any_engagement_doc(client, firm_a_owner):
    """Firm owner accesses a document from an engagement they are not an
    explicit EngagementMember of."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    doc_id = r.json()["id"]

    r = client.get(f"/documents/{doc_id}", headers=owner_headers)
    assert r.status_code == 200


def test_manager_can_access_any_engagement_doc(client, firm_a_owner):
    """Manager role bypasses the membership gate entirely."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    doc_id = r.json()["id"]

    email, password, _ = _create_user(firm_id, role=UserRole.manager)
    mgr_headers = _login(client, email, password)

    r = client.get(f"/documents/{doc_id}", headers=mgr_headers)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 4. Trio enforcement on delete
# ---------------------------------------------------------------------------

def test_delete_refused_for_non_admin_member(client, firm_a_owner):
    """Regular engagement member (not administrator) cannot delete."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    doc_id = r.json()["id"]

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_id, user_id, is_administrator=False)
    staff_headers = _login(client, email, password)

    with patch("app.api.documents.s3_service.delete_object"):
        r = client.delete(f"/documents/{doc_id}", headers=staff_headers)
    assert r.status_code == 404


def test_delete_allowed_for_engagement_admin(client, firm_a_owner):
    """Engagement administrator can delete documents from their engagement."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    doc_id = r.json()["id"]

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_id, user_id, is_administrator=True)
    admin_headers = _login(client, email, password)

    with patch("app.api.documents.s3_service.delete_object"):
        r = client.delete(f"/documents/{doc_id}", headers=admin_headers)
    assert r.status_code == 204


def test_delete_allowed_for_firm_owner(client, firm_a_owner):
    """Firm owner can delete any document."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    doc_id = r.json()["id"]

    with patch("app.api.documents.s3_service.delete_object"):
        r = client.delete(f"/documents/{doc_id}", headers=owner_headers)
    assert r.status_code == 204


def test_delete_allowed_for_manager(client, firm_a_owner):
    """Manager can delete any document without being an engagement member."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    doc_id = r.json()["id"]

    email, password, _ = _create_user(firm_id, role=UserRole.manager)
    mgr_headers = _login(client, email, password)

    with patch("app.api.documents.s3_service.delete_object"):
        r = client.delete(f"/documents/{doc_id}", headers=mgr_headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# 5. Parent-mismatch upload rejection (hardening A)
# ---------------------------------------------------------------------------

def test_upload_parent_mismatch_refused(client, firm_a_owner):
    """Upload where client_id and engagement_id belong to different clients is refused."""
    owner_headers = firm_a_owner["headers"]

    cl1 = client.post("/clients/", json={"name": "Client X"}, headers=owner_headers)
    client_id_1 = cl1.json()["id"]
    cl2 = client.post("/clients/", json={"name": "Client Y"}, headers=owner_headers)
    client_id_2 = cl2.json()["id"]

    eng = client.post(
        "/engagements/",
        json={"name": "Eng for X", "client_id": client_id_1},
        headers=owner_headers,
    )
    eng_id = eng.json()["id"]

    # client_id_2 and eng_id are both real but do NOT belong together.
    r = _upload_doc(client, owner_headers, client_id_2, eng_id)
    assert r.status_code == 404, (
        f"Expected 404 for parent-mismatch upload, got {r.status_code}: {r.text}"
    )


def test_upload_nonmember_staff_refused(client, firm_a_owner):
    """Staff user who is not a member of the engagement cannot upload to it."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    email, password, _ = _create_user(firm_id)
    staff_headers = _login(client, email, password)

    r = _upload_doc(client, staff_headers, client_id, eng_id)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 6. Identical response bodies for not-found vs denied (hardening B)
# ---------------------------------------------------------------------------

def test_not_found_and_denied_responses_are_byte_identical(client, firm_a_owner):
    """
    A genuinely nonexistent doc ID and a real-but-denied doc ID must produce
    byte-identical 404 response bodies.
    """
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    r = _upload_doc(client, owner_headers, client_id, eng_id)
    real_doc_id = r.json()["id"]

    # Staff with no memberships: denied on the real doc
    email, password, _ = _create_user(firm_id)
    staff_headers = _login(client, email, password)

    r_nonexistent = client.get(f"/documents/{uuid.uuid4()}", headers=staff_headers)
    r_denied = client.get(f"/documents/{real_doc_id}", headers=staff_headers)

    assert r_nonexistent.status_code == 404
    assert r_denied.status_code == 404
    assert r_nonexistent.content == r_denied.content, (
        f"Response bodies differ.\n"
        f"Not-found body: {r_nonexistent.content}\n"
        f"Denied body:    {r_denied.content}"
    )


# ---------------------------------------------------------------------------
# 7. No document metadata before authorization (hardening C)
# ---------------------------------------------------------------------------

def test_denied_response_contains_no_document_metadata(client, firm_a_owner):
    """A denied get_document response must not leak filename, size, or doc ID."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    sentinel_filename = f"secret-{uuid.uuid4()}.pdf"
    r = _upload_doc(client, owner_headers, client_id, eng_id, filename=sentinel_filename)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    doc_size = str(r.json()["size_bytes"])

    email, password, _ = _create_user(firm_id)
    staff_headers = _login(client, email, password)

    r = client.get(f"/documents/{doc_id}", headers=staff_headers)
    assert r.status_code == 404
    body = r.text

    assert sentinel_filename not in body, f"Filename leaked in denied response: {body}"
    assert doc_size not in body, f"Size leaked in denied response: {body}"
    assert doc_id not in body, f"Document ID leaked in denied response: {body}"


# ---------------------------------------------------------------------------
# 8. AST endpoint-inventory guard (hardening E)
# ---------------------------------------------------------------------------

def _collect_call_names(func_node) -> set[str]:
    names = set()
    for child in ast.walk(func_node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                names.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                names.add(child.func.attr)
    return names


def _find_ungated_endpoints(source_text: str) -> list[str]:
    """Parse source_text and return names of @router endpoints with no gate call."""
    tree = ast.parse(source_text)
    _HTTP_METHODS = {"get", "post", "patch", "delete"}
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in _HTTP_METHODS
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
            ):
                continue
            calls = _collect_call_names(node)
            if not (calls & _GATE_CALLS):
                missing.append(f"{node.name} (line {node.lineno})")
    return missing


def test_all_document_endpoints_have_gate_call():
    """
    Every @router.get/post/patch/delete endpoint in documents.py must contain
    a call to one of the document access gate functions.

    To deliberately exempt an endpoint: add it to _EXPLICIT_EXEMPTIONS with a
    named reason, then remove it from the missing check below.
    """
    # Endpoints deliberately exempt from the document-level gate requirement.
    # Each must have an equivalent or stricter access control applied elsewhere.
    _EXPLICIT_EXEMPTIONS = {
        "purge_document": (
            "Purge is firm-owner-only via require_firm_owner (stricter than the trio). "
            "The document is verified to belong to this firm via get_document_any_state "
            "with firm_id scoping inside the service function."
        ),
        "purge_all_trash": (
            "Purge-all is firm-owner-only via require_firm_owner (stricter than the trio). "
            "Scope filtering inside list_trash ensures only this firm's documents are affected."
        ),
    }

    src = _DOCS_PATH.read_text()
    raw_missing = _find_ungated_endpoints(src)
    missing = [m for m in raw_missing if m.split(" ")[0] not in _EXPLICIT_EXEMPTIONS]

    assert not missing, (
        "Endpoints in documents.py with no document access gate call:\n"
        + "\n".join(f"  - {m}" for m in missing)
        + "\nAdd the appropriate gate call or add to _EXPLICIT_EXEMPTIONS with a reason."
    )


# ---------------------------------------------------------------------------
# 9. firm_library scope readable by all staff
# ---------------------------------------------------------------------------

def test_firm_library_document_readable_by_any_staff(client, firm_a_owner):
    """
    A document with scope='firm_library' is readable by any staff member
    regardless of engagement membership.

    Documents.py upload_document only creates engagement-scoped docs, so
    the firm_library doc is inserted directly via TestingSessionLocal.
    """
    firm_id = firm_a_owner["firm_id"]

    doc_id = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        doc = Document(
            id=doc_id,
            firm_id=firm_id,
            scope="firm_library",
            filename="firm-policy.pdf",
            s3_key=f"{firm_id}/lib/{doc_id}/firm-policy.pdf",
            content_type="application/pdf",
            size_bytes=512,
            source="staff",
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()

    # Staff user with zero engagement memberships
    email, password, _ = _create_user(firm_id)
    staff_headers = _login(client, email, password)

    r = client.get(f"/documents/{doc_id}", headers=staff_headers)
    assert r.status_code == 200, (
        f"firm_library doc should be readable by any staff; got {r.status_code}: {r.text}"
    )

    # Also confirm it appears in the list for this user
    r_list = client.get("/documents/", headers=staff_headers)
    assert r_list.status_code == 200
    ids_in_list = [d["id"] for d in r_list.json()["items"]]
    assert str(doc_id) in ids_in_list, "firm_library doc must appear in list for any staff"


# ---------------------------------------------------------------------------
# 10. Watched-fail verification of the AST guard (hardening E)
# ---------------------------------------------------------------------------

def test_ast_guard_catches_missing_gate_call():
    """
    Mutate documents.py to remove the gate call from upload_document and
    confirm the AST guard flags it by name. This proves the guard can fail.
    Restore is verified by re-running the real guard at the end.
    """
    src = _DOCS_PATH.read_text()

    # Replace the function call (has an opening paren) not the import line
    # (which ends in a comma). This keeps the AST parseable.
    mutated = src.replace(
        "assert_can_upload_to_engagement(",
        "not_a_gate_call(",
        1,
    )
    assert mutated != src, (
        "Mutation did not change the source -- the gate call anchor is wrong."
    )

    _EXEMPT = {"purge_document", "purge_all_trash"}

    missing_mutated = [
        m for m in _find_ungated_endpoints(mutated)
        if m.split(" ")[0] not in _EXEMPT
    ]
    assert "upload_document" in [m.split(" ")[0] for m in missing_mutated], (
        f"AST guard should have flagged 'upload_document' as ungated, "
        f"but non-exempt missing list was: {missing_mutated}"
    )

    # Confirm the real (unmodified) file still passes after exemptions.
    non_exempt_missing = [
        m for m in _find_ungated_endpoints(src)
        if m.split(" ")[0] not in _EXEMPT
    ]
    assert not non_exempt_missing, (
        "The real documents.py has ungated non-exempt endpoints -- gate wiring is broken."
    )
