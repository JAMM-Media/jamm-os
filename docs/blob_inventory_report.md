# blob_inventory_report.md

# Settings Blob Inventory (READ ONLY)

Session: precursor to the settings blob backfill build.
Date: August 14, 2026.
Scope: inventory only. Nothing in `app/`, `migrations/`, or `tests/` was created, modified, or deleted. No migrations generated or applied. No database writes. No git commits.

---

## 1. Baseline diagnostics results

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| `pytest` | 856 passed, 2 skipped, 1 environmental failure, exit 1 | `1 failed, 856 passed, 2 skipped, 51 warnings in 1090.30s`, exit 1 | PASS |
| `alembic current` | `de2c76e703db` (mergepoint) | `de2c76e703db (head) (mergepoint)` | PASS |
| Effective `DATABASE_URL` | local dev | `postgresql+psycopg://postgres:***@localhost:5432/accounting_dev` | PASS |

The single failure is the expected Windows-only environmental one:

```
FAILED tests/test_sequence_version_pinning.py::TestNoCodePathModifiesVersionPin::
       test_no_code_path_currently_modifies_enrollment_sequence_version_id
```

Its cause was confirmed empirically rather than assumed. The traceback bottoms out in
`subprocess.py:1554` at `_winapi.CreateProcess` with
`FileNotFoundError: [WinError 2] The system cannot find the file specified`, which is the
`grep` shell-out that does not exist on Windows. No other test failed. Exit code 1 is
attributable solely to this test.

Environment notes:

- `alembic` and `pytest` are not on `PATH` as bare commands in this shell. Both were invoked via `python -m`.
- The OS environment variable `DATABASE_URL` is **not set**, so there is no stale shell export overriding `.env` through pydantic settings.
- Direct reads of `.env` are blocked by this session's permission settings. The effective URL was obtained through `app.core.config.get_settings()`, which is the same resolution path the application itself uses.
- The host check was re-run inside the query script immediately before the first SELECT, with a hard abort on any non-local host. It printed `localhost` and proceeded.

---

## 2. Classified code inventory

Column under inventory: `app/models/firm.py:54`

```python
settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
```

Created by `migrations/versions/0005_phase1_multitenancy.py:46`. Live column type confirmed as `json` in the dev database.

### 2a. Writers

| # | File :: function | R/W | Settings keys touched | Classification |
|---|---|---|---|---|
| 1 | `app/api/users.py:105` :: `update_my_firm_settings` (PATCH `/users/firm/settings`) | WRITER | **Arbitrary.** Body is an untyped `payload: dict` with no key whitelist | FEE RELATED and NON FEE |
| 2 | `app/services/user_service.py:15` :: `update_firm_settings` | READER and WRITER | Arbitrary merge. Explicitly special-cases `fee_schedule`; reads `portal_logo_s3_key` for S3 cleanup | FEE RELATED and NON FEE |
| 3 | `app/api/settings.py:34` :: `update_review_settings` | READER and WRITER | `google_review_url` | NON FEE |
| 4 | `app/api/settings.py:60` :: `update_email_calendar_sync` | READER and WRITER | `email_sync_enabled`, `calendar_sync_enabled`, `staff_can_disable_email_sync`, `staff_can_disable_calendar_sync` | NON FEE |
| 5 | `app/api/settings.py:83` :: `update_email_settings` | READER and WRITER | `email_reply_to`, `email_display_name` | NON FEE |
| 6 | `app/services/review_request_service.py:109` :: `record_nps_score` | READER and WRITER | Reads `google_review_url`, writes `last_nps_score` | NON FEE |
| 7 | `scripts/seed_additions.py:67` :: STEP 2 | READER and WRITER | `fee_schedule` (16 sub-keys) | **FEE RELATED** |
| 8 | `app/api/firms.py:61` :: `update_my_firm` (PATCH `/firms/me`) | WRITER | Arbitrary, **wholesale replace** via `FirmUpdate.settings` | FEE RELATED and NON FEE |
| 9 | `app/api/firms.py:246` :: `update_firm` (PATCH `/firms/{firm_id}`, system_admin) | WRITER | Arbitrary, **wholesale replace** via `FirmUpdate.settings` | FEE RELATED and NON FEE |
| 10 | `app/crud/firm.py:34` :: `update_firm` | WRITER (mechanism) | `setattr` over `model_dump(exclude_unset=True)`; the assignment path for 8 and 9 | n/a |

### 2b. Readers

