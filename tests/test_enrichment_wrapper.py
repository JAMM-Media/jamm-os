# tests/test_enrichment_wrapper.py

import uuid
import unittest
from unittest.mock import MagicMock, patch

from app.core.request_context import set_request_id, set_session_id
from app.services.behavioral_log import log_event

FIRM_ID = uuid.uuid4()


def _captured_event(mock_db_cls):
    """Return the BehavioralEvent passed to db.add in the most recent call."""
    instance = mock_db_cls.return_value.__enter__.return_value if hasattr(
        mock_db_cls.return_value, '__enter__'
    ) else mock_db_cls.return_value
    calls = instance.add.call_args_list
    assert calls, "db.add was never called"
    return calls[-1].args[0]


class TestEnrichmentWrapper(unittest.TestCase):

    def setUp(self):
        # Clear context vars before every test
        set_session_id(None)
        set_request_id(None)

    def tearDown(self):
        set_session_id(None)
        set_request_id(None)

    @patch("app.services.behavioral_log.SessionLocal")
    def test_explicit_ids_win_over_context(self, mock_session_cls):
        # Context holds value A
        context_session = str(uuid.uuid4())
        context_request = str(uuid.uuid4())
        set_session_id(context_session)
        set_request_id(context_request)

        # Caller passes value B (different UUIDs)
        explicit_session = uuid.uuid4()
        explicit_request = uuid.uuid4()

        assert explicit_session != uuid.UUID(context_session)
        assert explicit_request != uuid.UUID(context_request)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        log_event(
            event_type="test.event",
            firm_id=FIRM_ID,
            session_id=explicit_session,
            request_id=explicit_request,
        )

        event = mock_db.add.call_args[0][0]
        self.assertEqual(event.session_id, explicit_session)
        self.assertEqual(event.request_id, explicit_request)

    @patch("app.services.behavioral_log.SessionLocal")
    def test_context_ids_used_when_not_passed(self, mock_session_cls):
        ctx_session = str(uuid.uuid4())
        ctx_request = str(uuid.uuid4())
        set_session_id(ctx_session)
        set_request_id(ctx_request)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        log_event(event_type="test.event", firm_id=FIRM_ID)

        event = mock_db.add.call_args[0][0]
        self.assertEqual(event.session_id, uuid.UUID(ctx_session))
        self.assertEqual(event.request_id, uuid.UUID(ctx_request))

    @patch("app.services.behavioral_log.SessionLocal")
    def test_no_context_yields_none(self, mock_session_cls):
        # Context already cleared in setUp
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        log_event(event_type="test.event", firm_id=FIRM_ID)

        event = mock_db.add.call_args[0][0]
        self.assertIsNone(event.session_id)
        self.assertIsNone(event.request_id)

    @patch("app.services.behavioral_log.SessionLocal")
    def test_malformed_context_id_dropped_not_fatal(self, mock_session_cls):
        set_session_id("not-a-uuid")
        set_request_id(None)

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        # Must not raise
        log_event(event_type="test.event", firm_id=FIRM_ID)

        event = mock_db.add.call_args[0][0]
        self.assertIsNone(event.session_id)

    @patch("app.services.behavioral_log.SessionLocal")
    def test_fire_and_forget_still_swallows_errors(self, mock_session_cls):
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("DB exploded")
        mock_session_cls.return_value = mock_db

        # Must not raise -- fire-and-forget
        log_event(event_type="test.event", firm_id=FIRM_ID)
