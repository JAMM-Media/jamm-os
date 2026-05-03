## Current Task — Fix TypeScript type error blocking Vercel build

File: frontend/src/app/engagements/[id]/page.tsx

Around line 375 there is this code:
    engagement={engagement}

The Engagement type has engagementType as string | null but the
EditEngagementModal expects string | undefined.

Fix by spreading the engagement object and converting null to undefined:
    engagement={{
      ...engagement,
      engagementType: engagement.engagementType ?? undefined,
      endDate: engagement.endDate ?? undefined,
      description: engagement.description ?? undefined,
    }}

Make this change, then run:
cd frontend && npx tsc --noEmit

Report any remaining TypeScript errors. Fix them all using the same
null-to-undefined pattern before reporting back.