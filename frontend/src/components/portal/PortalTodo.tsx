// frontend/src/components/portal/PortalTodo.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileUp, PenLine, CreditCard, CheckCircle2 } from 'lucide-react'

interface ActionItem {
  id: string
  type: 'document-request' | 'signature' | 'invoice'
  title: string
  description: string
  dueDate?: string
  completed: boolean
}

interface DashboardResponse {
  pending_document_requests: Array<{
    id: string
    title?: string
    due_date?: string | null
    status?: string
  }>
  pending_signatures: Array<{
    id: string
    engagement_id: string | null
    status: string
    sent_at: string | null
  }>
}

function getIcon(type: ActionItem['type']) {
  if (type === 'document-request') return <FileUp className="h-4 w-4 text-[#9CA3AF]" />
  if (type === 'signature') return <PenLine className="h-4 w-4 text-[#9CA3AF]" />
  return <CreditCard className="h-4 w-4 text-[#9CA3AF]" />
}

function ActionCard({ item }: { item: ActionItem }) {
  return (
    <div
      className="flex items-center justify-between gap-4 bg-[#383838] rounded-[8px] px-4 py-3"
      style={{ opacity: item.completed ? 0.7 : 1 }}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="flex-shrink-0 mt-0.5">{getIcon(item.type)}</div>
        <div className="min-w-0">
          <p className="text-[12px] font-medium text-[#EDEEF0] leading-tight">{item.title}</p>
          <p className="text-[11px] text-[#9CA3AF] mt-0.5 leading-snug">{item.description}</p>
          {item.dueDate && !item.completed && (
            <p className="text-[11px] text-[#9CA3AF] mt-1">Due {item.dueDate}</p>
          )}
        </div>
      </div>
      {item.completed ? (
        <CheckCircle2 className="h-5 w-5 text-[#10B981] flex-shrink-0" />
      ) : (
        <button className="flex-shrink-0 h-8 px-3 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap">
          {item.type === 'document-request' ? 'Upload' : item.type === 'signature' ? 'Review & Sign' : 'Pay Now'}
        </button>
      )}
    </div>
  )
}

interface PortalTodoProps {
  clientFirstName: string
}

export function PortalTodo({ clientFirstName }: PortalTodoProps) {
  const [items, setItems] = useState<ActionItem[]>([])
  const [loading, setLoading] = useState(true)

  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('portal_access_token')
      const res = await fetch('/api/backend/portal/dashboard', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) return
      const data: DashboardResponse = await res.json()

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
          description: 'Please review and sign the document.',
          completed: sig.status === 'signed' || sig.status === 'completed',
        })),
      ]
      setItems(mapped)
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
          <div key={i} className="h-16 rounded-[8px] bg-[#383838] animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-5 flex flex-col gap-5 max-w-2xl mx-auto">
      <div>
        <p className="text-[14px] font-medium text-[#EDEEF0]">Hello, {clientFirstName}</p>
        <p className="text-[11px] text-[#9CA3AF] mt-0.5">
          {active.length === 0
            ? "You're all caught up."
            : `You have ${active.length} item${active.length !== 1 ? 's' : ''} that need${active.length === 1 ? 's' : ''} your attention.`}
        </p>
      </div>

      {active.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-2">
            Action needed
          </p>
          <div className="flex flex-col gap-2">
            {active.map((item) => <ActionCard key={item.id} item={item} />)}
          </div>
        </div>
      )}

      {completed.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-2">
            Completed
          </p>
          <div className="flex flex-col gap-2">
            {completed.map((item) => <ActionCard key={item.id} item={item} />)}
          </div>
        </div>
      )}
    </div>
  )
}
