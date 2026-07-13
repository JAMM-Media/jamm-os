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

TASK: Add missing topic buckets for QC checklists and signature envelopes to fix chip mismatches

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '232,306p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "TOPIC_CHIPS" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm current state matches what is described below before editing.

WHAT IS WRONG:

Two separate keyword systems exist in this codebase: _OPERATIONAL_KEYWORDS, which decides whether a question routes to a tool, and _TOPIC_KEYWORDS, which decides which suggestion chip appears. Tonight, four new tools were added to _OPERATIONAL_KEYWORDS, but _TOPIC_KEYWORDS was never updated to match. Confirmed: no bucket exists anywhere in _TOPIC_KEYWORDS for QC checklist related terms or for signature envelope related terms. QC checklist questions currently fall through to whichever unrelated bucket happens to share an incidental keyword, producing a plausible looking but incorrect chip. Signature envelope questions currently classify as general, producing no chip at all, inconsistent with every other domain having one. Neither of these two domains has a dedicated top level page in the frontend, both live inline on the engagement detail page, confirmed by checking the route tree directly.

CHANGE INSTRUCTIONS:

In route.py, add two new entries to the _TOPIC_KEYWORDS dictionary, matching the exact style and format of the existing entries. Name one qc_checklists with keywords covering qc, quality control, qc checklist, qc items, qc pending, unchecked items, quality check. Name the other signature_envelopes with keywords covering signature, envelope, e-signature, esignature, pending signature, has signed, needs to sign, signed yet, declined signature, expired signature.

In ConciergePanel.tsx, add matching entries to the TOPIC_CHIPS object for both new topic keys, qc_checklists and signature_envelopes, each pointing to Go to Engagements, matching the exact chip destination already used for the engagements topic itself, since both of these domains are only reachable through the engagement detail page and there is no dedicated top level page for either to point to instead.

Do not change any existing topic bucket or any existing chip mapping. Do not add a dedicated page for either domain, that is out of scope for this task.

VERIFY AFTER ACT:

grep -n "qc_checklists\|signature_envelopes" /home/corby/jamm-os/app/api/concierge/route.py /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present in both files, both places.

python3 -c "from app.main import app; print('OK')"
npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Restart both servers. Ask which engagements have outstanding QC items, confirm the resulting chip now correctly reads Go to Engagements. Ask which signature requests are still pending, confirm a chip now appears at all, and that it also reads Go to Engagements rather than nothing.

GIT:
git add -A
git commit -m "add missing QC checklist and signature envelope topic buckets to the chip classifier, which was never updated when the corresponding tools and operational keywords were added earlier tonight, closing the gap between tool routing keywords and chip classification keywords"
git pull --rebase origin main
git push origin main