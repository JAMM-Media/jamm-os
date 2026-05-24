// frontend/src/components/portal/PortalTodo.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileUp, PenLine, CreditCard, CheckCircle2 } from 'lucide-react'
import { getPortalDashboard } from '@/lib/portal-api'
import type { PortalDashboard } from '@/lib/portal-api'

interface ActionItem {
  id: string
  type: 'document-request' | 'signature' | 'invoice'
  title: string
  description: string
  dueDate?: string
  completed: boolean
}

function getIcon(type: ActionItem['type'], iconColor: string) {
  if (type === 'document-request') return <FileUp className="h-5 w-5" style={{ color: iconColor }} />
  if (type === 'signature') return <PenLine className="h-5 w-5" style={{ color: iconColor }} />
  return <CreditCard className="h-5 w-5" style={{ color: iconColor }} />
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function EngagementBadge({ status, accentColor }: { status: string; accentColor: string }) {
  const getStyle = (): React.CSSProperties => {
    switch (status) {
      case 'active':
      case 'in_progress':
        return { backgroundColor: accentColor + '33', color: accentColor, border: `1px solid ${accentColor}66` }
      case 'completed':
        return { backgroundColor: '#D1FAE5', color: '#065F46' }
      case 'overdue':
      case 'blocked':
        return { backgroundColor: '#FEE2E2', color: '#991B1B' }
      case 'planning':
      case 'draft':
      case 'pending':
      default:
        return { backgroundColor: accentColor + '22', color: accentColor, border: `1px solid ${accentColor}44` }
    }
  }
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-[4px] capitalize"
      style={getStyle()}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function ActionCard({ item, accentColor, cardColor, primaryText, mutedText, iconColor }: {
  item: ActionItem
  accentColor: string
  cardColor: string
  primaryText: string
  mutedText: string
  iconColor: string
}) {
  return (
    <div
      className="flex items-center justify-between gap-4 rounded-[8px] px-5 py-4"
      style={{ backgroundColor: cardColor, opacity: item.completed ? 0.7 : 1 }}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="flex-shrink-0 mt-0.5">{getIcon(item.type, iconColor)}</div>
        <div className="min-w-0">
          <p className="text-[14px] font-medium leading-tight" style={{ color: primaryText }}>{item.title}</p>
          <p className="text-[13px] mt-0.5 leading-snug" style={{ color: mutedText }}>{item.description}</p>
          {item.dueDate && !item.completed && (
            <p className="text-[13px] mt-1" style={{ color: mutedText }}>Due {item.dueDate}</p>
          )}
        </div>
      </div>
      {item.completed ? (
        <CheckCircle2 className="h-5 w-5 text-[#10B981] flex-shrink-0" />
      ) : (
        <button
          className="flex-shrink-0 h-10 px-4 rounded-[6px] text-white text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap"
          style={{ backgroundColor: accentColor }}
        >
          {item.type === 'document-request'
            ? 'Upload'
            : item.type === 'signature'
            ? 'Review & Sign'
            : 'Pay Now'}
        </button>
      )}
    </div>
  )
}

interface PortalTodoProps {
  clientFirstName: string
  accentColor?: string
  cardColor?: string
  portalMode?: 'light' | 'dark'
}

export function PortalTodo({ clientFirstName, accentColor = '#3A6A94', cardColor = '#383838', portalMode = 'dark' }: PortalTodoProps) {
  const primaryText = portalMode === 'light' ? '#1F3148' : '#EDEEF0'
  const mutedText = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
  const iconColor = portalMode === 'light' ? '#6B7280' : '#9CA3AF'

  const [items, setItems] = useState<ActionItem[]>([])
  const [engagements, setEngagements] = useState<PortalDashboard['active_engagements']>([])
  const [loading, setLoading] = useState(true)

  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getPortalDashboard()

      const mapped: ActionItem[] = [
        ...data.pending_document_requests.map((dr) => ({
          id: dr.id,
          type: 'document-request' as const,
          title: dr.title ?? 'Document Request',
          description: 'Please upload the requested documents.',
          dueDate: dr.due_date ?? undefined,
          completed: dr.status === 'approved',
        })),
        ...data.pending_signatures.map((sig) => ({
          id: sig.id,
          type: 'signature' as const,
          title: 'Signature Required',
          description: sig.sent_at
            ? `Sent ${formatDate(sig.sent_at)} — please review and sign.`
            : 'Please review and sign the document.',
          completed: sig.status === 'signed' || sig.status === 'completed',
        })),
      ]
      setItems(mapped)
      setEngagements(data.active_engagements)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboard()
  }, [fetchDashboard])

  const active = items.filter((i) => !i.completed)
  const completed = items.filter((i) => i.completed)

  if (loading) {
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-[8px] animate-pulse" style={{ backgroundColor: cardColor }} />
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 flex flex-col gap-6 max-w-2xl mx-auto">
      <div>
        <p className="text-[18px] font-medium" style={{ color: primaryText }}>Hello, {clientFirstName}</p>
        <p className="text-[14px] mt-0.5" style={{ color: mutedText }}>
          {active.length === 0
            ? "You're all caught up."
            : `You have ${active.length} item${active.length !== 1 ? 's' : ''} that need${active.length === 1 ? 's' : ''} your attention.`}
        </p>
      </div>

      {active.length > 0 && (
        <div>
          <p className="text-[12px] font-medium uppercase tracking-[0.05em] mb-2" style={{ color: mutedText }}>
            Action needed
          </p>
          <div className="flex flex-col gap-3">
            {active.map((item) => (
              <ActionCard key={item.id} item={item} accentColor={accentColor} cardColor={cardColor} primaryText={primaryText} mutedText={mutedText} iconColor={iconColor} />
            ))}
          </div>
        </div>
      )}

      {engagements.length > 0 && (
        <div>
          <p className="text-[12px] font-medium uppercase tracking-[0.05em] mb-2" style={{ color: mutedText }}>
            Active engagements
          </p>
          <div className="flex flex-col gap-3">
            {engagements.map((eng) => (
              <div
                key={eng.id}
                className="flex items-center justify-between rounded-[8px] px-4 py-3"
                style={{ backgroundColor: cardColor }}
              >
                <p className="text-[14px] font-medium" style={{ color: primaryText }}>{eng.name}</p>
                <EngagementBadge status={eng.status} accentColor={accentColor} />
              </div>
            ))}
          </div>
        </div>
      )}

      {completed.length > 0 && (
        <div>
          <p className="text-[12px] font-medium uppercase tracking-[0.05em] mb-2" style={{ color: mutedText }}>
            Completed
          </p>
          <div className="flex flex-col gap-3">
            {completed.map((item) => (
              <ActionCard key={item.id} item={item} accentColor={accentColor} cardColor={cardColor} primaryText={primaryText} mutedText={mutedText} iconColor={iconColor} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
