# tests/test_log_event_threading.py

import os
import threading
import time
import uuid
from unittest.mock import MagicMock, patch

from app.services.behavioral_log import log_event
from app.core.request_context import set_request_id, set_session_id


def test_context_resolved_before_thread():
    ctx_request_id = str(uuid.uuid4())
    ctx_session_id = str(uuid.uuid4())
    set_request_id(ctx_request_id)
    set_session_id(ctx_session_id)

    captured = {}
    done = threading.Event()

    def fake_add(event):
        captured["event"] = event
        done.set()

    mock_db = MagicMock()
    mock_db.add.side_effect = fake_add

    with patch("app.services.behavioral_log.SessionLocal", return_value=mock_db):
        log_event(
            event_type="document.viewed",
            firm_id=uuid.uuid4(),
        )

    assert done.wait(1.0)

    event = captured["event"]
    assert str(event.session_id) == ctx_session_id
    assert str(event.request_id) == ctx_request_id

    set_request_id(None)
    set_session_id(None)


def test_log_event_returns_immediately():
    """
    Fire-and-forget is a production-only behavior: under JAMM_TESTING=1,
    behavioral_log.log_event runs _write synchronously so tests can assert
    on the written row without a race. Force the production (threaded)
    path here to verify the non-blocking contract it actually protects.
    """
    release = threading.Event()

    def fake_session_local():
        release.wait(2.0)
        raise RuntimeError("stop before touching the db further")

    previous = os.environ.pop("JAMM_TESTING", None)
    try:
        with patch("app.services.behavioral_log.SessionLocal", side_effect=fake_session_local):
            start = time.monotonic()
            log_event(
                event_type="document.viewed",
                firm_id=uuid.uuid4(),
            )
            elapsed = time.monotonic() - start

        assert elapsed < 0.5
    finally:
        if previous is not None:
            os.environ["JAMM_TESTING"] = previous
        release.set()


def test_thread_failure_does_not_raise():
    done = threading.Event()

    def fake_session_local():
        done.set()
        raise RuntimeError("boom")

    with patch("app.services.behavioral_log.SessionLocal", side_effect=fake_session_local), \
         patch("app.services.behavioral_log.log.warning") as mock_warning:
        log_event(
            event_type="document.viewed",
            firm_id=uuid.uuid4(),
        )

    assert done.wait(1.0)
    time.sleep(0.1)
    assert mock_warning.called


def test_explicit_ids_still_win():
    ctx_request_id = str(uuid.uuid4())
    ctx_session_id = str(uuid.uuid4())
    set_request_id(ctx_request_id)
    set_session_id(ctx_session_id)

    explicit_session_id = uuid.uuid4()
    explicit_request_id = uuid.uuid4()

    captured = {}
    done = threading.Event()

    def fake_add(event):
        captured["event"] = event
        done.set()

    mock_db = MagicMock()
    mock_db.add.side_effect = fake_add

    with patch("app.services.behavioral_log.SessionLocal", return_value=mock_db):
        log_event(
            event_type="document.viewed",
            firm_id=uuid.uuid4(),
            session_id=explicit_session_id,
            request_id=explicit_request_id,
        )

    assert done.wait(1.0)

    event = captured["event"]
    assert event.session_id == explicit_session_id
    assert event.request_id == explicit_request_id

    set_request_id(None)
    set_session_id(None)
