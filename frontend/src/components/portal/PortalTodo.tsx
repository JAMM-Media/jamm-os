// frontend/src/components/portal/PortalTodo.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileUp, PenLine, ChevronRight, File, Receipt, CircleHelp, UserCheck, Lightbulb, CalendarDays } from 'lucide-react'
import { getPortalDashboard, getPortalDocuments } from '@/lib/portal-api'
import type { PortalDocument } from '@/lib/portal-api'

// Props interface is preserved unchanged so portal/page.tsx needs no edits.
// cardColor, portalMode, textPrimary, textMuted are accepted but not used here;
// the To-do page uses the fixed light-theme palette from the PortalShell rebuild.
interface PortalTodoProps {
  clientFirstName: string
  accentColor?: string
  cardColor?: string
  portalMode?: 'light' | 'dark'
  textPrimary?: string
  textMuted?: string
}

interface ActionItem {
  id: string
  type: 'document-request' | 'signature'
  title: string
  description: string
  dueDate?: string
  completed: boolean
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// Due date display: plain text + calendar icon, no pill background.
// Overdue retains the real date so information is not lost.
// Color rules confirmed from mock: overdue=red, within 7 days=amber, later=dark gray.
function getDueDateDisplay(iso?: string): { color: string; label: string } | null {
  if (!iso) return null
  const dateStr = formatDate(iso)
  const daysUntil = Math.floor((new Date(iso).getTime() - Date.now()) / 86400000)
  if (daysUntil < 0) return { color: '#DC2626', label: `Overdue - ${dateStr}` }
  if (daysUntil <= 7) return { color: '#D97706', label: `Due ${dateStr}` }
  return { color: '#374151', label: `Due ${dateStr}` }
}

// Description generator: frontend-only heuristic since DocumentRequest has no
// description/notes field (only title, due_date, status, checklist_items JSON).
// The checklist_items descriptions are not returned by the portal dashboard endpoint.
// Each call produces a sentence specific to the task title so rows are not identical.
function getTaskDescription(type: 'document-request' | 'signature', title: string): string {
  if (type === 'signature') return 'Please review and sign this document.'
  const t = title.toLowerCase()
  if (t.includes('receipt') || t.includes('expense')) return `Please provide your ${title}.`
  if (t.includes('questionnaire')) return 'Please complete the client questionnaire.'
  if (t.includes('review') || t.includes('approve')) return `Please review: ${title}.`
  return `Please upload your ${title}.`
}

// Single-container stat strip: one white card with internal dividers (not four separate cards).
// Each section's content is identical to the prior StatCard but without its own border.
function StatSection({ value, label, subtext, valueColor, subtextColor = '#9CA3AF' }: {
  value: number
  label: string
  subtext: string
  valueColor: string
  subtextColor?: string
}) {
  return (
    <div className="px-5 py-4 flex flex-col">
      <p className="text-[11px] font-medium mb-2" style={{ color: '#9CA3AF' }}>{label}</p>
      <p className="text-[40px] font-bold leading-none mb-1" style={{ color: valueColor }}>
        {value}
      </p>
      <p className="text-[11px] leading-snug" style={{ color: subtextColor }}>{subtext}</p>
    </div>
  )
}

// Icon selection rule: signature type always gets PenLine. For document-request types,
// the task title is matched case-insensitively against keywords:
//   "receipt" or "expense" -> Receipt
//   "questionnaire" or "question" -> CircleHelp
//   "review" or "approve" -> UserCheck
//   all others -> FileUp (generic document upload)
// This is a frontend-only heuristic; the backend carries no sub-type field.
// Icon color is dark neutral (#374151) per mock, not the accent blue.
function getTaskIcon(item: ActionItem): React.ReactNode {
  const iconColor = '#374151'
  if (item.type === 'signature') return <PenLine size={16} style={{ color: iconColor }} />
  const t = item.title.toLowerCase()
  if (t.includes('receipt') || t.includes('expense')) return <Receipt size={16} style={{ color: iconColor }} />
  if (t.includes('questionnaire') || t.includes('question')) return <CircleHelp size={16} style={{ color: iconColor }} />
  if (t.includes('review') || t.includes('approve')) return <UserCheck size={16} style={{ color: iconColor }} />
  return <FileUp size={16} style={{ color: iconColor }} />
}

function TaskRow({ item }: { item: ActionItem }) {
  const dueDateDisplay = getDueDateDisplay(item.dueDate)

  return (
    <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4">
      {/* Circular badge with muted gray background and dark icon, matching mock */}
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: '#E5E7EB' }}
      >
        {getTaskIcon(item)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold truncate" style={{ color: '#1F3148' }}>
          {item.title}
        </p>
        <p className="text-[12px] mt-0.5 truncate" style={{ color: '#6B7280' }}>
          {item.description}
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        {dueDateDisplay && (
          <div className="flex items-center gap-1 whitespace-nowrap">
            <CalendarDays size={12} style={{ color: dueDateDisplay.color }} />
            <span className="text-[11px] font-medium" style={{ color: dueDateDisplay.color }}>
              {dueDateDisplay.label}
            </span>
          </div>
        )}
        <ChevronRight size={16} style={{ color: '#9CA3AF' }} />
      </div>
    </div>
  )
}