| # | File :: function | Settings keys touched | Classification |
|---|---|---|---|
| 11 | `app/api/users.py:72` :: `read_users_me` | `concierge_entry_mode`, `concierge_suggestions_enabled` | NON FEE |
| 12 | `app/services/email_service.py:89` :: `EmailService.get_firm_email_settings` | `email_reply_to`, `email_display_name` | NON FEE |
| 13 | `app/services/auth_service.py:105,122,158` :: login | `password_policy.max_failed_attempts`, `session_timeout_minutes` | NON FEE |
| 14 | `app/services/password_reset_service.py:104` | `password_policy` (whole sub-object, passed to `validate_password_policy`) | NON FEE |
| 15 | `app/api/portal.py:535` :: `portal_me` | `portal_logo_s3_key`, `portal_mode`, `portal_colors_light`, `portal_colors_dark`, `portal_display_name` | NON FEE |
| 16 | `app/api/firms.py:205` :: `get_firm_logo` | `portal_logo_s3_key` | NON FEE |
| 17 | `app/api/reports.py:228` :: `get_billing_detail` | `portal_logo_s3_key` only | NON FEE |
| 18 | `app/services/invoice_renderer.py:181` :: `render_invoice_to_pdf` | `portal_logo_s3_key` | NON FEE |
| 19 | `app/services/irs_auth_service.py:203` :: `generate_auth_stub_pdf` | `portal_logo_s3_key` | NON FEE |
| 20 | `app/services/letter_renderer.py:62` :: `render_to_pdf` | `portal_logo_s3_key`; receives the whole blob as a `firm_settings` parameter | NON FEE |
| 21 | `app/services/esign_service.py:61,102` | `firm_address`, `firm_phone`, `firm_contact_email`, `firm_website`; passes whole blob to the renderer | NON FEE |
| 22 | `app/api/esign.py:624-642` :: template preview | `firm_address`, `firm_phone`, `firm_contact_email`, `firm_website`; passes whole blob | NON FEE |
| 23 | `app/api/esign.py:250` :: send reminder | `esign_second_reminder_days` | NON FEE |
| 24 | `app/api/dashboard.py:232` :: `_get_unsigned_documents_section` | `esign_first_reminder_days`, `esign_second_reminder_days`, `esign_escalation_days` | NON FEE |
| 25 | `app/services/esign_reminder_service.py:41,117` | `esign_first_reminder_days`, `esign_escalation_days` | NON FEE |
| 26 | `app/api/concierge/functions.py:1210` :: `get_firm_settings` | **Wildcard.** Every key whose lowercased name contains `notif`, `email`, or `reminder` | UNKNOWN (dynamic, cannot be statically enumerated) |

### 2c. Distinct keys named anywhere in code

`fee_schedule`, `google_review_url`, `email_sync_enabled`, `calendar_sync_enabled`,
`staff_can_disable_email_sync`, `staff_can_disable_calendar_sync`, `email_reply_to`,
`email_display_name`, `last_nps_score`, `concierge_entry_mode`,
`concierge_suggestions_enabled`, `password_policy`, `session_timeout_minutes`,
`portal_logo_s3_key`, `portal_mode`, `portal_colors_light`, `portal_colors_dark`,
`portal_display_name`, `firm_address`, `firm_phone`, `firm_contact_email`,
`firm_website`, `esign_first_reminder_days`, `esign_second_reminder_days`,
`esign_escalation_days`.

That is 25 named keys. **Exactly one is FEE RELATED: `fee_schedule`.**

### 2d. Reference points requested for verification

Both confirmed empirically, both accurate as described.

- `EmailService.get_firm_email_settings` (`app/services/email_service.py:89`) reads `email_reply_to` and `email_display_name` from the blob. Note that the third key it returns, `sending_domain`, is **not** from the blob: it comes from the real columns `firm.sending_domain` and `firm.sending_domain_verified`.
- The login flow (`app/services/auth_service.py`) reads `session_timeout_minutes` at line 158 and `password_policy.max_failed_attempts` at line 106. Staff auth policy is **not** in the blob: `staff_auth_policy` is a real column on `Firm`, written by `app/api/settings.py:29` directly.

### 2e. False positive excluded after inspection

`app/api/calendar.py` matches a naive `.settings` grep at lines 86, 108, 109, 130, 132, 138, 139 but does **not** touch the firm settings blob. It uses two separate columns: `User.calendar_settings` and `Firm.staff_calendar_colors`. Excluded from the inventory.

### 2f. Test coverage of the blob

`tests/` contains **zero** direct reads or writes of `Firm.settings`. Every `settings` token in the test tree is either the app config singleton (`from app.core.config import get_settings`) or a URL path string such as `/settings/security/staff-auth-policy`. The only coverage is indirect, through endpoint calls.

`tests/test_firm_setting_tracking.py` mentions `fee_schedule`, but only as literal argument data passed to `log_setting_changes`; it does not read or write the blob.

---

## 3. Distinct key census with row counts

Queried against `localhost:5432/accounting_dev`, SELECT only.

