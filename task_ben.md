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

TASK: Remove Smart Paste, give the header real identity, differentiate the trash icon at rest, and replace the raw browser tooltip on Autopilot

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '1580,1610p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
sed -n '955,1015p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "title=" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Read the full header row and the full Smart Paste block in context before touching anything, including whatever triggers Smart Paste to open, such as a clipboard icon button elsewhere in the file, so it can be removed cleanly with no dangling reference.

WHAT THIS IS:

Four small, real findings from a direct visual review of the panel after the phase 1 and phase 2 redesign work. First, Smart Paste no longer serves a clear purpose and should be removed entirely, along with whatever button or icon currently triggers it. Second, the JAMM Concierge header reads as a plain text label with no more visual weight than the buttons next to it, undercutting the identity work already done elsewhere in this panel. Third, the trash can icon, which correctly triggers a real confirm dialog before clearing a conversation, looks visually identical at rest to the harmless close button right next to it, a destructive action and a harmless one should not share identical visual weight before the user even interacts with either. Fourth, hovering Autopilot currently shows the raw, unstyled native browser tooltip, a plain black box in a system font, which clashes directly with the warm, considered typography and color work done in phases 1 and 2.

CHANGE INSTRUCTIONS:

Remove the Smart Paste form block entirely, along with its trigger button and any state variables that exist solely to control it. Confirm nothing else in the file references this state after removal.

Give the JAMM Concierge header real visual identity, pairing the existing font-display treatment on the text with a small, considered mark or icon, using the concierge accent color already established for the panel's identity, so the header reads as a named product moment, not a plain UI label. Keep this restrained and small, this is a refinement, not a redesign of the header layout.

Give the trash icon a subtle distinct visual treatment at its resting state, not only on hover, such as a slightly different muted tone leaning toward its existing hover warning color rather than being visually identical to the neutral close button beside it. Do not change or remove the existing confirm dialog safeguard in handleClearConversation, that logic is correct and already in place, this is purely a visual distinction so the two icons do not look interchangeable before a user even interacts with them.

Replace the native title attribute tooltip on the Autopilot toggle with a properly styled custom tooltip consistent with the rest of the redesigned panel, using the existing warm surface and border tokens and correct typography, positioned clearly without obstructing nearby content. Preserve the exact existing tooltip copy, when on I will navigate the app and open forms for you automatically, when off I will just tell you where to go, do not reword it, only restyle its presentation.

Do not change any state, logic, or functional behavior anywhere in this task beyond removing the Smart Paste feature's own dead state, every other change is purely visual and structural JSX, not behavioral.

VERIFY AFTER ACT:

grep -n "Smart Paste" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: no matches remaining.

npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

Confirm Smart Paste and its trigger are genuinely gone with no leftover empty space or broken button. Confirm the JAMM Concierge header now shows a real, considered identity mark, in both light and dark mode. Confirm the trash icon now looks visually distinct from the close button at rest, not just on hover, and confirm clicking it still correctly triggers the existing confirm dialog before clearing anything. Hover Autopilot and confirm the tooltip is now styled consistent with the rest of the panel, not the raw black browser default, with the exact same copy as before.

Report pass or fail individually for all four changes, with screenshots in both light and dark mode.

GIT:
git add -A
git commit -m "remove Smart Paste, give the JAMM Concierge header real identity treatment with the panel's established accent color, visually differentiate the destructive trash icon from the harmless close button at rest without changing the existing confirm dialog safeguard, and replace the raw native browser tooltip on Autopilot with a properly styled tooltip consistent with the rest of the redesigned panel"
git pull --rebase origin main
git push origin main