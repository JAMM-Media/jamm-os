# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# Section 3 - The task

# Task: Add 7 missing Settings knowledge sections to Concierge prompts.py

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "Fee Schedule: Navigate to Settings" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the Fee Schedule entry exists and its exact line number. All 7 new entries will be added as a single new block immediately after the Fee Schedule paragraph and its professional-judgment redirect sentence, before the blank line that precedes the QuickBooks Integration section. Do not add entries anywhere else in the file.

grep -n "QUICKBOOKS INTEGRATION\|---" /home/corby/jamm-os/app/api/concierge/prompts.py | head -10

Confirm the exact line numbers of the --- divider and QUICKBOOKS INTEGRATION heading that follow the Fee Schedule entry, so the insertion point is unambiguous.

## WHAT IS WRONG

Confirmed via direct live testing and full app audit: 7 real, live Settings features have zero coverage in prompts.py. A firm owner asking the agent about any of these would get either a wrong answer or a denial that the feature exists, the same class of failure as the Fee Schedule bug found and fixed earlier. All 7 were verified against actual component source files (SecurityTab.tsx, MigrationTab.tsx, PortalBrandingTab.tsx, EmailCalendarTab.tsx, settings/page.tsx) to ensure exact field names, navigation paths, and descriptions match the real UI.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

After the existing Fee Schedule block (the paragraph ending with "...offer to navigate them to Settings > Fee Schedule to enter whatever amount they decide on."), insert the following new block as a single addition before the existing --- divider that precedes QUICKBOOKS INTEGRATION. Do not modify any existing text.

---

Settings > Security (firm owner only): Three sub-sections. (1) Staff login policy -- three options: "Password or magic link" (staff can sign in with either a password or a one-time email link; recommended for most firms), "Password only" (staff must use their password; magic links are disabled; best for firms with strict security requirements), "Magic link only" (staff sign in via one-time email links; no passwords required; eliminates weak password risk). Note: the firm owner's own login always requires a password regardless of this setting. (2) Password policy -- sets minimum password length and maximum failed login attempts. After the configured number of consecutive failed logins, the account locks for 30 minutes. (3) Session timeout -- how long staff stay logged in before being asked to sign in again. Six options: 30 minutes (high security, staff sign in frequently), 1 hour (recommended for shared workstations), 2 hours (balanced security for most firms), 4 hours (standard for dedicated work machines), 8 hours (default; one sign-in per workday), 24 hours (convenient for trusted devices). Changes take effect on the next login; active sessions are not affected.

Settings > Migration (under Data, firm owner only): Six import paths, all accessed by uploading a CSV file. (1) Generic CSV -- required column: name; optional columns: email, phone, entity_type (individual, business, trust, or estate), company_name, address_line1, address_line2, city, state, postal_code, country, tags, notes; maximum 500 clients per import. (2) Canopy Individuals -- upload the Canopy Individuals export; in Canopy, go to Clients, select Import clients, choose Individual as the client type, and export current individual clients as CSV. (3) Canopy Businesses -- upload the Canopy Businesses export; in Canopy, go to Clients, select Import clients, choose Business as the client type, and export current business clients as CSV. (4) Karbon -- upload the Karbon contacts export; in Karbon, go to Contacts, click the cloud icon, and select All contacts; the Type column (Person or Organisation) maps automatically to Individual or Business in JAMM PX. (5) Financial Cents -- upload the Financial Cents client export; in Financial Cents, go to Clients, click Export, and download as CSV; JAMM PX imports Name, Email, Phone, and Address fields automatically. (6) TaxDome -- two separate imports: first import clients (upload the TaxDome Accounts export, downloaded from TaxDome under Clients, select all, export as CSV; JAMM PX previews every row before importing anything), then import jobs (upload the TaxDome Jobs export, downloaded from TaxDome under Work, select all jobs, export as CSV; job matching uses client names, so clients must be imported first). All import paths except generic CSV and Financial Cents show a preview before committing; review the preview and confirm before completing the import.

