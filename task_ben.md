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

TASK: Shift the core surface palette from warm to cool toned, matching a validated financial-trust research finding

USE: Fable 5

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/frontend/src/app/globals.css
grep -rl "bg-surface-page\|bg-surface-card\|bg-dark-page\|bg-dark-card" /home/corby/jamm-os/frontend/src --include="*.tsx" | wc -l

Read the full token file completely. The second command shows roughly how many files across the whole application will be affected by this change purely through the token system, with zero individual file edits required, confirming this is the real payoff of migrating ConciergePanel.tsx, the Dashboard, and the client detail page onto tokens earlier tonight rather than leaving them hardcoded.

WHAT THIS IS:

Tonight's redesign originally shifted the core surface palette warmer, based on instinct rather than research. A controlled study on cyber-banking interface trust, Kim and Moon, found the highest measured trust scores came from a specific, different combination: pastel, low brightness, cool toned color, set against a colored, non-white or non-neutral-gray background, not a warm palette. A live audit of the shipped warm palette separately described it as reading sterile rather than considered, which in hindsight likely was not actually a temperature problem, flat, low-saturation gray fails on either side of warm versus cool, the real fix is genuine color and adequate separation between page and card surfaces, which this change should achieve regardless of hue. A real side by side comparison of the current warm palette against a cool alternative was built and reviewed directly, and the cool alternative was the clear, deliberate choice, not a guess.

CHANGE INSTRUCTIONS:

In globals.css, replace the light mode surface tokens with these specific target values, adjusting only as needed for accessible contrast, not for taste: color-surface-page around #D6DEE6, color-surface-card around #E9EEF3, color-surface-border around #C2CDD8, color-surface-input a touch lighter than card. These were already reviewed and approved directly against the current warm palette in a real side by side comparison, use them as the actual target, not just inspiration. In HSL terms, this means a hue in the 205 to 215 range, saturation in the 20 to 30 percent range, and lightness in the 82 to 90 percent range for the page and card tones, genuinely cool and pastel, not neutral gray with no hue at all.

For dark mode, apply the same cool hue family, roughly 205 to 215, at appropriately low lightness for a dark theme, replacing the current warm charcoal tokens, color-dark-page, color-dark-card, color-dark-border, color-dark-sidebar, with genuinely cool-toned dark equivalents rather than warm ones, while preserving strong, accessible contrast against light text.

Update the corresponding shadcn style HSL variables in the root and dark blocks to these same real values, keeping both systems in sync exactly as was done previously tonight.

Update tailwind.config.ts surface and dark color values to match exactly, byte for byte consistent with globals.css.

Do not change the brand navy tokens, the concierge accent gold token, or any of the status tokens, red, green, blue, amber. This task is scoped only to the neutral surface palette.

Do not touch any component file directly. This change must work entirely through the token system, proving the migration work done earlier tonight on ConciergePanel.tsx, the Dashboard, and the client detail page was worth doing.

VERIFY AFTER ACT:

npm run build in frontend, expected zero TypeScript errors.

Confirm real, calculated contrast ratios between the new page and card background values, and between text and background pairings, meet at minimum WCAG AA standards in both light and dark mode, paste the actual computed ratios, do not simply assert they look fine.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

This is a real regression sweep across everything already migrated onto the token system tonight, not a fresh build, report pass or fail individually for each:

1. The Concierge panel, light and dark mode, confirm the gold accent bar, avatar, and elevation still read correctly against the new cool background.
2. The Dashboard, light and dark mode, confirm all four stat cards including the Overdue Engagements alert-tinted card remain clearly legible and appropriately distinct from the new background.
3. The client detail page and all five of its tabs, Overview, Notes, IRS Authorizations, Documents, Portal, light and dark mode, confirm full legibility and confirm status color coding remains clearly distinguishable against the new surface tones.
4. Navigate through at least three other real pages not yet individually redesigned, and confirm the automatic token cascade did not produce any illegible or badly contrasted result anywhere, since these pages will also inherit the new values automatically.

Report pass or fail individually for all four checks, with screenshots of the Concierge panel and the Dashboard in both light and dark mode at minimum.

GIT:
git add -A
git commit -m "shift the core surface palette from warm to cool toned, pastel, and low brightness, implementing a validated financial-trust research finding directly, replacing an earlier warm palette choice that was based on instinct rather than evidence, verified with real computed contrast ratios and a full regression sweep across every surface already migrated onto the token system"
git pull --rebase origin main
git push origin main