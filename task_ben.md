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

TASK: Fix the generic/unshaped or spinner-only loading states on nine settings-area files from tonight's skeleton audit — team, my-integrations, settings/page, settings/billing, AutomationsTab, EmailCalendarTab, LetterTemplatesTab, SecurityTab, PortalBrandingTab.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat "src/app/(app)/dashboard/page.tsx" | grep -n "Skeleton" -A 8

Reference standard, already used successfully five times tonight: named, content-shaped skeleton components using surface-border/dark-border tokens and animate-pulse, matching real content layout.

Then, for each of the nine files, view enough of the real file to determine (a) exactly what the current loading state looks like and (b) what the real loaded content actually renders, so the skeleton can match it precisely rather than being guessed:

cat "src/app/(app)/settings/team/page.tsx" | grep -n "animate-pulse" -B 5 -A 15
cat "src/app/(app)/settings/my-integrations/page.tsx" | grep -n "animate-pulse" -B 10 -A 5
cat "src/app/(app)/settings/page.tsx" | grep -n "animate-pulse" -B 10 -A 10
cat "src/app/(app)/settings/billing/page.tsx" | grep -n "animate-pulse" -B 10 -A 10
cat frontend/src/components/settings/AutomationsTab.tsx | grep -n "SkeletonRow" -B 5 -A 20
cat frontend/src/components/settings/EmailCalendarTab.tsx | grep -n "animate-pulse" -B 10 -A 5
cat frontend/src/components/settings/LetterTemplatesTab.tsx | grep -n "animate-pulse" -B 10 -A 5
cat frontend/src/components/settings/SecurityTab.tsx | grep -n "224" 
sed -n '200,240p' frontend/src/components/settings/SecurityTab.tsx
cat frontend/src/components/settings/PortalBrandingTab.tsx | grep -n "animate-pulse" -B 10 -A 5

Note on SecurityTab.tsx specifically: this file has many Loader2 instances. Only the one around line 224 is a genuine initial-page-data-load spinner. All others (savingPassword, setupLoading, verifying, regenerating, disabling) are button-action spinners triggered by user clicks, not data-loading states — do not touch those, they are correct as-is and out of scope.

Note on AutomationsTab.tsx specifically: it already has a SkeletonRow component with title/subtitle/meta bars and a toggle-shaped placeholder. Before rebuilding it, compare it against the real automation row it's meant to represent (search this same file for how a real, loaded automation row renders) and determine honestly whether SkeletonRow already matches that shape well, or whether it needs adjustment. Report this determination explicitly rather than assuming either way.

If any file's current state doesn't match what a targeted grep suggests, stop and report the actual content instead of proceeding on that file with an assumption.

CHANGE INSTRUCTIONS:

For each of the nine files, based on your own investigation of its real loaded content:

1. team/page.tsx — replace the generic h-2 w-[60%] per-cell bars with a real skeleton matching the actual team member row's real columns (name, role, email, status, etc. — confirm real columns from the loaded row markup).

2. my-integrations/page.tsx — replace the generic h-[88px] card block with a real skeleton matching the actual integration card's real layout (icon, name, description, connect/status button — confirm from real card markup).

3. settings/page.tsx — this file has multiple distinct loading spots (an h-[88px] integrations block, three h-3 w-[120px] bars, and an h-2 w-[60%] bar). Address each with a skeleton matching its own real nearby content, treating them as separate small fixes within the same file rather than one unified change.

4. settings/billing/page.tsx — replace the single h-8 w-32 bar with a real skeleton matching the actual subscription status section's real layout (likely plan name, price, renewal date, or similar — confirm from real content).

5. AutomationsTab.tsx — if your investigation in VERIFY BEFORE ACT found SkeletonRow does not yet match the real automation row shape, fix it to match. If it already matches well, state that explicitly and make no change to this file.

6. EmailCalendarTab.tsx — replace the generic h-12 rounded-lg bars with a real skeleton matching the actual connected-account row's real layout (confirm from real markup — likely provider icon, email, sync status).

7. LetterTemplatesTab.tsx — replace the generic h-16 blocks with a real skeleton matching the actual template row's real layout (template name, type, last modified, or similar — confirm from real markup).

8. SecurityTab.tsx — replace the single centered Loader2 spinner at the genuine initial-data-load spot (confirmed in VERIFY BEFORE ACT) with a real skeleton matching the tab's real loaded content shape (likely 2FA status, password change form, backup codes section — confirm from real markup). Do not touch any of the button-action Loader2 spinners.

9. PortalBrandingTab.tsx — the current skeleton (a label bar + input bar) is already reasonably close to a real form field shape. Confirm this matches the real field it represents; if it does, this file may need no change or only a minor width/sizing adjustment — do not force an unnecessary rebuild if it's already adequate.

Name every new/changed skeleton component descriptively, following the naming convention established throughout tonight's work. Do not touch any file not in this list of nine, and do not touch action-button spinners anywhere.

VERIFY AFTER ACT:

For each of the nine files, run a grep confirming the skeleton/loading state that now exists.

git diff --stat

Confirm the diff touches only these nine files (fewer, if AutomationsTab or PortalBrandingTab needed no change — report explicitly which files were left untouched and why).

MANUAL VERIFICATION:

Ben will run npm run build himself in the frontend directory and confirm it's clean before trusting this as done.

**Restart the frontend.** With network throttled to Slow 3G in devtools, visit Settings > Team, Settings > My Integrations, the main Settings page, Settings > Billing, and the Automations, Email & Calendar, Letter Templates, Security, and Portal Branding tabs. Confirm each now shows a real, content-shaped skeleton (or confirm no change was needed where noted). Report back plainly, file by file.

GIT:

Do not commit until Ben confirms in the browser.