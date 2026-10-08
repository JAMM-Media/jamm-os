# tests/test_seed_calendar_dev_events.py
"""
Tests for scripts/seed_calendar_dev_events.py: plan builder, guard,
no-network dry run, no-secret-leak, and cleanup pager.
"""
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
import requests

from scripts.seed_calendar_dev_events import (
    build_event_plan,
    CATEGORY_PLAN,
    check_local_api_url,
    main,
    plan_cleanup_pages,
)

NY = 'America/New_York'
KOL = 'Asia/Kolkata'


def _to_utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# build_event_plan: titles
# ---------------------------------------------------------------------------

def test_plan_four_events_with_dev_seed_prefix():
    plan = build_event_plan('2026-10-15', NY)
    assert len(plan) == 4
    for ev in plan:
        assert ev['title'].startswith('DEV SEED ')


# ---------------------------------------------------------------------------
# build_event_plan: UTC times for America/New_York 2026-10-15 (EDT, UTC-4)
# ---------------------------------------------------------------------------

def test_plan_ny_first_event_utc():
    # 09:00 EDT (UTC-4) => 13:00Z; 10:00 EDT => 14:00Z
    plan = build_event_plan('2026-10-15', NY)
    assert _to_utc(plan[0]['start_at']) == datetime(2026, 10, 15, 13, 0, tzinfo=timezone.utc)
    assert _to_utc(plan[0]['end_at'])   == datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)


def test_plan_ny_late_block_utc():
    # 22:30 EDT on Oct 15 (UTC-4) => Oct 16 02:30Z; 23:30 EDT => Oct 16 03:30Z
    plan = build_event_plan('2026-10-15', NY)
    assert _to_utc(plan[3]['start_at']) == datetime(2026, 10, 16, 2, 30, tzinfo=timezone.utc)
    assert _to_utc(plan[3]['end_at'])   == datetime(2026, 10, 16, 3, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# build_event_plan: UTC times for Asia/Kolkata (IST, UTC+5:30)
# ---------------------------------------------------------------------------

def test_plan_kolkata_first_event_utc():
    # 09:00 IST (UTC+5:30) => 03:30Z
    plan = build_event_plan('2026-10-15', KOL)
    assert _to_utc(plan[0]['start_at']) == datetime(2026, 10, 15, 3, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# build_event_plan: DST transition dates
# ---------------------------------------------------------------------------

def test_plan_fall_back_2026_11_01():
    # DST ends at 02:00 on 2026-11-01; 09:00 AM is EST (UTC-5) => 14:00Z
    plan = build_event_plan('2026-11-01', NY)
    assert _to_utc(plan[0]['start_at']) == datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc)


def test_plan_spring_forward_2026_03_08():
    # DST starts at 02:00 on 2026-03-08; 09:00 AM is EDT (UTC-4) => 13:00Z
    plan = build_event_plan('2026-03-08', NY)
    assert _to_utc(plan[0]['start_at']) == datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# build_event_plan: structural invariants
# ---------------------------------------------------------------------------

def test_plan_start_before_end_and_same_local_date():
    plan = build_event_plan('2026-10-15', NY)
    zone = ZoneInfo(NY)
    for ev in plan:
        start = datetime.fromisoformat(ev['start_at'])
        end   = datetime.fromisoformat(ev['end_at'])
        assert start < end
        assert start.astimezone(zone).date() == end.astimezone(zone).date()


def test_plan_events_1_and_2_overlap():
    # Event 1 is 09:00-10:00, event 2 is 09:30-10:30; they overlap
    plan = build_event_plan('2026-10-15', NY)
    ev1_end   = datetime.fromisoformat(plan[0]['end_at'])
    ev2_start = datetime.fromisoformat(plan[1]['start_at'])
    assert ev2_start < ev1_end


def test_plan_event_3_lasts_15_minutes():
    plan = build_event_plan('2026-10-15', NY)
    start = datetime.fromisoformat(plan[2]['start_at'])
    end   = datetime.fromisoformat(plan[2]['end_at'])
    assert end - start == timedelta(minutes=15)


def test_plan_category_keys_valid():
    plan = build_event_plan('2026-10-15', NY)
    valid = {'client_call', 'review', None}
    for ev in plan:
        assert ev['category_key'] in valid


def test_plan_owned_true_only_for_first():
    plan = build_event_plan('2026-10-15', NY)
    assert plan[0]['owned'] is True
    for ev in plan[1:]:
        assert ev['owned'] is False


# ---------------------------------------------------------------------------
# build_event_plan: error cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('bad', ['', '2026-10', '2026-13-01', '2026-10-15x'])
def test_plan_malformed_date_raises_value_error(bad):
    with pytest.raises(ValueError):
        build_event_plan(bad, NY)


def test_plan_invalid_zone_raises_zone_info_not_found_error():
    with pytest.raises(ZoneInfoNotFoundError):
        build_event_plan('2026-10-15', 'Not/AZone')


# ---------------------------------------------------------------------------
# CATEGORY_PLAN colors
# ---------------------------------------------------------------------------

def test_category_plan_colors_match_rrggbb():
    import re
    for key, cat in CATEGORY_PLAN.items():
        assert re.fullmatch(r'#[0-9A-Fa-f]{6}', cat['color']), f'{key}: {cat["color"]!r}'


# ---------------------------------------------------------------------------
# check_local_api_url: accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('url', [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost',
])
def test_guard_accepted(url):
    check_local_api_url(url)


