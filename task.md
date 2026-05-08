## TASK: Force portal pages to render dynamically

Next.js is prerendering /portal as a static page which breaks 
localStorage access on load.

Add this export to the TOP of each of these files, 
right after the last import line:

export const dynamic = 'force-dynamic'

Files to update:
- frontend/src/app/portal/page.tsx
- frontend/src/app/portal/auth/page.tsx
- frontend/src/app/portal/settings/page.tsx

That's the only change needed in each file. 
Run npx tsc --noEmit after and report any errors.