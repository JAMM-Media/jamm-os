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

TASK: The login page currently relies on native browser HTML validation (the `required` attribute) to prevent empty form submissions. This produces an unstyled, ugly native browser popup ("Please fill out this field") that renders differently and poorly across browsers (confirmed by Ben on both Chrome and Safari), completely outside the app's design system and uncontrollable via CSS. Replace native validation with the app's own styled inline error message, reusing the existing red error text pattern already used for login failures.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

sed -n '39,65p' "src/app/(auth)/login/page.tsx"
sed -n '125,180p' "src/app/(auth)/login/page.tsx"

Paste both. Confirm handleSubmit currently calls e.preventDefault() then immediately calls login(email, password) with no check that either field is non-empty, relying entirely on the required attribute on the input elements to prevent this. Confirm the existing error display pattern: {error && (<p className="text-[11px] text-[#991B1B] mt-1">{error}</p>)}.

If this does not match, stop and paste the real content instead of proceeding.

CHANGE INSTRUCTIONS:

1. Add noValidate to the main login form tag (the one with onSubmit={handleSubmit}), disabling the browser's native validation UI entirely for this form.

2. At the start of handleSubmit, after e.preventDefault() and before setIsLoading(true), add a real client-side check: if email.trim() is empty, setError('Please enter your email.') and return early without calling login(). If password.trim() is empty (and step is 'password'), setError('Please enter your password.') and return early. Use the exact existing setError mechanism and existing error display, no new state or new UI element needed, the error will render through the same {error && (...)} block already in the file.

3. Also add noValidate to the magic link form (the one with onSubmit={handleMagicLink}), and add an equivalent check at the start of handleMagicLink: if the effective magic link email is empty, use the existing setMagicError mechanism with a message like 'Please enter your email.' and return early, before making the fetch call.

4. Remove the required attribute from the email and password inputs in the main form, and from the magic link email input, since validation is now handled by the code instead of the browser. Do NOT remove required from the TOTP or backup code inputs unless you also add equivalent client-side checks for them — if you have time, add the same pattern (check totpCode or backupCode is non-empty before calling login() in the 'code' step), otherwise leave required on those two specific inputs alone as a safe fallback, and note this explicitly in your report.

Do not change any other validation, the login logic itself, routing, or styling.

VERIFY AFTER ACT:

sed -n '39,65p' "src/app/(auth)/login/page.tsx"
sed -n '125,180p' "src/app/(auth)/login/page.tsx"

git diff --stat

Confirm noValidate is present on both forms, confirm the new email/password checks exist and use the existing error state/display pattern, confirm required was removed only from the fields that now have a matching code-level check.

MANUAL VERIFICATION:

Ben will run npm run build himself and confirm it's clean before trusting this as done.

**Restart the frontend.** Reload /login. Click "Sign in" with both fields empty — confirm no native browser popup appears, and instead a styled red error message shows using the app's existing error text style. Fill in only email and submit — confirm the password-specific error shows. Test the magic link form the same way with an empty email. Confirm a real, valid sign-in still works normally end to end. Report back plainly whether the native validation popup is fully gone in favor of the app's own styled error.

GIT:

Do not commit until Ben confirms in the browser.