Settings > Portal (Portal Branding, firm owner only): Three customization areas. (1) Firm name in portal -- the name clients see in the portal top bar; defaults to the firm name. (2) Firm logo -- upload a PNG, JPG, SVG, or WEBP file up to 2MB; displayed in the portal top bar instead of the firm name when set. (3) Portal colors -- configure separate color schemes for dark mode and light mode; each mode has 9 named color slots: Top bar, Page background, Tab bar, Accent (tabs and buttons), Client avatar, Subtitle text, Card/item background, Primary text, Secondary text. A live preview updates as colors are changed. Use "Set as active" to choose which mode clients see. Use "Reset to defaults" to restore the original color scheme for either mode. A setup checklist shows three completion indicators: Display name customized, Firm logo uploaded, Colors customized. Save with the "Save branding" button.

Settings > Portal Domain (firm owner only): Lets firms give clients a branded portal URL (e.g. portal.smithcpa.com) instead of the default JAMM PX URL. Requires adding two DNS records to the firm's domain. Enter the desired subdomain in the SUBDOMAIN field (placeholder: portal.smithcpa.com) and click "Set Up Domain." No domain is configured by default.

Settings > Email Domain (under Email, firm owner only): Lets firms send client emails from their own domain instead of noreply@jammpx.com. Requires adding two DNS records to the firm's domain. Enter the domain (placeholder: smithcpa.com) and click "Register Domain." This tab is labeled "Email Domain" in the app navigation, not "Sending Domain."

Settings > Email & Calendar (under Email, firm owner only): Four toggles in two sections. Email Sync: "Enable email sync" (when on, staff can connect their Gmail or Outlook and see emails inside JAMM PX; when off, the My Integrations page shows a disabled message) and "Allow staff to disable email sync" (when on, individual staff members can opt out of email sync even when it is enabled firm-wide). Calendar Sync: "Enable calendar sync" (when on, staff can sync their calendar events into JAMM PX so appointments appear alongside engagements and tasks) and "Allow staff to disable calendar sync" (when on, individual staff members can opt out of calendar sync even when it is enabled firm-wide). A third section, Staff Integration Controls, shows per-staff email and calendar sync access overrides once staff have connected their email; this overrides their personal connection -- disabling here prevents them from using their inbox in JAMM PX regardless of whether they have connected.

Settings > Firm (firm owner only) has four sub-sections beyond the read-only firm info card: (1) Firm Contact Details -- Mailing Address, Phone Number, Website, and Contact Email; this information appears on engagement letters and client-facing documents. (2) Timesheets -- one toggle: "Require manager approval for submitted timesheets"; when on, submitted entries show as Pending Approval until a manager approves them. (3) Email Settings -- Reply-To Email Address (when clients reply to emails from JAMM PX, their reply goes to this address) and Email Display Name (the name clients see in their inbox; defaults to the firm name). (4) Review Requests -- one toggle: "Enable review requests" (when enabled, clients who rate their experience 9 or 10 will be prompted to leave a Google review after an engagement is marked complete); Google Review Link field (clients who rate 9 or 10 are directed here to leave a public review); Most recent client rating sub-section shows the last NPS score submitted by a client through a review request email. (5) Data export -- "Download export" button generates a ZIP file containing CSVs for all clients, engagements, invoices, tasks, IRS authorizations, notes, time entries, and documents; "Request document archive" button generates a larger archive sent to the firm owner's email. Large archives may take a few minutes.

## VERIFY AFTER ACT

grep -n "Settings > Security\|Settings > Migration\|Settings > Portal\|Settings > Email Domain\|Settings > Email & Calendar\|Settings > Firm" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: all 7 new section headings present.

grep -n "QUICKBOOKS INTEGRATION" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: still present and unchanged -- confirm the insertion did not accidentally modify anything below it.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

Restart the backend. Ask the Concierge each of the following questions and confirm each produces a correct, specific answer rather than a denial or a wrong navigation path:

1. "Where do I set the session timeout for my staff?"
2. "How do I import my clients from Karbon?"
3. "How do I customize my client portal colors?"
4. "How do I set up a custom portal domain?"
5. "Where do I set my firm's reply-to email address?"
6. "How do I enable Google review requests?"
7. "How do I export all my firm data?"

Report the exact response for each question.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: add 7 missing Settings knowledge sections to Concierge prompts.py covering Security tab (login policy, password policy, session timeout), Migration tab (all 6 import paths with exact source export instructions), Portal Branding, Portal Domain, Email Domain, Email & Calendar sync controls, and Firm sub-sections (contact details, timesheets, email settings, review requests/NPS, data export)"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.