## STANDING RULES
- No migrations
- Routers are thin
- Every file starts with a path comment

## TASK: Fix portal/auth page — exchange magic link token on load

File: frontend/src/app/portal/auth/page.tsx

Read the file first and report its current contents before making any changes.

The page currently shows a login form. When the URL contains a ?token= 
query parameter, the page must exchange it for a portal JWT before 
rendering anything else.

Add a useEffect that runs on mount:
1. Read the token from the URL: new URLSearchParams(window.location.search).get('token')
2. If a token exists, call GET /api/backend/portal/auth?token={token}
3. On success: store the returned access_token in localStorage as 
   'portal_access_token', then redirect to /portal
4. On failure: show an error message "This link has expired. Please 
   request a new one." and render the login form normally
5. While the exchange is in flight, show a loading spinner — do not 
   render the login form yet

If no token is in the URL, render the login form as normal.

The exchange endpoint is GET /api/backend/portal/auth?token={token}
It returns: { access_token: string, token_type: string }

Do not change anything else about the login form behavior.

After the fix run: npx tsc --noEmit in the frontend directory.
Report every change made.