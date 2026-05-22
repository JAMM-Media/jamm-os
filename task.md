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

== TASK: Fix Session Timeout — Staff JWT and Silent Refresh ==

The staff side of JAMM PX is kicking users out after approximately
30-60 minutes. There is a refresh token system in place that should
silently renew the access token before it expires, but it is not
working correctly. This task fixes the root cause and adds a
belt-and-suspenders config change.

Do all four steps in order. Report findings after Step 1 before
proceeding if anything unexpected is found.

== STEP 1 — DIAGNOSE THE SILENT REFRESH INTERCEPTOR ==

Read the following files in full before making any changes:

- frontend/src/lib/api.ts
- frontend/src/lib/hooks/useAuth.ts
- frontend/src/app/api/backend/auth/refresh/route.ts (if it exists)
- Any Next.js API route under frontend/src/app/api/backend/auth/

Look for the Axios interceptor that handles 401 responses. It should:
1. Catch a 401 from any API call
2. Call the /auth/refresh endpoint using the jamm_refresh_token cookie
3. Retry the original request with the new access token
4. Redirect to /login only if refresh fails

Report exactly what the interceptor currently does. Common failure
modes to check for:
- The interceptor exists but is never registered (not imported in
  the right place)
- The interceptor makes the refresh call but does not retry the
  original request
- The refresh API route does not correctly forward the
  jamm_refresh_token cookie to the backend
- The interceptor triggers an infinite loop on the /auth/refresh
  endpoint itself (refresh failing causes another 401 which
  triggers another refresh attempt)

== STEP 2 — FIX THE SILENT REFRESH INTERCEPTOR ==

Based on the diagnosis in Step 1, fix the interceptor so it works
correctly. The correct behavior is:

1. Every Axios request goes out normally
2. If a 401 comes back AND the request was not itself to
   /auth/refresh:
   a. Call POST /api/backend/auth/refresh (the Next.js route that
      proxies to the backend)
   b. If refresh succeeds: store the new access_token in
      localStorage under the key 'access_token', then retry the
      original failed request once with the new token in the
      Authorization header
   c. If refresh fails (401 or any error): clear localStorage,
      redirect to /login
3. If a 401 comes back from /auth/refresh itself: clear
   localStorage, redirect to /login — do not retry

Make sure the interceptor is only registered once. If useAuth or
api.ts both try to register interceptors, consolidate so there is
exactly one 401 interceptor on the Axios instance.

The Next.js API route at
frontend/src/app/api/backend/auth/refresh/route.ts must:
- Accept POST requests
- Forward the jamm_refresh_token cookie from the browser to the
  backend POST /auth/refresh endpoint
- Return the new access_token in the JSON response body
- Forward the new jamm_refresh_token Set-Cookie header from the
  backend response back to the browser

If this route does not exist, create it.

== STEP 3 — EXTEND JWT AND MAGIC LINK EXPIRY IN CONFIG ==

Belt-and-suspenders fix alongside the interceptor repair.

File: app/core/config.py

Change:
  ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
To:
  ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

This sets the staff JWT to 8 hours. Even if the silent refresh
has an edge case, a firm owner will not be kicked out mid-workday.

File: app/services/staff_magic_link.py

Change:
  _MAGIC_LINK_EXPIRY_MINUTES = 15
To:
  _MAGIC_LINK_EXPIRY_MINUTES = 30

The 15-minute window is too short. Email delivery can take a few
minutes and users do not always click immediately. 30 minutes is
the industry standard for magic link expiry.

== STEP 4 — VERIFY ==

After all changes:

1. Confirm app/core/config.py shows ACCESS_TOKEN_EXPIRE_MINUTES = 480
2. Confirm app/services/staff_magic_link.py shows
   _MAGIC_LINK_EXPIRY_MINUTES = 30
3. Confirm the Axios interceptor is registered exactly once
4. Confirm the /api/backend/auth/refresh Next.js route exists and
   correctly forwards cookies in both directions
5. Print a summary of every file modified and what changed in
   each one

Do not restart any services — Andrew will handle deployment.