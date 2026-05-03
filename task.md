## Current Task — Fix useSearchParams Suspense boundary on portal auth page

File: frontend/src/app/portal/auth/page.tsx

Same issue as login/magic/page.tsx — useSearchParams() needs a Suspense boundary.

Apply the same pattern:
1. Read the file
2. Extract the component body into an inner component (e.g. PortalAuthContent)
3. Wrap it in Suspense in the default export

Import Suspense from 'react' and Loader2 from 'lucide-react' if not already imported.

Use this fallback:
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </div>
    }>

After fixing, run:
cd frontend && npx tsc --noEmit

Also search for any other pages that use useSearchParams() and apply the same
fix to all of them. Report every file fixed.