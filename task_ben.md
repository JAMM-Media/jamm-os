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

TASK: Replace the left/right corner position setting with a real Sidebar-vs-Floating entry mode choice, restoring the original sidebar Concierge nav item as one of the two modes

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '53,62p' /home/corby/jamm-os/frontend/src/components/layout/Sidebar.tsx

sed -n '500,560p' /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

sed -n '895,930p' /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

sed -n '95,115p' /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

cat /tmp/sidebar_before_removal.tsx | sed -n '225,239p'

Confirm Sidebar.tsx currently has no Concierge nav item and no onConciergeOpen prop at all, confirm the exact original code for that removed button is preserved in /tmp/sidebar_before_removal.tsx from git history, confirm Settings currently stores concierge_button_position as left or right inside the firm settings JSON blob and uses it purely to position the floating button in a screen corner, and confirm AppShell currently always renders PersistentEntryButton unconditionally. Confirm all of this before changing anything.

WHAT THIS IS:

Direct correction of a misunderstanding from earlier tonight. The left/right setting just built was based on a misread of the original request: the person wanted a real choice between two different entry point styles, the original sidebar navigation item that was removed earlier tonight when it was found to be redundant with the new floating button, versus the new floating button itself, not a choice of which screen corner the floating button sits in. The two modes are being named Sidebar and Floating, deliberately not old and new, since one is not simply a legacy version of the other, they are two different, equally valid interaction patterns a firm may prefer.

CHANGE INSTRUCTIONS:

In Sidebar.tsx, restore the exact Concierge nav button code from /tmp/sidebar_before_removal.tsx, including the onConciergeOpen prop in SidebarProps and the function's destructured parameters, placed back in its original position between Dark mode and Settings.

In settings/page.tsx, rename the stored setting from concierge_button_position with values left or right, to concierge_entry_mode with values sidebar or floating, defaulting to floating when absent. Update the section's heading and copy to describe choosing between the Sidebar and Floating entry points, no longer screen corner language. Update the two radio options to read Sidebar and Floating instead of Left and Right. Update handleConciergePositionChange, or rename it to something like handleConciergeEntryModeChange, to write concierge_entry_mode into the settings blob instead, and keep the same localStorage plus custom event pattern already established, renaming the storage key and event name to match, for example jamm_concierge_entry_mode and jamm:concierge-entry-mode-changed.

In AppShell.tsx, read this same renamed setting the same way conciergePosition is currently read, and use it to decide which entry point actually renders: when the mode is sidebar, pass onConciergeOpen into Sidebar and do not render PersistentEntryButton at all. When the mode is floating, do not pass onConciergeOpen into Sidebar and do render PersistentEntryButton in its existing fixed bottom-6 right-6 position, since the earlier left or right corner concept is being retired entirely, floating always means the bottom right corner going forward. Default to floating when the setting is absent or not yet loaded, matching the default already used for the current setting.

Do not change ConciergePanel itself, do not change useConciergeNotifications, and do not change the ring or solid-versus-pulsing styling already finalized on PersistentEntryButton earlier tonight, only whether it renders at all.

VERIFY AFTER ACT:

grep -n "onConciergeOpen" /home/corby/jamm-os/frontend/src/components/layout/Sidebar.tsx

Expected: present again, matching the restored original.

grep -n "concierge_entry_mode\|concierge_button_position" /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

Expected: concierge_entry_mode present everywhere, concierge_button_position no longer present anywhere.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

On Settings, confirm the section now reads Sidebar and Floating, not Left and Right, and confirm the currently saved value shows correctly selected.

Select Sidebar. Confirm the floating button disappears from the corner, and confirm the original JAMM Concierge item reappears in the main left-hand navigation list, in its original position between Dark mode and Settings, and that clicking it opens the panel correctly.

Select Floating. Confirm the sidebar nav item disappears again, and the floating button reappears in the bottom right corner, working correctly.

Reload the page entirely after selecting Sidebar, confirm the choice persisted as a real firm setting, not just local UI state, matching the same persistence pattern already proven for the previous version of this setting.

Report pass or fail for all four checks individually.

GIT:

git add -A

git commit -m "replace the left/right screen corner setting with a real Sidebar-versus-Floating entry mode choice, correcting a misunderstanding of the original request, restoring the exact original sidebar Concierge navigation item from git history as the sidebar mode rather than reconstructing it from memory, and having AppShell render exactly one of the two entry points at a time based on this firm-level setting, defaulting to Floating"

git pull --rebase origin main

git push origin main