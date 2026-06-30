# tests/test_irs_auth_activation.py

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.irs_auth_service import activate_authorization_for_envelope


FIRM_ID = uuid.uuid4()
ENVELOPE_ID = uuid.uuid4()
CLIENT_ID = uuid.uuid4()
AUTH_ID = uuid.uuid4()


def _make_auth(**kwargs):
    auth = MagicMock()
    auth.id = AUTH_ID
    auth.firm_id = FIRM_ID
    auth.client_id = CLIENT_ID
    auth.signature_envelope_id = ENVELOPE_ID
    auth.status = kwargs.get("status", "pending_signature")
    auth.form_type = kwargs.get("form_type", "8821")
    auth.valid_from = kwargs.get("valid_from", None)
    auth.valid_until = kwargs.get("valid_until", None)
    return auth


def _make_db(auth):
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = auth
    db.execute.return_value = execute_result
    return db


class TestActivateAuthorizationForEnvelope:

    @patch("app.services.irs_auth_service.log_event")
    def test_activation_flips_pending_to_active(self, mock_log_event):
        auth = _make_auth(status="pending_signature", form_type="8821", valid_from=None)
        db = _make_db(auth)

        activate_authorization_for_envelope(db=db, envelope_id=ENVELOPE_ID, firm_id=FIRM_ID)

        assert auth.status == "active"
        assert auth.valid_from == date.today()
        db.commit.assert_called_once()

        mock_log_event.assert_called_once()
        call_kwargs = mock_log_event.call_args[1]
        assert call_kwargs["event_type"] == "irs_authorization.activated"
        assert call_kwargs["metadata"]["from_status"] == "pending_signature"
        assert call_kwargs["metadata"]["to_status"] == "active"

    @patch("app.services.irs_auth_service.log_event")
    def test_activation_noop_when_no_auth_linked(self, mock_log_event):
        db = _make_db(None)

        activate_authorization_for_envelope(db=db, envelope_id=ENVELOPE_ID, firm_id=FIRM_ID)

        mock_log_event.assert_not_called()
        db.commit.assert_not_called()

    @patch("app.services.irs_auth_service.log_event")
    def test_activation_noop_when_already_active(self, mock_log_event):
        auth = _make_auth(status="active")
        original_status = auth.status
        db = _make_db(auth)

        activate_authorization_for_envelope(db=db, envelope_id=ENVELOPE_ID, firm_id=FIRM_ID)

        assert auth.status == original_status
        mock_log_event.assert_not_called()
        db.commit.assert_not_called()

    @patch("app.services.irs_auth_service.log_event")
    def test_activation_preserves_existing_valid_from(self, mock_log_event):
        past_date = date(2025, 1, 15)
        auth = _make_auth(status="pending_signature", valid_from=past_date)
        db = _make_db(auth)

        activate_authorization_for_envelope(db=db, envelope_id=ENVELOPE_ID, firm_id=FIRM_ID)

        assert auth.valid_from == past_date
        assert auth.status == "active"
        mock_log_event.assert_called_once()
