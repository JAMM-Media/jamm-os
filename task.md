== STANDING RULES — ENFORCE ALWAYS ==

Project: JAMM PX
Backend: FastAPI + PostgreSQL on DigitalOcean droplet, Uvicorn + Gunicorn
Frontend: Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui
All backend files start with a path comment.
All frontend files start with a path comment.
Never use && to chain commands — run them sequentially.
Never modify the database schema in this task — no migrations.
Tenant isolation is absolute — every query scoped to firm_id.
Routers are thin — no business logic in routers ever.

== TASK: Diagnose and Fix Magic Link — Staff and Portal ==

Magic links may be globally broken. There are two separate magic
link systems in the codebase:

1. Staff magic link — staff log into the app via
   /login/magic?token=... instead of password
2. Portal magic link — firm staff send a client a link to access
   their portal at /portal/auth?token=...

Both need to be diagnosed and fixed if broken. Work through all
steps in order.

== STEP 1 — DIAGNOSE STAFF MAGIC LINK END TO END ==

Read these files in full:

- app/api/auth.py (the request-magic-link and verify-magic-link
  endpoints)
- app/services/staff_magic_link.py
- frontend/src/app/(auth)/login/magic/page.tsx
- frontend/src/app/api/backend/auth/verify-magic-link/route.ts
  (if it exists — check if this Next.js proxy route exists)
- frontend/src/app/api/backend/auth/request-magic-link/route.ts
  (if it exists)

Trace the full flow:
1. User enters email on login page and requests a magic link
2. Backend generates token, stores hash, sends email with URL
3. User clicks link, lands on /login/magic?token=...
4. Frontend page reads token from URL, calls verify endpoint
5. Backend verifies hash, clears token, returns JWT
6. Frontend stores JWT and redirects to /dashboard

For each step identify whether it works correctly or has a
failure point. Specifically check:

- Does the verify-magic-link Next.js proxy route exist? If not
  this is the primary failure — the frontend calls
  /api/backend/auth/verify-magic-link but there may be no
  dedicated route, meaning the catch-all proxy handles it. Check
  whether the catch-all proxy correctly handles GET requests with
  query parameters.
- After the session timeout fix in the previous task, the
  frontend now stores access_token in localStorage and uses the
  Axios interceptor. Does the magic page correctly store the
  returned token in localStorage after verification? Check
  frontend/src/app/(auth)/login/magic/page.tsx — it currently
  calls fetch() directly, not the Axios instance. This means the
  new interceptor does not apply. The page must store the token
  in localStorage after a successful verify so the rest of the
  app can use it.
- Does the email contain the correct URL pointing to the right
  frontend domain? Check that FRONTEND_URL in the backend config
  matches the production URL.

== STEP 2 — DIAGNOSE PORTAL MAGIC LINK END TO END ==

Read these files in full:

- app/api/portal.py (the portal magic-link endpoints)
- app/services/portal_magic_link.py
- frontend/src/app/portal/auth/page.tsx (if it exists)
- frontend/src/app/api/backend/portal/auth/route.ts (if it
  exists)

Trace the full portal magic link flow:
1. Staff member clicks Send Portal Link on client detail page
2. Backend generates token, stores hash on PortalSession,
   sends email to client with URL
3. Client clicks link, lands on /portal/auth?token=...
4. Frontend reads token, calls exchange endpoint
5. Backend verifies hash, clears token, returns portal JWT
6. Frontend stores portal JWT and redirects to portal home

Check the same failure points as Step 1 — missing proxy routes,
token not stored correctly, wrong URL in email.

== STEP 3 — FIX ALL IDENTIFIED ISSUES ==

Fix every failure point identified in Steps 1 and 2. Common
fixes needed:

FIX A — Staff magic link page not storing token in localStorage
If frontend/src/app/(auth)/login/magic/page.tsx calls fetch()
and then does localStorage.setItem('access_token', ...) only on
success but the key or storage call is wrong, fix it. The page
must store the token under the key 'access_token' in localStorage
after a successful verify response, then redirect to /dashboard.
This is consistent with how the new Axios interceptor expects
to find the token.

FIX B — Missing Next.js proxy routes
If the catch-all proxy at
frontend/src/app/api/backend/[...path]/route.ts handles GET
requests with query parameters correctly, no dedicated route is
needed. Verify this by reading the catch-all proxy. If it does
not forward query parameters, create dedicated routes:
- frontend/src/app/api/backend/auth/verify-magic-link/route.ts
- frontend/src/app/api/backend/portal/auth/route.ts
Each route must forward all query parameters to the backend and
return the response body and status unchanged.

FIX C — Portal auth page missing or broken
If frontend/src/app/portal/auth/page.tsx does not exist or does
not correctly store the portal JWT and redirect to the portal
home, fix or create it. The portal uses a separate token key —
check what key the portal currently uses for its JWT (look for
how the portal reads its token in portal page components) and
store the returned token under that same key.

FIX D — Wrong FRONTEND_URL in email
If the magic link URL in the email points to localhost or the
wrong domain, the backend is reading FRONTEND_URL from the
environment incorrectly. Do not hardcode the URL — flag this for
Andrew to verify the FRONTEND_URL environment variable on the
droplet matches https://app.jammpx.com.

== STEP 4 — VERIFY ==

After all fixes:

1. List every file created or modified and what changed
2. Trace the staff magic link flow end to end in plain English
   confirming each step now works
3. Trace the portal magic link flow end to end in plain English
   confirming each step now works
4. Flag anything that requires Andrew to verify on the server
   (environment variables, email delivery) that cannot be
   confirmed from code alone

Do not restart any services — Andrew will handle deployment.