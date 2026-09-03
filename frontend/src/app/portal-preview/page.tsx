// path: frontend/src/app/portal-preview/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { FileUp, PenLine } from 'lucide-react'
import { PortalShell } from '@/components/portal/PortalShell'

interface PreviewMe {
  client_id: string
  client_name: string
  firm_name: string
  portal_display_name: string
  portal_logo_url: string | null
  portal_mode: 'light' | 'dark'
  portal_top_bar_color: string
  portal_page_color: string
  portal_tab_bar_color: string
  portal_accent_color: string
  portal_avatar_color: string
  portal_subtitle_color: string
  portal_card_color: string
  portal_text_primary: string
  portal_text_muted: string
}

interface DashboardData {
  pending_document_requests: Array<{
    id: string
    title: string
    due_date: string | null
    status: string
  }>
  pending_signatures: Array<{
    id: string
    status: string
    sent_at: string | null
  }>
  unread_notification_count: number
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function PortalPreviewPage() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')
  const [me, setMe] = useState<PreviewMe | null>(null)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('No preview token found. Return to Settings → Portal Branding and click "Open preview" again.')
      return
    }
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    Promise.all([
      fetch('/api/backend/portal-preview/me', { headers }).then(async (r) => {
        if (!r.ok) throw new Error(String(r.status))
        return r.json()
      }),
      fetch('/api/backend/portal-preview/dashboard', { headers }).then(async (r) => {
        if (!r.ok) throw new Error(String(r.status))
        return r.json()
      }),
    ])
      .then(([meData, dashData]: [PreviewMe, DashboardData]) => {
        setMe(meData)
        setDashboard(dashData)
      })
      .catch(() => {
        setError('Preview session expired or invalid. Return to Settings → Portal Branding and click "Open preview" again.')
      })
  }, [token])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#F3F4F6' }}>
        <div className="max-w-md w-full mx-4 text-center p-8 bg-white rounded-xl shadow-sm border border-gray-100">
          <p className="text-[15px] font-semibold mb-2" style={{ color: '#1F3148' }}>Preview unavailable</p>
          <p className="text-[13px]" style={{ color: '#6B7280' }}>{error}</p>
        </div>
      </div>
    )
  }

  if (!me) {
    return (
      <div className="min-h-screen flex" style={{ backgroundColor: '#2D2D2D' }}>
        <div className="w-56 flex-shrink-0 animate-pulse" style={{ backgroundColor: '#1A2535' }} />
        <div className="flex-1 p-6 flex flex-col gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-xl animate-pulse bg-white" />
          ))}
        </div>
      </div>
    )
  }

  const logoImgSrc = me.portal_logo_url
    ? `https://api.jammpx.com${me.portal_logo_url}`
    : undefined

  const open = dashboard
    ? [
        ...dashboard.pending_document_requests.map((dr) => ({
          id: dr.id,
          type: 'doc' as const,
          title: dr.title ?? 'Document Request',
          sub: 'Needs your attention',
          dueDate: dr.due_date,
        })),
        ...dashboard.pending_signatures.map((sig) => ({
          id: sig.id,
          type: 'sig' as const,
          title: 'Signature Required',
          sub: sig.sent_at ? `Sent ${formatDate(sig.sent_at)}` : 'Please review and sign.',
          dueDate: null,
        })),
      ]
    : []

  return (
    <div className="flex flex-col h-screen">
      {/* Banner in normal document flow, above PortalShell. Not sticky/absolute, so it
          does not overlap the floating bell and avatar (absolute top-4 right-5 z-10
          inside PortalShell's right column). */}
      <div
        className="flex-shrink-0 flex items-center justify-center gap-2 px-4 py-2.5"
        style={{ backgroundColor: '#FEF3C7', borderBottom: '1px solid #FDE68A' }}
      >
        <svg className="w-4 h-4 flex-shrink-0" style={{ color: '#92400E' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        </svg>
        <span className="text-[13px] font-semibold" style={{ color: '#92400E' }}>
          Staff preview - this is not a live client session. Branding reflects your current saved settings.
        </span>
      </div>
      {/* PortalShell fills the remaining viewport height. overflow-hidden clips the
          internal h-screen so the shell does not extend below the viewport. */}
      <div className="flex-1 overflow-hidden min-h-0">
        <PortalShell
          firmName={me.portal_display_name || me.firm_name}
          logoUrl={logoImgSrc}
          brandColor={me.portal_top_bar_color}
          pageColor={me.portal_page_color}
          tabBarColor={me.portal_tab_bar_color}
          accentColor={me.portal_accent_color}
          avatarColor={me.portal_avatar_color}
          subtitleColor={me.portal_subtitle_color}
          portalMode={me.portal_mode}
          clientName={me.client_name}
          activeTab="todo"
          onTabChange={() => {}}
        >

      {/* To-do content (read-only) */}
      <div className="p-6 flex flex-col gap-6">
        <div>
          <h1 className="text-[22px] font-bold" style={{ color: '#1F3148' }}>To-do</h1>
          <p className="text-[13px] mt-1" style={{ color: '#6B7280' }}>
            Here are the tasks and action items that need your attention.
          </p>
        </div>

        <section>
          <h2 className="text-[13px] font-semibold mb-3" style={{ color: '#374151' }}>Open tasks</h2>
          {!dashboard ? (
            <div className="flex flex-col gap-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-16 rounded-xl animate-pulse bg-white border border-gray-100" />
              ))}
            </div>
          ) : open.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-100 px-5 py-10 text-center">
              <p className="text-[14px]" style={{ color: '#6B7280' }}>No open tasks for this client.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {open.map((item) => (
                <div
                  key={item.id}
                  className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4"
                >
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: '#E5E7EB' }}
                  >
                    {item.type === 'sig' ? (
                      <PenLine size={16} style={{ color: '#374151' }} />
                    ) : (
                      <FileUp size={16} style={{ color: '#374151' }} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[14px] font-semibold truncate" style={{ color: '#1F3148' }}>{item.title}</p>
                    <p className="text-[12px] mt-0.5" style={{ color: '#6B7280' }}>{item.sub}</p>
                  </div>
                  {item.dueDate && (
                    <span className="text-[11px] font-medium flex-shrink-0" style={{ color: '#6B7280' }}>
                      Due {formatDate(item.dueDate)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
        </PortalShell>
      </div>
    </div>
  )
}
