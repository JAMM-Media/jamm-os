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

# Task: Fix onboarding message race condition and correct the "New engagement" chip to open the actual new-engagement form

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '383,420p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current _open() effect: it checks !user?.firm_type to decide whether to show the onboarding question, with no check on isLoading from useAuth() beforehand, meaning if user is still null/loading at the moment this effect runs, firm_type will incorrectly appear unset even for a firm that already has it configured.

grep -n "isLoading" /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx

Confirm isLoading is exposed on the AuthContextType and set to false only after the initial /api/auth/me fetch completes.

grep -n "'New engagement'\|'new-engagement'" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current handleSuggestion routes map sends 'New engagement' to the plain route '/engagements', identical to 'Go to Engagements', and confirm the existing 'new-engagement' modal action (already used successfully elsewhere, per modalLabel map showing 'Opened New Engagement drawer') that this chip should trigger instead.

## WHAT IS WRONG

Confirmed via live testing: two separate, small bugs.

1. The onboarding "what does your firm do most" question sometimes reappears for firms that already have firm_type set, immediately after the Phase 1 route-group migration. Root cause: the _open() effect checks !user?.firm_type without first confirming useAuth()'s isLoading has finished. If the panel's opening logic runs before the async /api/auth/me fetch resolves, user is still null and the check incorrectly treats firm_type as unset, showing the onboarding question to a firm that has already completed it.

2. The "New engagement" suggestion chip is functionally identical to "Go to Engagements" -- both just navigate to /engagements with no distinction, even though a working "open the new engagement form directly" action (new-engagement) already exists and is used successfully elsewhere in this file.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Fix 1 -- import useAuth's isLoading and wait for it before evaluating firm_type in the _open() effect. Find where user is currently obtained via useAuth() in this file (likely already destructured near the top of the component) and confirm isLoading is also destructured from the same call. Then, inside the _open async function, before the existing "if (!user?.firm_type)" check, add a wait similar to the existing uiContext.ready wait pattern:

          if (isLoadingAuth) {
            let waited = 0
            while (isLoadingAuth && waited < 1500) {
              await new Promise((resolve) => setTimeout(resolve, 100))
              waited += 100
            }
          }

Note: since isLoading is a value from a hook, not a ref, a simple closure-captured while loop like this will not see updates to it across renders. Instead, use a ref that mirrors isLoading's current value, updated via a separate small effect:

  const isLoadingAuthRef = useRef(true)
  useEffect(() => {
    isLoadingAuthRef.current = isLoading
  }, [isLoading])

Then inside _open, wait on the ref instead:

          if (isLoadingAuthRef.current) {
            let waited = 0
            while (isLoadingAuthRef.current && waited < 1500) {
              await new Promise((resolve) => setTimeout(resolve, 100))
              waited += 100
            }
          }

Place this new wait block right after the existing uiContext.ready wait block, before the pathname.startsWith('/dashboard') check, so both readiness conditions (page context and auth) are satisfied before any firm_type-dependent branching happens.

Fix 2 -- change the 'New engagement' chip to trigger the existing new-engagement modal action instead of a plain route navigation. In the handleSuggestion function, the routes map currently includes 'New engagement': '/engagements'. Remove this specific entry from the plain routes map, and add a special case before or after the existing route lookup that handles 'New engagement' by calling executeAction directly with the modal action shape already used successfully elsewhere in this file for new-engagement (matching whatever exact action.type and structure the existing working new-engagement modal action uses, found via the modalLabel map reference at VERIFY BEFORE ACT).

Do not change any other suggestion chip mapping. Do not change the show_briefing_again, set_firm_type, or any other action handling. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "isLoadingAuthRef" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: the ref declaration, its update effect, and its use inside the _open wait block, all present.

grep -n "'New engagement'" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: no longer present in the plain routes map; present instead wherever the new special-case handling for this chip was added.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend with a clean build.
2. Log in as a firm with firm_type already set (Riverside). Navigate directly to Dashboard as the very first page load of a fresh browser session (private window), open the Concierge panel immediately.
3. Confirm the onboarding "what does your firm do most" question does NOT appear -- confirm either the morning briefing or the plain "Let's get ready to work" message appears instead, matching a firm with firm_type already configured.
4. Repeat step 2-3 three times with fresh private windows to confirm this holds consistently, not just once, since race conditions can be intermittent.
5. Ask the Concierge a question that produces a "New engagement" suggestion chip (e.g. ask about creating an engagement), click the chip, and confirm it opens the New Engagement drawer/modal directly rather than just navigating to the plain Engagements list page.

Report what you observe at steps 3 (across all three attempts) and 5.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge panel now waits for useAuth's isLoading to resolve before evaluating firm_type, preventing the onboarding question from incorrectly reappearing for firms that already have firm_type set; also fixed the New engagement suggestion chip to open the new-engagement form directly instead of just navigating to the plain Engagements list, matching what Go to Engagements already does"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.