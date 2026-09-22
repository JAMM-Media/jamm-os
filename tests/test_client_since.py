# tests/test_client_since.py

"""Tests for Client.client_since (ruling R8, Sep 17, 2026).

client_since is the date the client's relationship with the FIRM began,
which is a different fact from created_at, the date the client row was
created in JAMM. It is firm-entered, optional, and read by nothing as of
Sep 2026, so these tests are the only thing standing between it and silent
breakage.

The won path deliberately does NOT stamp it (R8), and the TaxDome importer
is out of scope.
"""

import io
import uuid
from datetime import date

import pytest

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.services.client_service import import_clients_csv


CSV_HEADER = "name,email,entity_type,client_since\n"


def _csv_upload(client, headers, body: str):
    """POST a CSV string to the bulk import endpoint."""
    return client.post(
        "/clients/import",
        headers=headers,
        files={"file": ("clients.csv", io.BytesIO(body.encode("utf-8")), "text/csv")},
    )


def _read_client(firm_id, name):
    db = TestingSessionLocal()
    try:
        row = (
            db.query(Client)
            .filter(Client.firm_id == firm_id, Client.name == name)
            .one_or_none()
        )
        if row is not None:
            _ = row.id, row.client_since, row.name
        return row
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API round trip
# ---------------------------------------------------------------------------

def test_create_with_client_since_round_trips_through_client_out(client, firm_a_owner):
    """A date sent on create comes back on ClientOut as an ISO string."""
    headers = firm_a_owner["headers"]
    r = client.post(
        "/clients/",
        headers=headers,
        json={"name": "Since Co", "email": f"since-{uuid.uuid4()}@example.com",
              "client_since": "2019-04-01"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["client_since"] == "2019-04-01"

    stored = _read_client(uuid.UUID(firm_a_owner["firm_id"]), "Since Co")
    assert stored.client_since == date(2019, 4, 1), (
        "the value must be a real DATE in the database, not a string"
    )


def test_create_without_client_since_is_none(client, firm_a_owner):
    """The column is optional everywhere."""
    headers = firm_a_owner["headers"]
    r = client.post(
        "/clients/",
        headers=headers,
        json={"name": "No Since Co", "email": f"nosince-{uuid.uuid4()}@example.com"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["client_since"] is None


def test_update_sets_and_then_clears_client_since(client, firm_a_owner):
    """PATCH sets the date, and an explicit null clears it.

    The clear is the half worth pinning: null has to reach the column rather
    than being read as "field omitted, leave alone".
    """
    headers = firm_a_owner["headers"]
    created = client.post(
        "/clients/",
        headers=headers,
        json={"name": "Patch Since Co", "email": f"patchsince-{uuid.uuid4()}@example.com"},
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]
    assert created.json()["client_since"] is None

    setr = client.patch(
        f"/clients/{client_id}", headers=headers, json={"client_since": "2021-12-31"}
    )
    assert setr.status_code == 200, setr.text
    assert setr.json()["client_since"] == "2021-12-31"
    assert _read_client(uuid.UUID(firm_a_owner["firm_id"]), "Patch Since Co").client_since == date(
        2021, 12, 31
    )

    clearr = client.patch(
        f"/clients/{client_id}", headers=headers, json={"client_since": None}
    )
    assert clearr.status_code == 200, clearr.text
    assert clearr.json()["client_since"] is None
    assert _read_client(uuid.UUID(firm_a_owner["firm_id"]), "Patch Since Co").client_since is None


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def test_csv_row_with_a_valid_date_lands(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = _csv_upload(
        client, headers,
        CSV_HEADER + f"CSV Good,csvgood-{uuid.uuid4()}@example.com,business,2020-06-15\n",
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1, r.json()
    assert r.json()["errors"] == []

    stored = _read_client(uuid.UUID(firm_a_owner["firm_id"]), "CSV Good")
    assert stored is not None
    assert stored.client_since == date(2020, 6, 15)


def test_csv_row_with_an_invalid_date_is_a_row_error_and_creates_nothing(client, firm_a_owner):
    """An unparseable date is a row error in the entity_type shape, not a crash.

    The row must not be created. Checked by reading the table directly, not
    by trusting the created count, because a count is a summary and the
    question here is whether a specific row exists.
    """
    headers = firm_a_owner["headers"]
    r = _csv_upload(
        client, headers,
        CSV_HEADER + f"CSV Bad,csvbad-{uuid.uuid4()}@example.com,business,06/15/2020\n",
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["created"] == 0, payload
    assert payload["errors"] == [
        {"row": 2, "reason": "Invalid client_since '06/15/2020'. Use YYYY-MM-DD."}
    ], payload

    assert _read_client(uuid.UUID(firm_a_owner["firm_id"]), "CSV Bad") is None, (
        "a row with a bad date must not create a client"
    )


def test_csv_one_bad_date_does_not_stop_the_other_rows(client, firm_a_owner):
    """The error is per row: a bad date must not take down the whole import."""
    headers = firm_a_owner["headers"]
    r = _csv_upload(
        client, headers,
        CSV_HEADER
        + f"CSV Bad Two,csvbad2-{uuid.uuid4()}@example.com,business,not-a-date\n"
        + f"CSV Good Two,csvgood2-{uuid.uuid4()}@example.com,business,2022-01-03\n",
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["created"] == 1, payload
    assert len(payload["errors"]) == 1, payload
    assert _read_client(uuid.UUID(firm_a_owner["firm_id"]), "CSV Bad Two") is None
    good = _read_client(uuid.UUID(firm_a_owner["firm_id"]), "CSV Good Two")
    assert good is not None and good.client_since == date(2022, 1, 3)


def test_csv_with_the_column_absent_creates_the_client_with_none(client, firm_a_owner):
    """Every existing CSV in the wild lacks this column; they must still import."""
    headers = firm_a_owner["headers"]
    r = _csv_upload(
        client, headers,
        "name,email,entity_type\n"
        + f"CSV NoCol,csvnocol-{uuid.uuid4()}@example.com,individual\n",
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1, r.json()
    assert r.json()["errors"] == []

    stored = _read_client(uuid.UUID(firm_a_owner["firm_id"]), "CSV NoCol")
    assert stored is not None
    assert stored.client_since is None


def test_csv_with_an_empty_client_since_cell_is_none(client, firm_a_owner):
    """An empty cell means absent, not an error."""
    headers = firm_a_owner["headers"]
    r = _csv_upload(
        client, headers,
        CSV_HEADER + f"CSV Empty,csvempty-{uuid.uuid4()}@example.com,individual,\n",
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1, r.json()
    assert r.json()["errors"] == []
    assert _read_client(uuid.UUID(firm_a_owner["firm_id"]), "CSV Empty").client_since is None


def test_importer_called_directly_reports_the_row_error(firm_a_owner):
    """The service is the thing R8 names, so it is also tested without HTTP.

    Row numbering starts at 2 because row 1 is the header.
    """
    db = TestingSessionLocal()
    try:
        created, skipped, errors = import_clients_csv(
            db=db,
            rows=[{"name": "Direct Bad", "client_since": "2020-13-45"}],
            firm_id=uuid.UUID(firm_a_owner["firm_id"]),
        )
    finally:
        db.close()
    assert created == 0
    assert errors == [
        {"row": 2, "reason": "Invalid client_since '2020-13-45'. Use YYYY-MM-DD."}
    ]
