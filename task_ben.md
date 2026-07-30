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

TASK: Expose a real refreshUser function on the auth context and call it after both Concierge setting changes, fixing the shared user object going stale without a full reload

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '1,50p' /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx

sed -n '85,92p' /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx

sed -n '550,575p' /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

Confirm AuthContextType currently exposes only user, isLoading, isAuthenticated, login, and logout, with no way for any other component to trigger a refresh of the user object after it has already loaded. Confirm the initial fetch of /api/auth/me happens once, inside a useEffect with an empty dependency array, on mount only. Confirm handleConciergeEntryModeChange and handleConciergeSuggestionsChange in the Settings page both currently write to the backend successfully but never update the shared user object afterward.

WHAT THIS IS:

Confirmed live tonight: toggling Concierge Suggestions to Off in Settings correctly saved to the backend, but navigating to Engagements in the same browser session without a full page reload still showed the suggestion banner, because the shared user object read by every gated page comes from AuthProvider, which only ever fetches once on mount and has no way to be told a setting changed elsewhere. This is very likely the same latent gap behind concierge_entry_mode, which was never caught because it was always tested using a fresh incognito window, a genuine new mount, rather than same-session navigation after a change. Both settings need a real fix, not just the one that was caught live.

CHANGE INSTRUCTIONS:

In useAuth.tsx, extract the existing fetch-and-setUser logic currently inside the mount-time useEffect into its own named async function, for example refreshUser, that fetches /api/auth/me and calls setUser with the result. Call this same function from inside the mount-time useEffect so the original first-load behavior is unchanged. Add refreshUser to AuthContextType and include it in the object passed to AuthContext.Provider's value prop, so any component using useAuth can now call it directly.

In the Settings page, destructure refreshUser alongside the existing user from useAuth. At the end of handleConciergeEntryModeChange, after its existing PATCH call succeeds, call refreshUser and await it. Do the same at the end of handleConciergeSuggestionsChange, after its existing PATCH call succeeds. Do not change the existing localStorage or custom event logic already present in handleConciergeEntryModeChange, this is an addition, not a replacement, and do not change the PATCH call itself in either function.

VERIFY AFTER ACT:

grep -n "refreshUser" /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

Expected: refreshUser defined and exposed in useAuth.tsx, and called in both handler functions in the Settings page.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Without reloading the page at any point, go to Settings, switch Concierge Suggestions to Off, then navigate directly to Engagements, Billing, or the client detail page, wherever a real trigger condition is currently true. Confirm no suggestion or banner appears, with no page reload involved.

Switch it back to On in Settings, again without reloading, navigate to the same page, confirm the suggestion or banner correctly reappears immediately.

Separately, without reloading, switch Concierge Entry Point between Sidebar and Floating in Settings, then navigate to a different page and back to Settings, confirm the correct option still shows as selected, confirming this same fix also closed the equivalent gap for that setting.

Report pass or fail for all three checks individually.

GIT:

git add -A

git commit -m "expose a real refreshUser function on the auth context, fixing the shared user object going stale after changing either Concierge Suggestions or Concierge Entry Point in Settings without a full page reload, confirmed live tonight when turning suggestions off correctly saved to the backend but the Engagements page still showed a banner in the same session, since AuthProvider previously only ever fetched the user object once on mount with no way for any other component to trigger a refresh"

git pull --rebase origin main

git push origin main