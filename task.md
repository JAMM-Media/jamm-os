## Current Task — Fix TypeScript error in documents page for Vercel build

File: frontend/src/app/documents/page.tsx

Build error:
Type error: Type '{ documents: Document[]; view: "table"; onUpload: () => void | undefined; }'
is not assignable to type 'IntrinsicAttributes & DocumentTableProps'.
Property 'view' does not exist on type 'IntrinsicAttributes & DocumentTableProps'.

Read both files:
- frontend/src/app/documents/page.tsx
- frontend/src/components/documents/DocumentTable.tsx

The DocumentTable component doesn't accept a 'view' prop but the page
is passing one. Fix by removing the view prop from the DocumentTable
usage in documents/page.tsx.

After fixing run:
cd frontend && npx tsc --noEmit

If there are more errors fix them all. Report every file changed
and the final tsc output.