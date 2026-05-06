## Current Task — Fix middleware to allow favicon.svg

File: frontend/middleware.ts

Two changes needed:

1. Add '/favicon.svg' and '/logo.svg' to the PUBLIC_PATHS array

2. Update the matcher regex to also exclude .svg files in the
   public directory. Change:
   '/((?!_next/static|_next/image|favicon\\.ico).*)'
   To:
   '/((?!_next/static|_next/image|favicon\\.ico|favicon\\.svg|logo\\.svg).*)'

No tsc check needed. No pytest needed. Just make the change and report back.