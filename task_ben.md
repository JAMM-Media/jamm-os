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

# Task: Phase 1 -- Create shared (app) route group layout and migrate dashboard, engagements, clients pages to eliminate AppShell/ConciergePanel remounting on navigation

USE: claude fable-5

## VERIFY BEFORE ACT

cat /home/corby/jamm-os/frontend/src/app/layout.tsx

Confirm the true root layout only wraps QueryProvider, AuthProvider, ThemeProvider, and Toaster -- no AppShell, no Sidebar, no ConciergePanel.

cat /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx | head -15

Confirm AppShell's props interface is exactly { children: React.ReactNode }, with no page-specific props required, and pathname is read internally via usePathname(), not passed in.

grep -c "<AppShell" /home/corby/jamm-os/frontend/src/app/dashboard/page.tsx /home/corby/jamm-os/frontend/src/app/engagements/page.tsx /home/corby/jamm-os/frontend/src/app/clients/page.tsx "/home/corby/jamm-os/frontend/src/app/clients/[id]/page.tsx"

Confirm counts match what was previously verified: dashboard 2, engagements 2, clients 2, clients/[id] 3, all with matching closing </AppShell> counts.

## WHAT IS WRONG

Confirmed via live testing and code tracing: AppShell (which renders Sidebar and ConciergePanel) is individually imported and rendered inside 23 separate page.tsx files across the app, rather than once in a shared Next.js layout. This means every client-side navigation between pages fully unmounts and remounts the entire AppShell tree, including ConciergePanel, destroying all local component state (the messages array holding the active conversation, and the hasInitialized ref meant to prevent the opening flow from re-triggering). This is the root cause of a bug where an active Concierge conversation completely disappears and gets replaced with a fresh opening message whenever the user clicks a "Go to X" suggestion chip or otherwise navigates between pages while the panel is open. Every prior fix to hasInitialized or messages state was addressing symptoms of this deeper structural issue, not the actual cause, since the whole component was being destroyed and recreated on every navigation regardless of any state-management logic inside it.

The correct fix is the standard Next.js pattern: move AppShell into a shared layout.tsx so React treats it as a stable, persistent part of the tree across route changes within that layout's scope, instead of tearing it down and rebuilding it per page. A plain root-level layout.tsx cannot be used directly, since /portal has its own separate layout.tsx for the unauthenticated client-facing portal and must never receive the authenticated AppShell. The correct mechanism is a Next.js route group -- a folder named (app) that does not affect the URL structure -- containing its own layout.tsx that wraps AppShell around children, with the authenticated pages physically moved inside that folder.

This task is Phase 1 of two: migrate only dashboard, engagements, and clients (both the list page and the [id] detail page) as a proof of concept, verify cross-page conversation persistence actually works end to end, before rolling the same pattern out to the remaining 20 pages in a follow-up task.

This is the highest-risk structural change made to this codebase this session -- it touches file locations, not just file contents, across the app's most-used pages. Move slowly, verify every step before proceeding to the next, and stop to report rather than guess if anything about the file structure does not match what is described below.

## ACTION

Step 1: Create the route group layout.

Create /home/corby/jamm-os/frontend/src/app/(app)/layout.tsx:

// path: frontend/src/app/(app)/layout.tsx
import { AppShell } from '@/components/layout/AppShell'

export default function AppGroupLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <AppShell>{children}</AppShell>
}

Step 2: Move the four page files into the new route group, preserving their exact relative paths and all dynamic segment folder names.

Move (using git mv to preserve history, not delete-and-recreate):

git mv frontend/src/app/dashboard frontend/src/app/(app)/dashboard
git mv frontend/src/app/engagements frontend/src/app/(app)/engagements
git mv frontend/src/app/clients frontend/src/app/(app)/clients

Note: engagements and clients folders each already contain their own [id] subfolder or similar nested routes -- moving the parent folder moves all nested routes automatically. Confirm after each git mv that the nested dynamic route folders moved correctly by listing the new directory contents before proceeding to the next git mv.

