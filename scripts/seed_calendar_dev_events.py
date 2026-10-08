# path: scripts/seed_calendar_dev_events.py
"""
Developer seed script: creates sample native calendar events through the local API.
Dry run by default. Pass --apply to create. Pass --cleanup to soft delete all DEV SEED items.
Never use against a non-local backend. Requires JAMM_DEV_API_URL (all modes) plus
JAMM_DEV_EMAIL and JAMM_DEV_PASSWORD for --apply and --cleanup only.
"""
import argparse
import os
import sys
import urllib.parse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_PLAN = {
    'client_call': {'name': 'DEV SEED Client call', 'color': '#3F6E9A'},
    'review':      {'name': 'DEV SEED Review',       'color': '#B07D3A'},
}

_DEV_SEED_PREFIX = 'DEV SEED '

# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

def check_local_api_url(url: str) -> None:
    """Exits 1 unless url is a plain http://localhost/... or http://127.0.0.1/..."""
    if not url:
        print('Error: JAMM_DEV_API_URL is empty or missing')
        raise SystemExit(1)
    if '@' in url:
        print(f'Error: JAMM_DEV_API_URL must not contain @, got {url!r}')
        raise SystemExit(1)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'http':
        print(f'Error: JAMM_DEV_API_URL scheme must be http, got {parsed.scheme!r}')
        raise SystemExit(1)
    if parsed.hostname not in ('localhost', '127.0.0.1'):
        print(f'Error: JAMM_DEV_API_URL hostname must be localhost or 127.0.0.1, got {parsed.hostname!r}')
        raise SystemExit(1)

# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------

def build_event_plan(date_str: str, timezone_name: str) -> list:
    """
    Returns four sample event dicts for date_str in the given IANA zone.
    Keys: title, start_at, end_at, category_key, owned.
    Raises ValueError for a malformed date_str; lets ZoneInfoNotFoundError propagate.
    """
    d = date.fromisoformat(date_str)
    zone = ZoneInfo(timezone_name)

    def _iso(hour: int, minute: int = 0) -> str:
        dt = datetime(d.year, d.month, d.day, hour, minute, tzinfo=zone)
        return dt.isoformat()

    return [
        {
            'title':        'DEV SEED Client call',
            'start_at':     _iso(9, 0),
            'end_at':       _iso(10, 0),
            'category_key': 'client_call',
            'owned':        True,
        },
        {
            'title':        'DEV SEED Review session',
            'start_at':     _iso(9, 30),
            'end_at':       _iso(10, 30),
            'category_key': 'review',
            'owned':        False,
        },
        {
            'title':        'DEV SEED Quick check',
            'start_at':     _iso(13, 0),
            'end_at':       _iso(13, 15),
            'category_key': None,
            'owned':        False,
        },
        {
            'title':        'DEV SEED Late block',
            'start_at':     _iso(22, 30),
            'end_at':       _iso(23, 30),
            'category_key': 'review',
            'owned':        False,
        },
    ]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_check(response, context: str = '') -> None:
    if not response.ok:
        try:
            detail = response.json().get('detail', response.text[:300])
        except Exception:
            detail = response.text[:300]
        label = f' ({context})' if context else ''
        print(f'HTTP {response.status_code}{label}: {detail}')
        sys.exit(1)


def _login(base_url: str, email: str, password: str) -> str:
    r = requests.post(f'{base_url}/auth/token', json={'username': email, 'password': password})
    if not r.ok:
        print(f'Login failed: HTTP {r.status_code}')
        sys.exit(1)
    return r.json()['access_token']


def _auth_headers(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}

# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------

