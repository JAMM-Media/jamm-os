# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment

---

# TASK: Replace native browser tooltip on HealthDot with proper multi-line tooltip

## What this does
The HealthDot component currently uses the native browser `title` attribute
for its tooltip. This renders as a plain text string — multiple reasons joined
with \n are not reliably displayed as separate lines in most browsers. The fix
replaces the native title attribute with the shadcn Tooltip component that is
already installed and already used in IrsAuthBadge.tsx in the same folder.

After this change, hovering the health dot shows a clean styled tooltip with
each reason on its own line, preceded by a bullet dot.

Frontend only. One file. No backend changes.

---

## File to modify
`frontend/src/components/clients/HealthDot.tsx`

---

## Full replacement

Replace the entire file contents with the following:

```tsx
// frontend/src/components/clients/HealthDot.tsx
'use client'

import { useQuery } from '@tanstack/react-query'
import { clientsApi } from '@/lib/api/clients'
import type { ClientHealth } from '@/lib/api/clients'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip'

const STATUS_CONFIG = {
  healthy: { color: '#10B981', label: 'Healthy' },
  needs_attention: { color: '#F59E0B', label: 'Needs Attention' },
  at_risk: { color: '#E24B4A', label: 'At Risk' },
} as const

interface HealthDotProps {
  clientId: string
  showLabel?: boolean
}

export function HealthDot({ clientId, showLabel = false }: HealthDotProps) {
  const { data, isLoading, isError } = useQuery<ClientHealth>({
    queryKey: ['client-health', clientId],
    queryFn: () => clientsApi.getHealth(clientId),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  if (isError) return null

  const config = data
    ? STATUS_CONFIG[data.status as keyof typeof STATUS_CONFIG] ?? null
    : null
  const color = isLoading || !config ? '#C8CDD6' : config.color

  const hasReasons = data && data.reasons.length > 0

  const dot = (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        flexShrink: 0,
      }}
    />
  )

  const trigger = showLabel ? (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 12,
        color: isLoading || !config ? '#C8CDD6' : config.color,
        cursor: hasReasons ? 'default' : undefined,
      }}
    >
      {dot}
      {!isLoading && config && config.label}
    </span>
  ) : (
    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
      {dot}
    </span>
  )

  // No reasons — healthy or still loading — just render the dot/label with no tooltip
  if (!hasReasons) {
    return trigger
  }

  // Has reasons — wrap in tooltip showing each reason on its own line
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          {trigger}
        </TooltipTrigger>
        <TooltipContent
          side="right"
          className="max-w-[240px]"
        >
          <div className="flex flex-col gap-1">
            {data.reasons.map((reason, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <span
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: '50%',
                    backgroundColor: color,
                    flexShrink: 0,
                    marginTop: 5,
                  }}
                />
                <span className="text-[11px] leading-tight">{reason}</span>
              </div>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
```

---

## What changed and why

The old implementation used `title={tooltip}` where tooltip was
`data.reasons.join('\n')`. Browser native title tooltips:
- Do not reliably render newlines as separate lines across browsers
- Have no styling control — plain OS-rendered text
- Cannot show bullet points or structured layout

The new implementation uses the shadcn Tooltip component (already installed,
already imported in IrsAuthBadge.tsx in the same folder). Each reason renders
as its own row with a small colored dot matching the health status color.
The tooltip appears on the right side of the dot (side="right") to avoid
being clipped at the left edge of the screen.

The healthy state (no reasons) renders with no tooltip at all — nothing to
show, no tooltip wrapper needed.

---

## Verification

1. Deploy frontend (git push — Vercel auto-deploys)
2. Navigate to any client with a non-healthy status
3. Hover the colored dot next to the client name on the detail page
4. Confirm a styled tooltip appears showing each reason on its own line
   with a bullet dot
5. Navigate to the clients list and hover health dots on client cards/rows
   — same tooltip should appear there too (HealthDot is used in both places)
6. A healthy client (green dot) should show no tooltip on hover

---

## Files to modify
- frontend/src/components/clients/HealthDot.tsx — full file replacement