Step 3: In each of the four now-moved page.tsx files (dashboard/page.tsx, engagements/page.tsx, clients/page.tsx, clients/[id]/page.tsx), remove every <AppShell> opening tag and its matching </AppShell> closing tag, while preserving everything between them exactly as-is (the actual page content, loading states, and error states must remain completely unchanged, only the wrapper tags are removed). Also remove the now-unused AppShell import line from each file's import block.

For dashboard/page.tsx: 2 <AppShell> instances to unwrap (a loading/error state and the main success state).
For engagements/page.tsx: 2 instances.
For clients/page.tsx: 2 instances.
For clients/[id]/page.tsx: 3 instances (a loading state, a not-found state, and the main state).

Each unwrap means deleting just the <AppShell> and </AppShell> lines themselves and dedenting the content between them if needed for readability, not deleting or altering the JSX content itself. Do this one file at a time, verifying the AppShell count drops to zero in that specific file before moving to the next file.

Do not modify AppShell.tsx itself. Do not touch any of the other 19 pages that still individually import AppShell -- those remain unchanged in this phase and will continue to work exactly as before, just without the persistence fix yet. Do not modify ConciergePanel.tsx in this task.

## VERIFY AFTER ACT

find /home/corby/jamm-os/frontend/src/app/\(app\) -type f -name "*.tsx"

Expected: dashboard/page.tsx, engagements/page.tsx, clients/page.tsx, clients/[id]/page.tsx (and any other files that were nested inside the original engagements/ or clients/ folders, such as loading.tsx or additional dynamic routes) all present under the new (app) route group.

grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/dashboard/page.tsx" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx" "/home/corby/jamm-os/frontend/src/app/(app)/clients/page.tsx" "/home/corby/jamm-os/frontend/src/app/(app)/clients/[id]/page.tsx"

Expected: 0 for all four files -- every AppShell wrapper tag removed.

grep -n "import.*AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/dashboard/page.tsx" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx" "/home/corby/jamm-os/frontend/src/app/(app)/clients/page.tsx" "/home/corby/jamm-os/frontend/src/app/(app)/clients/[id]/page.tsx"

Expected: no matches -- unused import removed from all four.

cd /home/corby/jamm-os/frontend
rm -rf .next
npm run build

Expected: zero errors, and the build output's route list still shows /dashboard, /engagements, /clients, and /clients/[id] as valid routes (route groups do not appear in the URL, Next.js resolves them transparently).

## MANUAL VERIFICATION (the actual test -- this is what actually proves the fix)

1. Restart the frontend with a clean build (the rm -rf .next above already forces this).
2. Log in, navigate to Dashboard, open the Concierge panel, ask a real question (e.g. "how do I add a new engagement") and get a real answer.
3. Click the "Go to Engagements" suggestion chip that appears below the answer.
4. Confirm you land on the Engagements page AND the panel still shows the full prior conversation (the question and answer from step 2), not a fresh "Let's get ready to work" message.
5. Ask a follow-up question on the Engagements page and confirm it works normally, continuing the same conversation.
6. Navigate to Clients using the sidebar (not a chip) and confirm the conversation still persists.
7. Open a specific client's detail page and confirm the conversation still persists there too.
8. Regression check: navigate to a page NOT in this phase's migration (e.g. Staff, Billing, Settings) and confirm the conversation DOES still reset there for now, since those 19 pages have not been migrated yet -- this is expected and will be fixed in Phase 2, not a failure of this task.
9. Regression check: confirm the /portal client-facing login page is completely unaffected and still has no sidebar or Concierge panel.

Report what you observe at steps 4 through 7 specifically, since that is the actual proof this phase worked.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Phase 1 -- move AppShell into a shared (app) route group layout for dashboard, engagements, and clients pages, so the Concierge panel and its conversation state persist across navigation between these pages instead of fully remounting and losing all state on every route change. Phase 2 will roll this pattern out to the remaining pages."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.