# ---------------------------------------------------------------------------
# check_local_api_url: @ sign is refused before scheme/hostname checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('url', [
    'http://user@evil.com@localhost',
    'http://localhost@evil.com',
    'http://evil.com@localhost:8000',
])
def test_guard_refused_at_sign(url):
    # All URLs containing @ are refused regardless of how parsers resolve the host.
    # Report: requests.models.PreparedRequest().prepare_url('http://user@evil.com@localhost', None)
    # returns 'http://user%40evil.com@localhost/' (encodes the first @, resolves host=localhost).
    # Despite that, we refuse any URL with @ to eliminate the ambiguity class entirely.
    with pytest.raises(SystemExit) as exc_info:
        check_local_api_url(url)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# check_local_api_url: refused (scheme, hostname)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('url', [
    'https://localhost',
    'http://example.com',
    'http://localhost.evil.com',
    'http://127.0.0.1.evil.com',
    'http://10.0.0.5:8000',
    'http://0.0.0.0:8000',
    '',
    'localhost:8000',
])
def test_guard_refused(url):
    with pytest.raises(SystemExit) as exc_info:
        check_local_api_url(url)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# No network in dry run
# ---------------------------------------------------------------------------

def test_no_network_in_dry_run(monkeypatch, capsys):
    def _fail(*a, **kw):
        pytest.fail('HTTP call made during dry run')

    monkeypatch.setattr(requests, 'get',  _fail)
    monkeypatch.setattr(requests, 'post', _fail)
    monkeypatch.setenv('JAMM_DEV_API_URL', 'http://localhost:8000')
    monkeypatch.delenv('JAMM_DEV_EMAIL',    raising=False)
    monkeypatch.delenv('JAMM_DEV_PASSWORD', raising=False)
    monkeypatch.setattr(sys, 'argv', ['seed', '--date', '2026-10-15', '--tz', NY])

    main()

    out = capsys.readouterr().out
    assert 'DRY RUN: nothing was created' in out


# ---------------------------------------------------------------------------
# No secret leak
# ---------------------------------------------------------------------------

def test_no_secret_in_dry_run_output(monkeypatch, capsys):
    monkeypatch.setenv('JAMM_DEV_API_URL',  'http://localhost:8000')
    monkeypatch.setenv('JAMM_DEV_PASSWORD', 'PW-MARKER-12345')
    monkeypatch.delenv('JAMM_DEV_EMAIL', raising=False)
    monkeypatch.setattr(sys, 'argv', ['seed', '--date', '2026-10-15', '--tz', NY])

    main()

    captured = capsys.readouterr()
    assert 'PW-MARKER-12345' not in captured.out
    assert 'PW-MARKER-12345' not in captured.err


# ---------------------------------------------------------------------------
# plan_cleanup_pages
# ---------------------------------------------------------------------------

def _make_server(event_list):
    """Returns (fetch_page, delete_event, db) backed by a mutable list."""
    db = list(event_list)

    def fetch_page(offset):
        return db[offset:offset + 100]

    def delete_event(eid):
        db[:] = [e for e in db if e['id'] != eid]

    return fetch_page, delete_event, db


def test_cleanup_250_mixed_events_all_seed_deleted():
    # 250 events: 120 DEV SEED interleaved with 130 non-DEV SEED.
    # Interleaved: seed at even positions 0..238 (120), non-seed at odd 1..239 (120),
    # then 10 more non-seed at positions 240..249. Total = 250, seed = 120.
    events = []
    for i in range(120):
        events.append({'id': f'seed-{i}', 'title': f'DEV SEED item {i}'})
        events.append({'id': f'other-{i}', 'title': f'Normal item {i}'})
    for i in range(10):
        events.append({'id': f'extra-{i}', 'title': f'Extra item {i}'})
    assert len(events) == 250

    fetch_page, delete_event, db = _make_server(events)
    deleted = plan_cleanup_pages(fetch_page, delete_event)

    assert deleted == 120
    remaining_seed = [e for e in db if e['title'].startswith('DEV SEED ')]
    assert remaining_seed == []


def test_cleanup_seed_on_later_pages():
    # First page: 100 non-DEV SEED (offset advances to 100).
    # Second page: 10 DEV SEED (deleted, offset stays at 100, re-read gives empty).
    events = (
        [{'id': f'other-{i}', 'title': f'Normal {i}'} for i in range(100)]
        + [{'id': f'seed-{i}', 'title': f'DEV SEED item {i}'} for i in range(10)]
    )
    fetch_page, delete_event, db = _make_server(events)
    deleted = plan_cleanup_pages(fetch_page, delete_event)

    assert deleted == 10
    assert all('DEV SEED' not in e['title'] for e in db)


def test_cleanup_empty_server():
    fetch_page, delete_event, db = _make_server([])
    deleted_ids = []

    def track_delete(eid):
        deleted_ids.append(eid)
        delete_event(eid)

    deleted = plan_cleanup_pages(fetch_page, track_delete)
    assert deleted == 0
    assert deleted_ids == []


def test_cleanup_safety_valve_prints_warning(capsys):
    # fetch_page always returns a DEV SEED item; delete_event is a no-op.
    # The page never empties so the 200-iteration valve must fire.
    page = [{'id': 'seed-1', 'title': 'DEV SEED item'}]

    def fetch_page(offset):
        return page

    def delete_event(eid):
        pass  # server never removes the item

    deleted = plan_cleanup_pages(fetch_page, delete_event)

    out = capsys.readouterr().out
    assert 'WARNING' in out
    assert '200' in out
