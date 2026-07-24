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

TASK: Replace generic Inter typography and refine the core color tokens, foundational visual redesign phase 1 of 2

USE: Fable 5

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/frontend/src/app/globals.css
cat /home/corby/jamm-os/frontend/tailwind.config.ts
sed -n '1,20p' /home/corby/jamm-os/frontend/src/app/layout.tsx

Read all of this in full before changing anything. This is the foundational layer every other page in the app builds on, mistakes here have the widest possible blast radius of anything touched tonight.

WHAT THIS IS:

The app currently uses Inter as its only font, loaded at only weights 400 and 500, meaning anything using font-semibold or heavier has been relying on the browser synthesizing bold rather than a real bold weight being loaded at all. Inter is also explicitly one of the most overused, generic typefaces in software right now, contributing to the product currently reading as a templated, forgettable SaaS admin panel rather than something considered and distinctive, confirmed as a real, specific problem worth fixing, not just a vague feeling. Separately, the existing color tokens are well organized structurally, properly split between light and dark mode, but the actual chosen values are extremely conventional, a navy brand color and cool gray surfaces, and the one accent color, brand-light at #4A7FA5, is used so evenly across every interactive element that nothing feels special or specifically JAMM.

This is phase 1 of 2, deliberately scoped to only the central design tokens and font loading, not any individual component. A separate, later task will refactor ConciergePanel.tsx specifically to actually use these updated tokens and receive real visual hero treatment, since that file currently bypasses the token system with hardcoded hex values throughout and needs its own careful, isolated pass given how many separate fixes it has gone through tonight.

CHANGE INSTRUCTIONS:

Replace the Inter font entirely. Load two fonts via next/font/google in layout.tsx: a distinctive serif or slab serif with real character, appropriate for a professional financial product, something considered and warm rather than decorative or playful, used for headings, page titles, and key figures such as dollar amounts, and a clean, warmer humanist sans serif, not Inter, Roboto, or Arial, and not Space Grotesk, used for body text and UI labels. Load real weight ranges for both, including genuine bold weights, not just 400 and 500. Make a real, considered choice for both fonts rather than defaulting to the first plausible option, this should feel deliberately chosen for a trust focused financial product, not generic.

Update the --font-sans token in globals.css and the fontFamily entry in tailwind.config.ts to reference the new sans serif font's CSS variable. Add a new --font-serif or --font-display token following the same pattern, referencing the new serif font's CSS variable, and add a matching fontFamily entry in tailwind.config.ts so it is usable as a Tailwind utility class such as font-serif or font-display throughout the app going forward.

Refine the actual color values, keeping the existing token structure and naming exactly as is, brand, surface, dark, status, only changing the underlying hex and hsl values. Deepen the neutral surface colors in both light and dark mode away from flat, generic cool gray toward something warmer and richer with more depth, while maintaining strong, accessible contrast in both modes. Keep the navy brand color as the primary brand identity, it is appropriate for this audience, but introduce one new, genuinely distinctive secondary accent color, used deliberately and sparingly rather than repeated everywhere the way brand-light currently is, intended specifically for moments that should feel special or specifically tied to the Concierge's own identity, to be applied in the phase 2 task, not this one. Update both the @theme token block and the shadcn-style HSL variable block in :root and .dark to stay consistent with each other, since components elsewhere in the app depend on both systems being in sync.

Do not touch any component file in this task, not ConciergePanel.tsx, not any page under frontend/src/app, not any file under frontend/src/components. This task only touches globals.css, tailwind.config.ts, and layout.tsx.

VERIFY AFTER ACT:

npm run build in frontend, expected zero TypeScript errors.

grep -n "font-serif\|font-display" /home/corby/jamm-os/frontend/tailwind.config.ts

Expected: present, confirming the new font utility is actually usable.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

Load the app in light mode, visually confirm the new fonts are actually rendering, not falling back to a system font silently, check a page title and check body text specifically. Switch to dark mode, confirm the same, and confirm text remains clearly readable with strong contrast in dark mode, this was a real, hard-won fix earlier tonight and must not regress.

Navigate through at least four or five different real pages, Dashboard, Clients, Engagements, Billing, Staff, and visually confirm nothing looks broken, misaligned, or illegible as a result of the token value changes, since roughly half the app's pages already correctly use these tokens and will visually change immediately.

Open the Concierge panel specifically and confirm it still functions correctly, sends messages, receives responses, since this task should not have touched its logic at all, only confirm no visual regression occurred as a side effect of the shared token changes, deeper visual treatment for this panel specifically is intentionally deferred to phase 2.

Report pass or fail for light mode rendering, dark mode rendering and contrast, the five page visual sweep, and the Concierge panel functioning correctly with no regressions.

GIT:
git add -A
git commit -m "phase 1 of 2 visual redesign: replace generic Inter typography with a distinctive serif and sans pairing loaded at real weight ranges, and refine the core color token values toward a warmer, more considered palette while preserving the existing token structure, scoped deliberately to only globals.css, tailwind.config.ts, and layout.tsx, no component files touched, phase 2 will refactor ConciergePanel.tsx specifically to use these tokens and receive real visual hero treatment"
git pull --rebase origin main
git push origin main