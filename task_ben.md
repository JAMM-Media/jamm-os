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

TASK: Frontend hygiene batch. Three unrelated, low-risk cleanup items from the Aug 11 email exchange with Andrew. Each item is independent -- do not let one block the others.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:
pwd

State plainly: confirm the output is exactly /home/corby/jamm-os, and confirm no path resolved against /mnt/c/Users or any Windows-side copy.

REPORTING DISCIPLINE / ANTI-HALLUCINATION:
Quote all real output verbatim. Never paraphrase.
If evidence is absent, STOP and report the absence rather than inferring.
Take no action beyond what CHANGE INSTRUCTIONS explicitly names.
Before claiming any file is stale, unused, or safe to delete, confirm it exists and state its real git tracking status, and search for any real reference to it elsewhere in the codebase before concluding it is unreferenced.
Do NOT delete the file named "main" at the repo root under any circumstances in this task, regardless of what you find. Report findings only; Ben decides separately.

VERIFY BEFORE ACT:

Block 1, current state:
cd /home/corby/jamm-os
git fetch origin
git status --short
git log --oneline -3

Block 2, frontend test/tsx state:
cat frontend/package.json
find frontend -maxdepth 3 -iname "*.test.ts" -o -iname "*.test.tsx" -o -iname "*.spec.ts" -o -iname "*.spec.tsx" 2>/dev/null

Report the real current devDependencies, whether tsx is already present, whether any test script exists, and which real file is the one existing test.

Block 3, Growth Cooperative leftover strings:
grep -rln "Growth Cooperative" frontend/src/ 2>/dev/null
grep -rn "Growth Cooperative" frontend/src/ 2>/dev/null

Report every real file and line where this string still appears.

Block 4, the stray "main" file:
ls -la main 2>/dev/null
file main 2>/dev/null
cat main 2>/dev/null
git log --all --oneline -- main
git log -p --follow -- main | head -60
grep -rn "\"main\"\|'main'\|/main\b" package.json frontend/package.json .github/ 2>/dev/null

Report: does this file exist at the repo root, what are its real contents (or confirm it is genuinely empty), what does its git history show (when added, by whom, in what commit, with what commit message), and is it referenced anywhere as an entry point, script target, or build artifact name. Do not conclude anything about safety to delete -- just report the real evidence.

WHAT THIS IS:
Three independent hygiene items, per Ben and Andrew's Aug 11 exchange: (1) get the one existing frontend test actually runnable via tsx plus a test script, (2) finish the Growth Cooperative to Peer Network rename Andrew made official Aug 11 by catching any leftover strings, (3) investigate but do NOT delete a stray empty file named "main" at the repo root -- Ben will decide on deletion after reviewing real findings.

CHANGE INSTRUCTIONS:

1. Add tsx to frontend's devDependencies (confirm the real current version convention used by other devDependencies in the same package.json -- match it rather than guessing a version). Add a test script to package.json's scripts block that actually runs the one existing test file found in Block 2, using tsx. Do not invent a broader test framework or configuration beyond what is needed to run the one existing test.

2. For every real occurrence found in Block 3, replace "Growth Cooperative" with "Peer Network" in frontend/src/. Do not touch any occurrence outside frontend/src/ without reporting it first. Do not touch anything in docs/, backend code, or migration files even if it happens to contain the old name -- report those separately if found, do not change them in this task.

3. No action on the "main" file. Report only, per Block 4.

No em dashes anywhere in any file, string, comment, or commit message.

VERIFY AFTER ACT:

cd frontend
npm run test 2>&1 | tail -30

Confirm the one test actually runs and its real pass/fail result.

grep -rn "Growth Cooperative" frontend/src/ 2>/dev/null

Confirm this returns nothing -- zero remaining occurrences in frontend/src/.

git diff --stat

Paste the full real diff for review.

MANUAL VERIFICATION:
Restart frontend dev server before Ben spot-checks any UI screens that previously showed "Growth Cooperative" text, to confirm the rename displays correctly.

GIT:
Do not commit until Ben reviews the real diff pasted in chat. After Ben confirms and pushes:
git log --oneline -3
Paste the real output confirming the new hash sits next to origin/main and origin/HEAD.