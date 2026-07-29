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

TASK: Bring ContextualBanner's visual weight in line with SuggestionCard's ring-and-glow treatment, keeping its confident, factual tone

USE: claude sonnet

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/SuggestionCard.tsx

sed -n '145,158p' /home/corby/jamm-os/frontend/src/app/\(app\)/billing/page.tsx

grep -n "color-status-red\|color-status-green\|color-status-amber" /home/corby/jamm-os/frontend/src/app/globals.css

Confirm ContextualBanner currently uses a solid status-color background fill with a solid-fill button, no ring or glow, and confirm SuggestionCard's current ring-1 plus shadow-[] glow pattern and its outlined, de-emphasized button style. Confirm the real hex values for status-red-text, status-green-text, and status-amber-text before hardcoding any rgba glow values. Confirm the live Billing usage passes a real, factual, non-speculative message (a real overdue invoice count and dollar total), not a suggestion, before editing.

WHAT THIS IS:

Direct product decision to bring ContextualBanner visually in line with the ring-and-glow treatment just finished on SuggestionCard, so both inline Concierge components read as the same visual family. This is explicitly not a copy of SuggestionCard's honest, low-commitment label pattern ("Might be worth a look"), since ContextualBanner represents a confident, factual, ready-to-act state, a real overdue invoice count and total, not a speculative suggestion, and using speculative framing here would misrepresent it. Only the visual weight is being harmonized: a softer background instead of a solid color fill, a ring and soft glow in the banner's own tone color instead of a hard border, and a de-emphasized, outlined button instead of a solid-fill button, matching the restraint already established for SuggestionCard.

CHANGE INSTRUCTIONS:

For each of the three tones, green, amber, and red, replace the current solid wrapperClass background fill with a lighter background tint using the same status color at low opacity (for example bg-status-red/15 instead of bg-status-red), combine it with a ring-1 in the tone's -text color at moderate opacity, and add a soft box-shadow glow using the tone's real confirmed hex value at roughly 25 to 35 percent opacity, sized similarly to the glow already used on SuggestionCard and the portal-link highlight. Change each tone's button from a solid color fill to an outlined, ghost-style button, using the tone's -text color for text and border with a transparent or near-transparent background, matching the exact treatment already used for SuggestionCard's button. Keep the bold count number exactly as it is, this is a real, confident data point and should stay visually prominent, not softened. Do not add any honest-label style text, do not change the compact horizontal layout, do not add a header bar or identity dot, this banner should stay visually distinct in shape from SuggestionCard while matching its restraint and glow language.

VERIFY AFTER ACT:

grep -n "shadow-\[\|ring-1\|bg-status-red$\|bg-status-green$\|bg-status-amber$" /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Expected: no bare bg-status-red, bg-status-green, or bg-status-amber remain as solid fills, and shadow-[ and ring-1 now appear.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Visit /dev/concierge-kit, confirm ContextualBanner's green and amber examples now show a softer tinted background with a visible ring and glow, in both light and dark mode, and confirm their buttons are now outlined rather than solid fill.

Visit Billing with at least one real overdue invoice present, confirm the live red banner shows the same updated treatment, still states the real count and dollar total clearly, and the count number is still bold and prominent.

Confirm clicking Ask Concierge on the live banner still correctly opens the panel and prefills the overdue invoices question, unaffected by the visual change.

Report pass or fail for each of the three checks individually.

GIT:

git add -A

git commit -m "bring ContextualBanner's visual weight in line with SuggestionCard's ring-and-glow treatment across all three tones, replacing solid color fills with softer tinted backgrounds plus a ring and soft glow, and de-emphasizing each tone's button to an outlined style matching SuggestionCard's button, while deliberately keeping the bold count number, compact horizontal layout, and confident factual tone intact, since ContextualBanner represents a ready-to-act state rather than a speculative suggestion and should not carry SuggestionCard's low-commitment honest-label framing"

git pull --rebase origin main

git push origin main