function DocRow({ doc, isLast }: { doc: PortalDocument; isLast: boolean }) {
  // Split name into base + extension so truncation never cuts into the extension.
  const dotIdx = doc.name.lastIndexOf('.')
  const basename = dotIdx > 0 ? doc.name.slice(0, dotIdx) : doc.name
  const ext = dotIdx > 0 ? doc.name.slice(dotIdx) : ''

  return (
    <tr className={isLast ? '' : 'border-b border-gray-50'}>
      <td className="px-5 py-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <File size={14} style={{ color: '#9CA3AF' }} className="flex-shrink-0" />
          <div className="flex items-baseline min-w-0">
            <span className="text-[13px] font-medium truncate" style={{ color: '#1F3148' }}>{basename}</span>
            <span className="text-[13px] font-medium flex-shrink-0" style={{ color: '#1F3148' }}>{ext}</span>
          </div>
        </div>
      </td>
      <td className="px-5 py-3 whitespace-nowrap">
        <span className="text-[12px]" style={{ color: '#6B7280' }}>
          {formatDate(doc.uploaded_at)}
        </span>
      </td>
      <td className="px-5 py-3">
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-[4px]"
          style={{ backgroundColor: '#D1FAE5', color: '#065F46' }}
        >
          Uploaded
        </span>
      </td>
    </tr>
  )
}

// Pass (a): "Need help?" right panel -- present in mock, was absent from current implementation.
function NeedHelpPanel({ accentColor }: { accentColor: string }) {
  return (
    <div className="w-60 flex-shrink-0">
      <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Lightbulb size={16} style={{ color: '#1F3148' }} />
          <p className="text-[14px] font-semibold" style={{ color: '#1F3148' }}>Need help?</p>
        </div>
        <p className="text-[12px] leading-relaxed" style={{ color: '#6B7280' }}>
          If you have any questions about your tasks or need to share information, reach out to your accountant.
        </p>
        <a
          href="/portal?tab=messages"
          className="block text-center text-[12px] font-semibold px-4 py-2 rounded-lg text-white transition-opacity hover:opacity-80"
          style={{ backgroundColor: '#1F3148' }}
        >
          Send a message
        </a>
      </div>
    </div>
  )
}