| Metric | Value |
|---|---|
| Total rows in `firms` | **4** |
| Rows where `settings IS NULL` | 0 |
| Rows where `settings = {}` | **4** |
| **Distinct top-level keys across all rows** | **0** |

Per-row detail:

| firm id | name | created_at | raw `settings::text` |
|---|---|---|---|
| `43a59446-bc57-469f-8970-578ecaa0f71b` | Auth Test Firm | 2026-05-02 02:54:59-04 | `{}` |
| `d27767e4-5ffd-460a-829f-27ba48de59d1` | Auth Test Firm | 2026-05-02 02:55:00-04 | `{}` |
| `20509bb1-8f5d-41bb-a64f-44f732d57ad6` | Auth Test Firm | 2026-05-02 02:55:02-04 | `{}` |
| `0fc25bb9-6741-41e7-937e-2e83d2f23d76` | POC Demo Firm aa83feea-deb1-45bc-9b3f-23545bb5882a | 2026-07-19 15:09:28-04 | `{}` |

The census is empty. Every one of the 25 keys named in code is absent from all data.

This was confirmed twice by different means, because an all-empty result is exactly the kind of finding that deserves distrust before acceptance:

1. Through the ORM, decoding the JSON column into Python dicts.
2. Through raw SQL casting the column to text (`SELECT settings::text FROM firms`), bypassing ORM and JSON decoding entirely. All four rows return the literal two-character string `'{}'`.

Surrounding table counts, to characterise the database rather than just the column:

| table | rows |
|---|---|
| `firms` | 4 |
| `users` | 3 |
| `clients` | 2 |
| `engagements` | 1 |
| `engagement_letter_templates` | 0 |
| `invoices` | 0 |
| `service_catalog_entries` | 0 |

---

## 4. Fee related and unknown key sample dumps with shape notes

**No samples can be dumped. There is no blob data in the local dev database.**

`fee_schedule` is present on 0 of 4 rows. The same is true of every other key, so there is nothing to sample for the UNKNOWN (Concierge wildcard) category either.

The requirement in the session brief, that the backfill's null-versus-zero handling be grounded in knowing exactly which value shapes appear in real data, **cannot be satisfied from this database.** What follows is the only fee-shape evidence available, and it comes from **code, not from data**. It is recorded here as such and must not be mistaken for a data observation.

`scripts/seed_additions.py:69-86` is the sole writer of `fee_schedule` with literal content. Its shape:

- `fee_schedule` is a **nested object** (a flat, single-level dict) at the top level.
- 16 sub-keys: `tax_return_1040`, `tax_return_1120`, `tax_return_1120s`, `tax_return_1065`, `tax_return_1041`, `tax_return_706`, `amended_return_1040x`, `extension_4868`, `extension_7004`, `extension_8868`, `bookkeeping_monthly`, `bookkeeping_quarterly`, `payroll_tax_941`, `tax_planning_advisory`, `audit_representation`, `custom`.
- **Every monetary value is a JSON string, not a number.** `"850"`, `"2400"`, `"1800"`, `"1600"`, `"1200"`, `"3500"`, `"400"`, `"150"`, `"150"`, `"150"`, `"600"`, `"750"`, `"350"`, `"300"`, `"2500"`.
- They are **bare integer strings**: no decimal point, no currency symbol, no thousands separator.
- **One value is the empty string:** `"custom": ""`. This is the ambiguous-legacy-value case. Under the locked ruling it becomes NULL and routes to quote, and must not be coerced to zero.
- No `null` and no float appears anywhere in the seed literal.

Two further constraints on shape come from code rather than from the seed:

- `app/services/user_service.py:64` compares fee values with `str(...)` on both sides when computing `changed_types`. That normalisation means a value written as the number `850` and a value written as the string `"850"` are treated as equal by the change detector, so **numeric fee values are not excluded by anything in the write path.**
- The write endpoints impose no schema on fee values at all. `PATCH /users/firm/settings` accepts an untyped `dict`, and `PATCH /firms/me` and `PATCH /firms/{firm_id}` accept `FirmUpdate.settings: Optional[dict]`. Any JSON type can therefore have been written into any fee sub-key by any of the three, including `null`, floats, and nested objects.

The practical consequence is that the set of shapes actually present in production is **unknown and not bounded by anything in the repository.** It cannot be inferred from the seed script, because the seed script is not the only writer.

---

## 5. Orphaned keys found in data but not in code

**None.** This result is vacuous rather than reassuring: there are zero keys in the data at all, so the orphan check had nothing to examine. It is not evidence that orphaned keys do not exist in real firm data. It is only evidence that this database is empty.

The inverse check is the one with content. All 25 keys named in code are **absent** from every row:

