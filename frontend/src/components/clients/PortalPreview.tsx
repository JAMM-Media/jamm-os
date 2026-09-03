// frontend/src/components/clients/PortalPreview.tsx
'use client'
import { formatLocalDate } from '@/lib/utils'

import { useState } from 'react'
import { useFetch } from '@/lib/hooks/useFetch'
import api from '@/lib/api'
import { portalPreviewApi, PortalPreviewData } from '@/lib/api/portalPreviewApi'
import {
  CheckSquare, FolderOpen, Receipt, BarChart3, BookOpen, MessageSquare, Bell,
  FileText, AlertCircle,
} from 'lucide-react'

interface PortalPreviewProps {
  clientId: string
  clientName: string
}

interface ColorSet {
  top_bar: string
  accent: string
  avatar: string
  subtitle: string
}

const DARK_DEFAULTS: ColorSet = {
  top_bar: '#1A2535',
  accent: '#4A7FA5',
  avatar: '#3A6A94',
  subtitle: '#7DA3C4',
}

const LIGHT_DEFAULTS: ColorSet = {
  top_bar: '#1F3148',
  accent: '#1F3148',
  avatar: '#1F3148',
  subtitle: '#7DA3C4',
}

// Matches the real PortalShell content area background
const CONTENT_BG = '#F7F8FA'

// Exact same order as PortalShell.tsx NAV_ITEMS, plus Notifications (sidebar button in PortalShell)
const NAV_ITEMS = [
  { key: 'todo',            label: 'To-do',         Icon: CheckSquare },
  { key: 'documents',      label: 'Documents',      Icon: FolderOpen },
  { key: 'invoices',       label: 'Invoices',       Icon: Receipt },
  { key: 'billing-detail', label: 'Billing Detail', Icon: BarChart3 },
  { key: 'organizer',      label: 'Tax Organizer',  Icon: BookOpen },
  { key: 'messages',       label: 'Messages',       Icon: MessageSquare },
  { key: 'notifications',  label: 'Notifications',  Icon: Bell },
] as const

type NavKey = (typeof NAV_ITEMS)[number]['key']

function clientInitials(name: string): string {
  return name.split(' ').filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatUSD(amount: number): string {
  return amount.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function Bdg({ bg, text, label }: { bg: string; text: string; label: string }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 600, borderRadius: 9999, padding: '2px 8px', backgroundColor: bg, color: text, flexShrink: 0 }}>
      {label}
    </span>
  )
}

function docBadge(status: string) {
  const s = status.toLowerCase()
  if (s === 'pending' || s === 'sent') return <Bdg bg="#FEF3C7" text="#92400E" label={status} />
  if (s === 'complete' || s === 'completed') return <Bdg bg="#D1FAE5" text="#065F46" label={status} />
  return <Bdg bg="#E5E7EB" text="#374151" label={status} />
}

function invBadge(status: string) {
  const s = status.toLowerCase()
  if (s === 'paid') return <Bdg bg="#D1FAE5" text="#065F46" label={status} />
  if (s === 'overdue') return <Bdg bg="#FEE2E2" text="#991B1B" label={status} />
  if (s === 'sent' || s === 'unpaid' || s === 'pending') return <Bdg bg="#FEF3C7" text="#92400E" label={status} />
  return <Bdg bg="#E5E7EB" text="#374151" label={status} />
}

function SkeletonRows() {
  return (
    <div className="p-4 flex flex-col gap-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-14 rounded-xl animate-pulse" style={{ backgroundColor: '#E5E7EB' }} />
      ))}
    </div>
  )
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div className="flex items-center justify-center py-10">
      <p style={{ fontSize: 12, color: '#6B7280' }}>{msg}</p>
    </div>
  )
}

function HonestPlaceholder({ tab }: { tab: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 gap-2">
      <AlertCircle size={18} style={{ color: '#D1D5DB' }} />
      <p style={{ fontSize: 12, color: '#6B7280', textAlign: 'center' }}>
        {tab} data is not available in this preview. Open the live portal to view the full {tab} page.
      </p>
    </div>
  )
}

