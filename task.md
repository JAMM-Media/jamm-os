## Current Task — Fix useSearchParams Suspense boundary for Vercel build

File: frontend/src/app/(auth)/login/magic/page.tsx

Next.js 16 requires useSearchParams() to be wrapped in a Suspense boundary
during static generation. The build is failing with:
"useSearchParams() should be wrapped in a suspense boundary at page /login/magic"

Fix: Wrap the component that uses useSearchParams in a Suspense boundary.

Read the file first, then apply this pattern:

1. Create an inner component that contains the useSearchParams logic
   (e.g. MagicLinkContent)
2. The default export wraps it in <Suspense fallback={...}>

Example pattern:
  function MagicLinkContent() {
    const searchParams = useSearchParams()
    // ... rest of the existing component logic
  }

  export default function MagicLinkPage() {
    return (
      <Suspense fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
        </div>
      }>
        <MagicLinkContent />
      </Suspense>
    )
  }

Import Suspense from 'react' at the top of the file.

After fixing, run:
cd frontend && npx tsc --noEmit

Report any errors. If clean, report done.