STANDING RULES
- Path comment at top of every file
- Never use && to chain commands

TASK: Fix useSearchParams Suspense boundary error on /review page

PROBLEM
Vercel build fails with:
"useSearchParams() should be wrapped in a suspense boundary at page /review"

Next.js requires any component using useSearchParams() to be wrapped
in a React Suspense boundary during static generation.

FIX
In frontend/src/app/review/page.tsx, the component using useSearchParams
needs to be split into two parts:

1. An inner component (ReviewPageInner) that contains all the current
   logic and JSX — this is the component that calls useSearchParams()

2. An outer default export (ReviewPage) that wraps ReviewPageInner
   in a Suspense boundary with a simple fallback

Replace the current default export with this pattern:

import { Suspense } from 'react'

function ReviewPageInner() {
  // ALL existing logic and JSX goes here unchanged
  // This component calls useSearchParams()
}

export default function ReviewPage() {
  return (
    <Suspense fallback={
      <div style={{
        minHeight: '100vh',
        background: '#E4E6EA',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <p style={{ fontSize: '13px', color: '#6B7280' }}>Loading...</p>
      </div>
    }>
      <ReviewPageInner />
    </Suspense>
  )
}

Move ALL existing component code (useState, useEffect, useSearchParams,
all JSX) into ReviewPageInner. The outer ReviewPage component contains
only the Suspense wrapper.

Do not change any logic, styling, or behavior — this is a structural
fix only.

After editing, do not run any build commands.