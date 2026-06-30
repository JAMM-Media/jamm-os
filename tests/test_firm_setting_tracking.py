# tests/test_firm_setting_tracking.py

import uuid
from unittest.mock import MagicMock, patch

import app.services.behavioral_log as behavioral_log


def test_scalar_change_fires_event():
    firm_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    with patch("app.services.behavioral_log.log_event") as mock_log:
        behavioral_log.log_setting_changes(
            firm_id=firm_id,
            actor_id=actor_id,
            old_values={"session_timeout_minutes": 30},
            new_values={"session_timeout_minutes": 60},
        )

    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs["event_type"] == "firm.setting_changed"
    assert kwargs["metadata"]["setting_key"] == "session_timeout_minutes"
    assert kwargs["metadata"]["from_value"] == 30
    assert kwargs["metadata"]["to_value"] == 60


def test_unchanged_key_fires_nothing():
    with patch("app.services.behavioral_log.log_event") as mock_log:
        behavioral_log.log_setting_changes(
            firm_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            old_values={"x": 5},
            new_values={"x": 5},
        )

    mock_log.assert_not_called()


def test_multiple_changes_fire_multiple_events():
    with patch("app.services.behavioral_log.log_event") as mock_log:
        behavioral_log.log_setting_changes(
            firm_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            old_values={"a": 1, "b": 2},
            new_values={"a": 9, "b": 2},
        )

    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs["metadata"]["setting_key"] == "a"
    assert kwargs["metadata"]["from_value"] == 1
    assert kwargs["metadata"]["to_value"] == 9


def test_complex_value_not_dumped():
    with patch("app.services.behavioral_log.log_event") as mock_log:
        behavioral_log.log_setting_changes(
            firm_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            old_values={"fee_schedule": {"1040": 100}},
            new_values={"fee_schedule": {"1040": 200}},
        )

    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs["metadata"]["setting_key"] == "fee_schedule"
    assert kwargs["metadata"]["to_value"] == {"_type": "dict", "_changed": True}


def test_new_key_added_fires_event():
    with patch("app.services.behavioral_log.log_event") as mock_log:
        behavioral_log.log_setting_changes(
            firm_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            old_values={},
            new_values={"new_flag": True},
        )

    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs["metadata"]["setting_key"] == "new_flag"
    assert kwargs["metadata"]["from_value"] is None
    assert kwargs["metadata"]["to_value"] is True