def _get_or_create_categories(base_url: str, headers: dict) -> dict:
    r = requests.get(
        f'{base_url}/api/v1/calendar/categories',
        params={'include_inactive': 'true', 'limit': 100},
        headers=headers,
    )
    _http_check(r, 'list categories')
    existing = {item['name'].lower(): item for item in r.json().get('items', [])}
    result = {}
    for key, plan in CATEGORY_PLAN.items():
        name_lower = plan['name'].lower()
        if name_lower in existing:
            cat = existing[name_lower]
            if not cat.get('is_active', True):
                print(f"  WARNING: category {plan['name']!r} is inactive; events for key {key!r} will have no category")
                result[key] = None
            else:
                print(f"  reused category {plan['name']!r} id={cat['id']}")
                result[key] = cat['id']
        else:
            rc = requests.post(
                f'{base_url}/api/v1/calendar/categories',
                json={'name': plan['name'], 'color': plan['color']},
                headers=headers,
            )
            _http_check(rc, f"create category {plan['name']}")
            cat_id = rc.json()['id']
            print(f"  created category {plan['name']!r} id={cat_id}")
            result[key] = cat_id
    return result


def _list_events_for_date(base_url: str, headers: dict, date_str: str, firm_tz: str) -> list:
    d = date.fromisoformat(date_str)
    d_next = d + timedelta(days=1)
    zone = ZoneInfo(firm_tz)
    from_dt = datetime(d.year, d.month, d.day, 0, 0, tzinfo=zone).isoformat()
    to_dt = datetime(d_next.year, d_next.month, d_next.day, 0, 0, tzinfo=zone).isoformat()
    r = requests.get(
        f'{base_url}/api/v1/calendar/events',
        params={'from': from_dt, 'to': to_dt, 'limit': 100},
        headers=headers,
    )
    _http_check(r, 'list events for date')
    return r.json().get('items', [])

# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------