`calendar_sync_enabled`, `concierge_entry_mode`, `concierge_suggestions_enabled`,
`email_display_name`, `email_reply_to`, `email_sync_enabled`, `esign_escalation_days`,
`esign_first_reminder_days`, `esign_second_reminder_days`, `fee_schedule`, `firm_address`,
`firm_contact_email`, `firm_phone`, `firm_website`, `google_review_url`, `last_nps_score`,
`password_policy`, `portal_colors_dark`, `portal_colors_light`, `portal_display_name`,
`portal_logo_s3_key`, `portal_mode`, `session_timeout_minutes`,
`staff_can_disable_calendar_sync`, `staff_can_disable_email_sync`.

Note that the Concierge wildcard reader at `app/api/concierge/functions.py:1221` matches on substrings `notif`, `email`, and `reminder`. Any orphaned key in real data containing one of those substrings is a **live read** today, surfaced to the Concierge, despite appearing nowhere in code as a named key. Such keys cannot be discovered by static search. They can only be found in data, which means they cannot be found here.

---

## 6. Surprising or ambiguous, stated plainly

1. **The local dev database contains no settings blob data whatsoever.** All 4 firms carry `{}`. The stated purpose of this session, producing a verified inventory of what is actually in the blob, cannot be completed from this database. Sections 3, 4, and 5 are empty for that reason and not for lack of looking.

2. **The dev database is not a representative dataset.** 4 firms, 3 users, 2 clients, 1 engagement, 0 engagement letter templates, 0 invoices, 0 service catalog entries. Three of the four firms are named "Auth Test Firm" and were created within three seconds of each other on May 2, 2026. The fourth is "POC Demo Firm" with a UUID suffix, from July 19, 2026. These are leftover scratch rows, not seeded dev data.

3. **`scripts/seed_additions.py` has evidently never been run against this database.** It is the only code that writes a populated `fee_schedule`, and its STEP 3 adds an engagement letter template. There are 0 templates and 0 fee schedules present, consistent with the script never having run here.

4. **Test firm rows in the dev database initially suggested the test suite might target `accounting_dev`.** If it did, the `Base.metadata.drop_all()` in `conftest.pytest_unconfigure` would mean the Phase 0 pytest run had destroyed the very data this session was meant to inventory. This was checked rather than assumed. `tests/conftest.py` loads `.env.test` with `override=True`, and that resolves to `localhost:5432/accounting_test`, a **separate** database. The dev database was not touched by the Phase 0 run. Only two application databases exist on this instance, `accounting_dev` (25 MB) and `accounting_test` (14 MB), so there is no third database holding richer dev data. How the "Auth Test Firm" rows came to be in `accounting_dev` is unexplained; the most likely reading is a manual run against dev at some point in May, but this session found no evidence either way.

5. **Three separate writers can modify the blob with arbitrary, unvalidated keys, and two of them replace it wholesale.** `PATCH /users/firm/settings` takes an untyped `dict` and merges. `PATCH /firms/me` (firm_owner) and `PATCH /firms/{firm_id}` (system_admin) both accept `FirmUpdate.settings` and pass it through `crud/firm.py:34`, which does a plain `setattr`, replacing the entire blob rather than merging into it. Retiring the fee writers means addressing all three paths, not only the fee schedule tab path. It also means any key documented in this report can be destroyed today by a caller who sends a partial `settings` object to either firms endpoint.

6. **The Concierge reads settings keys by substring match rather than by name** (`app/api/concierge/functions.py:1221`). Any key containing `notif`, `email`, or `reminder` is surfaced. This reader cannot be enumerated statically, so no static inventory of the blob, including this one, can claim to be complete with respect to it.

7. **Nothing in the test suite watches the blob.** No test reads or writes `Firm.settings` directly. Per process rules instance nine, this is an absent watcher rather than a passing one: if the backfill breaks a NON FEE reader such as the login `session_timeout_minutes` path or `get_firm_email_settings`, no existing test would go red.

8. **`app/api/reports.py:228` is named `get_billing_detail` but reads only `portal_logo_s3_key`.** It is classified NON FEE. The name is the only thing about it that suggests fee relevance, and per the August 14 clarification about names not conferring status, the code was read rather than the name trusted.

9. **`fee_amount` is not a settings key.** It appears in `app/services/esign_service.py:75` and `app/api/esign.py:634` as an engagement letter template context variable, populated from an argument and from a hardcoded preview string `"$850"` respectively. It is noted only because a text search for fee-related terms surfaces it.

10. **Three frontend readers consume `settings.fee_schedule` directly.** These are outside the `app/`, `scripts/`, `tests/` scope specified for this session and are listed for completeness because a hard cut with no dual write period would break them: `frontend/src/components/settings/FeeScheduleTab.tsx:69` (reads, and writes back via `PATCH /users/firm/settings` at line 115), `frontend/src/components/engagements/SendEngagementLetterModal.tsx:112`, and `frontend/src/app/(app)/engagements/page.tsx:850`.