export function PortalTodo({ accentColor = '#3A6A94' }: PortalTodoProps) {
  const [items, setItems] = useState<ActionItem[]>([])
  const [docs, setDocs] = useState<PortalDocument[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [dashboard, documents] = await Promise.all([
        getPortalDashboard(),
        getPortalDocuments(),
      ])

      const mapped: ActionItem[] = [
        ...dashboard.pending_document_requests.map(dr => ({
          id: dr.id,
          type: 'document-request' as const,
          title: dr.title ?? 'Document Request',
          description: getTaskDescription('document-request', dr.title ?? 'Document Request'),
          dueDate: dr.due_date ?? undefined,
          completed: dr.status === 'complete',
        })),
        ...dashboard.pending_signatures.map(sig => ({
          id: sig.id,
          type: 'signature' as const,
          title: 'Signature Required',
          description: sig.sent_at
            ? `Sent ${formatDate(sig.sent_at)} - please review and sign.`
            : 'Please review and sign the document.',
          dueDate: undefined,
          completed: sig.status === 'completed',
        })),
      ]

      setItems(mapped)
      setDocs(documents.filter(d => !d.is_superseded).slice(0, 5))
    } catch {
      // leave empty state on error
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-16 rounded-xl animate-pulse bg-white border border-gray-100" />
        ))}
      </div>
    )
  }

  const active = items.filter(i => !i.completed)
  const completed = items.filter(i => i.completed)
  const overdueCount = active.filter(i => i.dueDate && new Date(i.dueDate).getTime() < Date.now()).length
  const dueThisWeekCount = active.filter(i => {
    if (!i.dueDate) return false
    const days = Math.floor((new Date(i.dueDate).getTime() - Date.now()) / 86400000)
    return days >= 0 && days <= 7
  }).length

  return (
    <div className="p-6 flex flex-col gap-6">
      {/* Pass (a): page title + subtitle -- present in mock, was absent */}
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: '#1F3148' }}>To-do</h1>
        <p className="text-[13px] mt-1" style={{ color: '#6B7280' }}>
          Here are the tasks and action items that need your attention.
        </p>
      </div>

      {/* Stat strip: single container with divide-x dividers (not four separate cards) */}
      <div className="bg-white rounded-xl border border-gray-100 grid grid-cols-4 divide-x divide-gray-100">
        <StatSection
          value={active.length}
          label="Open tasks"
          subtext="Due soon"
          valueColor="#1F3148"
          subtextColor="#D97706"
        />
        <StatSection
          value={overdueCount}
          label="Overdue"
          subtext="Needs immediate attention"
          valueColor={overdueCount > 0 ? '#DC2626' : '#1F3148'}
        />
        <StatSection
          value={dueThisWeekCount}
          label="Due this week"
          subtext="Within the next 7 days"
          valueColor="#1F3148"
        />
        <StatSection
          value={completed.length}
          label="Completed"
          subtext="This month"
          valueColor={completed.length > 0 ? '#059669' : '#1F3148'}
        />
      </div>

      {/* Pass (a): two-column zone -- main content left, "Need help?" right */}
      <div className="flex gap-6 items-start">
        {/* Left: tasks + recent documents */}
        <div className="flex-1 min-w-0 flex flex-col gap-6">
          {/* Open tasks */}
          {/* Pass (c): section heading changed to sentence case, 13px semi-bold */}
          <section>
            <h2 className="text-[13px] font-semibold mb-3" style={{ color: '#374151' }}>
              Open tasks
            </h2>
            {active.length === 0 ? (
              <div className="bg-white rounded-xl border border-gray-100 px-5 py-10 text-center">
                <p className="text-[14px]" style={{ color: '#6B7280' }}>
                  You are all caught up. No open tasks.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {active.map(item => (
                  <TaskRow key={item.id} item={item} />
                ))}
              </div>
            )}
          </section>

          {/* Recent documents */}
          <section>
            <h2 className="text-[13px] font-semibold mb-3" style={{ color: '#374151' }}>
              Recent documents
            </h2>
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              {docs.length === 0 ? (
                <div className="px-5 py-10 text-center">
                  <p className="text-[14px]" style={{ color: '#6B7280' }}>No documents yet.</p>
                </div>
              ) : (
                <>
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-100">
                        <th
                          className="text-left px-5 py-3 text-[11px] font-medium"
                          style={{ color: '#9CA3AF' }}
                        >
                          Document
                        </th>
                        <th
                          className="text-left px-5 py-3 text-[11px] font-medium"
                          style={{ color: '#9CA3AF' }}
                        >
                          Uploaded
                        </th>
                        <th
                          className="text-left px-5 py-3 text-[11px] font-medium"
                          style={{ color: '#9CA3AF' }}
                        >
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {docs.map((doc, idx) => (
                        <DocRow key={doc.id} doc={doc} isLast={idx === docs.length - 1} />
                      ))}
                    </tbody>
                  </table>
                  <div className="border-t border-gray-100 px-5 py-3">
                    <a
                      href="/portal?tab=documents"
                      className="text-[12px] font-medium transition-opacity hover:opacity-70"
                      style={{ color: accentColor }}
                    >
                      View all documents
                    </a>
                  </div>
                </>
              )}
            </div>
          </section>
        </div>

        {/* Right: "Need help?" panel */}
        <NeedHelpPanel accentColor={accentColor} />
      </div>
    </div>
  )
}
