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

TASK: Refactor ConciergePanel.tsx onto the token system and give it real visual identity, phase 2 of 2 visual redesign

USE: Fable 5

VERIFY BEFORE ACT:
grep -c "bg-\[#\|text-\[#\|border-\[#" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
cat /home/corby/jamm-os/frontend/src/app/globals.css
grep -n "revealedWordCount\|revealSession\|_STAFF_CONCIERGE\|parsedDraft\|msg.options\|stripTrailingMarkers" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | wc -l

Read the entire file in full before changing a single line. This file has been through many separate, hard-won fixes tonight: the reveal animation system, four separate trailing marker types, batch drafting, staff role scoping, dark mode contrast. This task must not touch any state, any logic, any function body, any conditional behavior, only visual presentation, class names, and static JSX structure. If you are unsure whether something is presentational or logical, treat it as logical and do not touch it.

WHAT THIS IS:

Phase 1 replaced the app's generic Inter typography with a distinctive serif and sans pairing, Lora and Plus Jakarta Sans, and refined the core color tokens toward a warmer palette, confirmed working cleanly across the rest of the app with no regressions. This file was deliberately excluded from phase 1 because it hardcodes a large number of raw hex color values directly in its className strings, bypassing the token system entirely, confirmed by the count returned in the first verify command. This means phase 1's changes never reached this file at all, it still looks exactly as it did before. This task has two goals: refactor these hardcoded hex values to reference the real design tokens so this panel is finally consistent with the rest of the redesigned app, and give the panel deliberate visual identity as the smart, differentiated layer of the product, using the concierge accent color token added in phase 1 specifically for this purpose and not used anywhere else yet.

CHANGE INSTRUCTIONS:

Replace hardcoded hex values throughout this file with the equivalent real token classes already defined in globals.css and tailwind.config.ts, such as bg-surface-card, text-brand, bg-dark-card, and so on, matching each hardcoded value to its closest real token rather than inventing new arbitrary values. Where light and dark mode variants both currently exist as separate hardcoded hex pairs, they should become a single token class that already handles both modes correctly through the existing dark variant system, do not keep them as two separate arbitrary hex values.

Apply the new display serif font, using the font-display utility class added in phase 1, to the panel's own header title, to bolded key figures inside message content such as dollar amounts and counts, currently rendered through the existing strong markdown renderer, and to the JC avatar initials, so the panel's own voice reads as distinctly considered rather than sharing the exact same typography as plain UI chrome elsewhere.

Use the concierge accent color token, added specifically for this purpose in phase 1, deliberately and sparingly, not as a wholesale color replacement. Good candidates: the avatar circle's background or a ring around it, a subtle border or accent line on the panel's own container distinguishing it visually from a plain flat page panel, and the streaming pulse or thinking indicator. Do not apply this accent color broadly across every button or every interactive element, it should read as special specifically because it appears rarely and deliberately.

Give the panel real elevation and visual weight distinguishing it from a flat, generic side panel, such as a genuine shadow, a subtle background treatment distinct from the surrounding page background, or a considered border treatment, appropriate to a refined, non-maximalist aesthetic given this is a trust focused financial product, not a loud or decorative one.

Do not change the avatar's actual content logic, only its visual styling. Do not change any spacing or layout structure in a way that could affect where the reveal animation's word count boundary falls or how draft cards, option buttons, or the suggestion chip row are positioned relative to their messages, only update their color and typography treatment.

VERIFY AFTER ACT:

grep -c "bg-\[#\|text-\[#\|border-\[#" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: a significantly lower count than the number found in the before check, ideally at or near zero, confirming real token migration happened, not just a few changes.

npm run build in frontend, expected zero TypeScript errors.

diff the actual logic sections against what they were before by confirming these specific patterns are byte for byte unchanged: the tick function inside the reveal animation effect, the stripTrailingMarkers function, the parseDraftFromResponse function, and the _STAFF_CONCIERGE_TOOLS related conditional rendering if any exists client side. Paste a diff or explicit confirmation that these specific logic blocks were not touched.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

This is a full regression sweep of every major feature this file has carried tonight, not just a visual check. Go through every one of these and report pass or fail individually, do not summarize:

1. Ask a longer question and confirm the word by word reveal animation still works smoothly, not instant, not blank, not stuck.
2. Ask which clients have overdue invoices right now, confirm the clickable client option buttons still render correctly and are still clickable.
3. Click one of those options, confirm a real, correctly personalized draft still generates with no placeholder text.
4. Ask for drafts for all qualifying clients, confirm multiple distinct draft cards still render correctly, not merged or broken.
5. Click Open to send on a draft, confirm the confirmation modal still appears correctly with accurate content.
6. Ask a question that should produce a topic suggestion chip, confirm it still appears correctly positioned below its message, not above.
7. Switch to dark mode, confirm all of the above still look correct and remain fully readable, this is the single most important check given how much effort dark mode contrast took to get right earlier tonight.
8. Confirm the panel now visually looks distinctly different from a flat generic page panel, with real identity, not just recolored.

Report pass or fail individually for all eight, with a screenshot of the panel in both light and dark mode.

GIT:
git add -A
git commit -m "phase 2 of 2 visual redesign: refactor ConciergePanel.tsx off hardcoded hex values onto the real design token system established in phase 1, apply the new display serif to the panel's own headers and key figures, and introduce the reserved concierge accent color deliberately and sparingly for the panel's visual identity, giving it real elevation and presence as the product's differentiated smart layer, with zero changes to any state, logic, or function body, confirmed through full regression testing of the reveal animation, draft generation, batch drafting, option buttons, and dark mode contrast"
git pull --rebase origin main
git push origin main