export function PortalPreview({ clientId, clientName }: PortalPreviewProps) {
  const [activeTab, setActiveTab] = useState<NavKey>('todo')

  const { data: preview, isLoading } = useFetch(
    (): Promise<PortalPreviewData> => portalPreviewApi.get(clientId).then((r) => r.data),
    [clientId]
  )

  // Fetch firm branding the same way PortalBrandingTab.tsx does
  const { data: firmRaw } = useFetch(
    () =>
      api
        .get<{ id: string; name: string; settings?: Record<string, unknown> | null }>('/users/firm')
        .then((r) => r.data),
    []
  )

  // Resolve colors from saved settings with real defaults
  const mode: 'dark' | 'light' = (firmRaw?.settings?.portal_mode as 'dark' | 'light') || 'dark'
  const defaults = mode === 'dark' ? DARK_DEFAULTS : LIGHT_DEFAULTS
  const saved = ((mode === 'dark'
    ? firmRaw?.settings?.portal_colors_dark
    : firmRaw?.settings?.portal_colors_light) ?? {}) as Partial<ColorSet>
  const colors: ColorSet = { ...defaults, ...saved }

  const brandColor = colors.top_bar
  const accentColor = colors.accent
  const avatarColor = colors.avatar
  const subtitleColor = colors.subtitle
  const displayName =
    (firmRaw?.settings?.portal_display_name as string) || firmRaw?.name || clientName

  const clientDisplayName = preview?.client_name ?? clientName
  const firstName = clientDisplayName.split(' ')[0] || clientDisplayName
  const initials = clientInitials(clientDisplayName)

  const sidebarTextActive = '#FFFFFF'
  const sidebarTextMuted = 'rgba(255,255,255,0.75)'
  const sidebarActiveBg = 'rgba(255,255,255,0.10)'

  return (
    <div className="rounded-[10px] overflow-hidden border border-surface-border dark:border-dark-border shadow-sm">
      {/* Label bar */}
      <div className="px-4 py-2 border-b border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card">
        <span style={{ fontSize: 11, letterSpacing: '0.05em' }} className="uppercase text-muted-foreground">
          Client Portal Preview
        </span>
      </div>

      {/* Sidebar + content row */}
      <div className="flex" style={{ minHeight: 460 }}>

        {/* Compact sidebar: same nav order and keys as PortalShell.tsx */}
        <div className="flex flex-col flex-shrink-0" style={{ width: 148, backgroundColor: brandColor }}>
          <div style={{ padding: '14px 12px 10px' }}>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#FFFFFF', lineHeight: 1.3 }}>{displayName}</p>
            <p style={{ fontSize: 8, letterSpacing: '0.08em', fontWeight: 600, color: subtitleColor, textTransform: 'uppercase', marginTop: 2 }}>
              Client Portal
            </p>
          </div>
          <div style={{ height: 1, backgroundColor: 'rgba(255,255,255,0.10)', margin: '0 10px 6px' }} />

          <nav style={{ flex: 1, padding: '0 6px', display: 'flex', flexDirection: 'column', gap: 2 }}>
            {NAV_ITEMS.map(({ key, label, Icon }) => {
              const isActive = activeTab === key
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveTab(key)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 7, padding: '7px 8px',
                    borderRadius: 8, fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    background: isActive ? sidebarActiveBg : 'transparent',
                    color: isActive ? sidebarTextActive : sidebarTextMuted,
                    borderLeft: isActive ? `2px solid ${accentColor}` : '2px solid transparent',
                    width: '100%', textAlign: 'left',
                  }}
                >
                  <Icon size={13} style={{ flexShrink: 0 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
                </button>
              )
            })}
          </nav>

          {/* Client avatar row, mirrors PortalShell */}
          <div style={{ padding: '8px 10px 12px', display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{
              width: 22, height: 22, borderRadius: '50%', backgroundColor: avatarColor,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <span style={{ fontSize: 7, fontWeight: 700, color: '#FFFFFF' }}>{initials}</span>
            </div>
            <span style={{ fontSize: 10, color: sidebarTextMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {clientDisplayName}
            </span>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto" style={{ backgroundColor: CONTENT_BG }}>
          {isLoading ? (
            <SkeletonRows />
          ) : (
            <>
              {/* TO-DO: real data from document_requests */}
              {activeTab === 'todo' && (
                <div className="p-4 flex flex-col gap-3">
                  <div>
                    <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>To-do</p>
                    <p style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
                      Hello, {firstName}.{' '}
                      {!preview?.document_requests.length
                        ? 'No open action items right now.'
                        : `${preview.document_requests.length} item${preview.document_requests.length !== 1 ? 's' : ''} need attention.`}
                    </p>
                  </div>
                  {!preview?.document_requests.length ? (
                    <EmptyState msg="Nothing needs attention right now." />
                  ) : (
                    preview.document_requests.map((req) => (
                      <div key={req.id} className="bg-white rounded-xl border border-gray-100 px-4 py-3 flex items-center justify-between gap-3">
                        <div style={{ minWidth: 0 }}>
                          <p style={{ fontSize: 13, fontWeight: 600, color: '#1F3148', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {req.title}
                          </p>
                          <p style={{ fontSize: 11, color: '#6B7280', marginTop: 1 }}>
                            {req.items_completed} of {req.items_total} uploaded
                            {req.due_date ? ' · Due ' + formatLocalDate(req.due_date, { month: 'short', day: 'numeric' }) : ''}
                          </p>
                        </div>
                        {docBadge(req.status)}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* DOCUMENTS: real data */}
              {activeTab === 'documents' && (
                <div className="p-4 flex flex-col gap-3">
                  <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>Documents</p>
                  {!preview?.documents.length ? (
                    <EmptyState msg="No documents on file." />
                  ) : (
                    preview.documents.map((doc) => (
                      <div key={doc.id} className="bg-white rounded-xl border border-gray-100 px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText size={13} style={{ color: '#9CA3AF', flexShrink: 0 }} />
                          <span style={{ fontSize: 13, color: '#1F3148', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {doc.name}
                          </span>
                        </div>
                        <span style={{ fontSize: 11, color: '#6B7280', flexShrink: 0 }}>{formatDate(doc.uploaded_at)}</span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* INVOICES: real data */}
              {activeTab === 'invoices' && (
                <div className="p-4 flex flex-col gap-3">
                  <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>Invoices</p>
                  {!preview?.invoices.length ? (
                    <EmptyState msg="No invoices yet." />
                  ) : (
                    preview.invoices.map((inv) => (
                      <div key={inv.id} className="bg-white rounded-xl border border-gray-100 px-4 py-3 flex items-center justify-between gap-3">
                        <div style={{ minWidth: 0 }}>
                          <p style={{ fontSize: 13, fontWeight: 600, color: '#1F3148' }}>{inv.invoice_number}</p>
                          <p style={{ fontSize: 11, color: '#6B7280', marginTop: 1 }}>
                            {formatUSD(inv.amount_due)}
                            {inv.due_date ? ' · Due ' + formatLocalDate(inv.due_date, { month: 'short', day: 'numeric' }) : ''}
                          </p>
                        </div>
                        {invBadge(inv.status)}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* BILLING DETAIL: real summary from invoice totals */}
              {activeTab === 'billing-detail' && (
                <div className="p-4 flex flex-col gap-3">
                  <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>Billing Detail</p>
                  {!preview?.billing ? (
                    <HonestPlaceholder tab="Billing Detail" />
                  ) : (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
                        {[
                          { label: 'Total invoiced', value: formatUSD(preview.billing.total_invoiced) },
                          { label: 'Outstanding',    value: formatUSD(preview.billing.total_outstanding) },
                          { label: 'Invoices',       value: String(preview.billing.invoice_count) },
                        ].map(({ label, value }) => (
                          <div key={label} className="bg-white rounded-xl border border-gray-100 px-3 py-3">
                            <p style={{ fontSize: 10, color: '#9CA3AF', marginBottom: 4 }}>{label}</p>
                            <p style={{ fontSize: 16, fontWeight: 700, color: '#1F3148' }}>{value}</p>
                          </div>
                        ))}
                      </div>
                      <p style={{ fontSize: 10, color: '#9CA3AF', textAlign: 'center' }}>
                        Showing invoice totals. Full billing detail with time entries is in the live portal.
                      </p>
                    </>
                  )}
                </div>
              )}

              {/* TAX ORGANIZER: real organizer status counts */}
              {activeTab === 'organizer' && (
                <div className="p-4 flex flex-col gap-3">
                  <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>Tax Organizer</p>
                  {!preview?.organizer ? (
                    <HonestPlaceholder tab="Tax Organizer" />
                  ) : preview.organizer.organizer_count === 0 ? (
                    <EmptyState msg="No tax organizers for this client." />
                  ) : (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
                        {[
                          { label: 'Total',       value: String(preview.organizer.organizer_count) },
                          { label: 'Sent',        value: String(preview.organizer.sent_count) },
                          { label: 'In progress', value: String(preview.organizer.in_progress_count) },
                          { label: 'Submitted',   value: String(preview.organizer.submitted_count) },
                        ].map(({ label, value }) => (
                          <div key={label} className="bg-white rounded-xl border border-gray-100 px-3 py-3">
                            <p style={{ fontSize: 10, color: '#9CA3AF', marginBottom: 4 }}>{label}</p>
                            <p style={{ fontSize: 16, fontWeight: 700, color: '#1F3148' }}>{value}</p>
                          </div>
                        ))}
                      </div>
                      <p style={{ fontSize: 10, color: '#9CA3AF', textAlign: 'center' }}>
                        Section questionnaire detail is in the live portal.
                      </p>
                    </>
                  )}
                </div>
              )}

              {/* MESSAGES: real data (unread count + last message timestamp) */}
              {activeTab === 'messages' && (
                <div className="p-4 flex flex-col gap-3">
                  <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>Messages</p>
                  {!preview?.messages || (!preview.messages.unread_count && !preview.messages.last_message_at) ? (
                    <div className="flex flex-col items-center justify-center py-10 gap-2">
                      <MessageSquare size={18} style={{ color: '#D1D5DB' }} />
                      <p style={{ fontSize: 13, fontWeight: 600, color: '#1F3148' }}>No messages yet</p>
                      <p style={{ fontSize: 11, color: '#6B7280', textAlign: 'center' }}>
                        Messages between your firm and this client appear here.
                      </p>
                    </div>
                  ) : (
                    <div className="bg-white rounded-xl border border-gray-100 px-4 py-3">
                      <div className="flex items-center justify-between">
                        <p style={{ fontSize: 13, fontWeight: 600, color: '#1F3148' }}>Conversation</p>
                        {preview.messages.unread_count > 0 && (
                          <span style={{ fontSize: 10, fontWeight: 600, borderRadius: 9999, padding: '2px 8px', backgroundColor: accentColor, color: '#FFFFFF' }}>
                            {preview.messages.unread_count} unread
                          </span>
                        )}
                      </div>
                      {preview.messages.last_message_at && (
                        <p style={{ fontSize: 11, color: '#6B7280', marginTop: 4 }}>
                          Last message {formatDate(preview.messages.last_message_at)}
                        </p>
                      )}
                      <p style={{ fontSize: 10, color: '#9CA3AF', marginTop: 8, fontStyle: 'italic' }}>
                        Switch to the Messages tab to view the full conversation.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* NOTIFICATIONS: real data from PortalNotification model */}
              {activeTab === 'notifications' && (
                <div className="p-4 flex flex-col gap-3">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3148' }}>Notifications</p>
                    {(preview?.notifications?.unread_count ?? 0) > 0 && (
                      <span style={{ fontSize: 10, fontWeight: 600, borderRadius: 9999, padding: '2px 8px', backgroundColor: accentColor, color: '#FFFFFF' }}>
                        {preview!.notifications.unread_count} unread
                      </span>
                    )}
                  </div>
                  {!preview?.notifications?.recent.length ? (
                    <EmptyState msg="No notifications yet." />
                  ) : (
                    preview.notifications.recent.map((n) => (
                      <div key={n.id} className="bg-white rounded-xl border border-gray-100 px-4 py-3">
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                          <p style={{ fontSize: 13, fontWeight: 600, color: '#1F3148' }}>{n.title}</p>
                          {!n.is_read && (
                            <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: accentColor, flexShrink: 0, marginTop: 4 }} />
                          )}
                        </div>
                        {n.body && <p style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>{n.body}</p>}
                        <p style={{ fontSize: 10, color: '#9CA3AF', marginTop: 4 }}>{formatDate(n.created_at)}</p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
