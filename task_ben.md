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
- Never trust file contents shown in VS Code opened against the Windows copy (C:\Users\corby\jamm-os) or Windows File Explorer. Verify all file state via the WSL terminal (cat, ls -la, wc -l) before assuming a file is stale, empty, or correct.
- Generated snapshot files (codebase_snapshot.txt, frontend/frontend_snapshot.txt) are gitignored. Never manually stage, commit, or resurrect them. Regenerate only via ./update_all_snapshots.sh.
- Before the first commit of any session, confirm git config user.email is ben@jammpx.com. Never assume git identity is correct without checking.
- Before writing or modifying anything touching the Concierge agent, read /home/corby/jamm-os/JAMM_PX_Perfect_Assistant_Build.md in full. Every Concierge task should be traceable to something described in that document.
- If a Concierge tool call fails inside the tool-use loop, the failure must surface as a diagnosable logged event, never as a generic deflection presented to the firm owner as if it were a real answer. Check backend logs for "Tool execution failed" before concluding a knowledge gap exists rather than a broken tool call.

---

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

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

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Fix the generic, unshaped loading skeletons on six list/table pages found in tonight's full skeleton audit — billing, billing/wip, clients, documents, engagements, and tasks. Each currently shows identical flat gray bars per cell regardless of what the real table's columns actually are, so the loading state looks the same whether you're viewing invoices, clients, or tasks. Replace each with a real skeleton matching that specific page's actual table columns.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat "src/app/(app)/dashboard/page.tsx" | grep -n "Skeleton" -A 8

Reference standard: named, content-shaped skeleton components using surface-border/dark-border tokens and animate-pulse, matching real content layout.

Confirmed reference for billing specifically, already investigated:

sed -n '1,90p' src/components/billing/InvoiceTable.tsx

Confirms the real table has 5 columns: Invoice, Client, Amount, Due, Status, with Status rendered via a real StatusBadge component (not a plain bar), and an optional checkbox column when selection is enabled. The billing/page.tsx loading state currently renders 5 rows of 6 identical h-4 flex-1 generic bars with no distinction between columns — this must be replaced with cells sized and shaped to match: a shorter bar for Invoice number, a medium bar for Client name, a shorter right-ish bar for Amount, a short bar for Due date, and a pill-shaped badge placeholder for Status (matching StatusBadge's real rounded-pill shape, not a plain bar).

For each of the other five pages, before writing any skeleton, view the real table/list component it renders to determine the real column structure:

For billing/wip/page.tsx: find and view its real table/row component.
For clients/page.tsx: find and view its real table/row component (likely a ClientTable or similar, search for "Table\|Card" imports at the top of the page file the same way InvoiceTable/InvoiceCard were found for billing).
For documents/page.tsx: same approach.
For engagements/page.tsx: same approach — note EngagementCard and EngagementTable are known to exist from tonight's earlier audit, matching the InvoiceTable/InvoiceCard split pattern.
For tasks/page.tsx: same approach — note TaskCard and TaskTable are known to exist from tonight's earlier audit, matching pattern.

For each page, identify the real column headers, their approximate relative widths, and any special cell types (badges, pills, avatars, currency-right-aligned, etc.) before writing that page's skeleton. Do not guess — read the real component file first.

If any page's current loading state doesn't match "generic flat h-4 bars per cell," stop and report the actual current state for that specific page instead of proceeding with an assumption.

CHANGE INSTRUCTIONS:

For each of the six pages, replace the generic flat-bar skeleton with a real, named, content-shaped skeleton component matching that page's actual real table columns (as investigated in VERIFY BEFORE ACT). Each cell in the skeleton row should be shaped and sized proportionally to its real column's typical content — short bars for dates/numbers, medium bars for names, pill-shaped placeholders for status badges, matching the real StatusBadge/badge component's actual border-radius and approximate size rather than a plain rectangular bar.

Keep the same row count (5 rows, matching the existing pattern) and the same outer container structure (rounded-modal border, existing color tokens) — only the per-cell shapes change from generic to column-matched.

Name each skeleton component descriptively per page (e.g. BillingTableSkeleton, ClientsTableSkeleton, etc.), following the naming convention already established in dashboard/page.tsx and in tonight's earlier fixes.

Do not touch any file not in this list of six. Do not change any data-fetching logic, only what renders during the loading state.

VERIFY AFTER ACT:

For each of the six files:
grep -n "Skeleton" "src/app/(app)/[path]/page.tsx"

Confirm a real, named, column-matched skeleton component now exists in each, replacing the generic flat-bar version.

git diff --stat

Confirm the diff touches only these six files.

MANUAL VERIFICATION:

Ben will run npm run build himself in the frontend directory and confirm it's clean before trusting this as done.

**Restart the frontend.** With network throttled to Slow 3G in devtools, visit each of the six pages (Billing, Billing WIP, Clients, Documents, Engagements, Tasks) and confirm each now shows a skeleton with cells shaped to match that specific page's real columns — not identical generic bars across all six pages. Report back plainly, page by page, and note if any page's real table structure turned out to be different from what was assumed going in.

GIT:

Do not commit until Ben confirms in the browser.