def plan_cleanup_pages(fetch_page, delete_event) -> int:
    """
    Pages through events via fetch_page(offset) -> list[{id, title, ...}].
    Deletes any event whose title starts with _DEV_SEED_PREFIX via delete_event(id).
    Re-reads the same offset after any deletion so server-side shifts are caught.
    Advances offset by 100 only when a page contained no DEV SEED events to delete.
    Stops on an empty page or after 200 iterations (safety valve).
    Returns the count of deleted events.
    """
    offset = 0
    deleted = 0
    for _ in range(200):
        items = fetch_page(offset)
        if not items:
            break
        had_seed = False
        for ev in items:
            if ev['title'].startswith(_DEV_SEED_PREFIX):
                delete_event(ev['id'])
                deleted += 1
                had_seed = True
        if not had_seed:
            offset += 100
    else:
        print('WARNING: cleanup safety valve reached 200 iterations; some events may not have been deleted')
    return deleted

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_url = os.environ.get('JAMM_DEV_API_URL', '')
    if not api_url:
        print('Error: JAMM_DEV_API_URL environment variable is not set')
        sys.exit(1)
    check_local_api_url(api_url)

    parser = argparse.ArgumentParser(
        description='Seed sample native calendar events into a local dev backend.'
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--apply', action='store_true', help='Create events and categories via the API.')
    mode_group.add_argument('--cleanup', action='store_true', help='Soft delete all DEV SEED events and deactivate categories.')
    parser.add_argument('--date', metavar='YYYY-MM-DD', help='Firm-zone date to place events on.')
    parser.add_argument('--tz', metavar='IANA_ZONE', help='IANA zone for dry run (default: America/New_York).')
    args = parser.parse_args()

    is_dry_run = not args.apply and not args.cleanup

    if is_dry_run:
        tz_name = args.tz if args.tz else 'America/New_York'
        tz_reason = 'from --tz' if args.tz else 'default (no login in dry run)'
        print(f'Zone: {tz_name} ({tz_reason})')
        if args.date:
            date_str = args.date
        else:
            date_str = (date.today() + timedelta(days=1)).isoformat()
        print(f'Guard passed: {api_url!r} is local')
        plan = build_event_plan(date_str, tz_name)
        print(f'Plan for {date_str} in {tz_name}:')
        for ev in plan:
            cat_name = CATEGORY_PLAN[ev['category_key']]['name'] if ev['category_key'] else 'none'
            print(f"  {ev['title']!r}  {ev['start_at']}  {ev['end_at']}  category={cat_name}  owned={ev['owned']}")
        print('DRY RUN: nothing was created')
        return

    email = os.environ.get('JAMM_DEV_EMAIL', '')
    password = os.environ.get('JAMM_DEV_PASSWORD', '')
    if not email or not password:
        print('Error: JAMM_DEV_EMAIL and JAMM_DEV_PASSWORD are required for --apply and --cleanup')
        sys.exit(1)

    token = _login(api_url, email, password)
    headers = _auth_headers(token)

    r_firm = requests.get(f'{api_url}/users/firm', headers=headers)
    _http_check(r_firm, 'get firm')
    firm_tz = r_firm.json().get('timezone')
    if not firm_tz:
        print('Error: the firm has no timezone set; set it in Settings first')
        sys.exit(1)

    r_me = requests.get(f'{api_url}/users/me', headers=headers)
    _http_check(r_me, 'get current user')
    my_user_id = r_me.json()['id']

    if args.apply:
        if args.date:
            date_str = args.date
        else:
            zone = ZoneInfo(firm_tz)
            date_str = (datetime.now(zone).date() + timedelta(days=1)).isoformat()
        plan = build_event_plan(date_str, firm_tz)
        cat_ids = _get_or_create_categories(api_url, headers)
        existing_events = _list_events_for_date(api_url, headers, date_str, firm_tz)
        existing_titles = {ev['title'] for ev in existing_events}
        created = 0
        skipped = 0
        for ev in plan:
            if ev['title'] in existing_titles:
                print(f"  skipped (already exists): {ev['title']!r}")
                skipped += 1
                continue
            payload = {
                'title':    ev['title'],
                'start_at': ev['start_at'],
                'end_at':   ev['end_at'],
            }
            if ev['category_key'] and cat_ids.get(ev['category_key']):
                payload['category_id'] = cat_ids[ev['category_key']]
            if ev['owned']:
                payload['owner_user_id'] = my_user_id
            rc = requests.post(f'{api_url}/api/v1/calendar/events', json=payload, headers=headers)
            _http_check(rc, f"create event {ev['title']!r}")
            print(f"  created: {ev['title']!r} id={rc.json()['id']}")
            created += 1
        print(f'APPLIED: created={created} skipped={skipped}')

    elif args.cleanup:
        zone = ZoneInfo(firm_tz)
        today = datetime.now(zone).date()
        d_from = today - timedelta(days=7)
        d_to = today + timedelta(days=60)
        from_dt = datetime(d_from.year, d_from.month, d_from.day, 0, 0, tzinfo=zone).isoformat()
        to_dt = datetime(d_to.year, d_to.month, d_to.day, 0, 0, tzinfo=zone).isoformat()

        def _fetch_page(off: int) -> list:
            r = requests.get(
                f'{api_url}/api/v1/calendar/events',
                params={'from': from_dt, 'to': to_dt, 'limit': 100, 'offset': off},
                headers=headers,
            )
            _http_check(r, 'list events for cleanup')
            return r.json().get('items', [])

        def _delete_event(eid: str) -> None:
            rd = requests.delete(f'{api_url}/api/v1/calendar/events/{eid}', headers=headers)
            _http_check(rd, f'delete event {eid}')
            print(f'  deleted event id={eid}')

        events_deleted = plan_cleanup_pages(_fetch_page, _delete_event)

        r_cats = requests.get(
            f'{api_url}/api/v1/calendar/categories',
            params={'include_inactive': 'true', 'limit': 100},
            headers=headers,
        )
        _http_check(r_cats, 'list categories for cleanup')
        cats_deactivated = 0
        for cat in r_cats.json().get('items', []):
            if cat['name'].startswith(_DEV_SEED_PREFIX) and cat.get('is_active', False):
                rp = requests.patch(
                    f"{api_url}/api/v1/calendar/categories/{cat['id']}",
                    json={'is_active': False},
                    headers=headers,
                )
                _http_check(rp, f"deactivate category {cat['id']}")
                print(f"  deactivated category: {cat['name']!r} id={cat['id']}")
                cats_deactivated += 1
        print(f'CLEANED: events_deleted={events_deleted} cats_deactivated={cats_deactivated}')


if __name__ == '__main__':
    main()
