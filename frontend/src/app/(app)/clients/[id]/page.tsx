// path: frontend/src/app/clients/[id]/page.tsx
'use client'

import { Suspense, useState, useEffect, useRef } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { clientsApi, engagementsApi, invoicesApi } from '@/lib/api'
import type { QBOARBalance } from '@/lib/api/clients'
import { useFetch } from '@/lib/hooks/useFetch'
import { Mail, Phone, MapPin, ArrowLeft, ExternalLink, Loader2, Send, Pencil, ChevronDown, ChevronUp } from 'lucide-react'
import { toast } from 'sonner'
import { parseMessage } from '@/lib/entityLinkParser'
import { NotesTab, NotesPanel } from '@/components/notes'
import { useNotes } from '@/components/notes'
import { useUnreadMessages } from '@/components/messaging/useUnreadMessages'
import { cn, formatEngagementType, formatEntityType, formatEntitySubtype } from '@/lib/utils'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'
import { IrsAuthBadge } from '@/components/clients/IrsAuthBadge'
import { IrsAuthTab } from '@/components/clients/IrsAuthTab'
import { DocumentExpirySection } from '@/components/clients/DocumentExpirySection'
import { PortalPreview } from '@/components/clients/PortalPreview'
import { HealthDot } from '@/components/clients/HealthDot'
import { EditClientModal } from '@/components/clients/EditClientModal'
import TaxOrganizerTab from '@/components/tax-organizer/TaxOrganizerTab'
import { NewEngagementModal } from '@/components/engagements/NewEngagementModal'
import { onConciergeAction } from '@/lib/events/conciergeEvents'
import type { Engagement } from '@/lib/api'
import type { Document } from '@/lib/api/documents'
import { DocumentTable } from '@/components/documents/DocumentTable'
import { BillingDetailModal } from '@/components/billing/BillingDetailModal'

function EngagementStatusBadge({ status }: { status: string }) {
  return <StatusBadge variant={status as Parameters<typeof StatusBadge>[0]['variant']} />
}

const CLIENT_TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'engagements', label: 'Engagements' },
  { key: 'documents', label: 'Documents' },
  { key: 'billing', label: 'Billing' },
  { key: 'irs-auth', label: 'IRS Authorizations' },
  { key: 'organizer', label: 'Tax Organizer' },
  { key: 'portal', label: 'Portal' },
  { key: 'emails', label: 'Emails' },
  { key: 'messages', label: 'Messages' },
]

function ClientDetailContent() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState(() => {
    const p = searchParams.get('tab')
    return p && CLIENT_TABS.some((t) => t.key === p) ? p : 'overview'
  })
  useEffect(() => {
    const p = searchParams.get('tab')
    if (p && CLIENT_TABS.some((t) => t.key === p) && p !== activeTab) {
      setActiveTab(p)
    }
  }, [searchParams])
  const [notesOpen, setNotesOpen] = useState(false)
  const [sendingPortalLink, setSendingPortalLink] = useState(false)
  const [viewingPortal, setViewingPortal] = useState(false)
  const { user } = useAuth()

  const clientId = params.id as string

  const [isEditOpen, setIsEditOpen] = useState(false)
  const [newEngagementOpen, setNewEngagementOpen] = useState(false)
  const [initialEngagementType, setInitialEngagementType] = useState<string | undefined>()
  const [portalLinkHighlight, setPortalLinkHighlight] = useState(false)
  const portalLinkRef = useRef<HTMLButtonElement>(null)
  const messageComposeRef = useRef<HTMLTextAreaElement>(null)
  const [qboEditMode, setQboEditMode] = useState(false)
  const [qboEditValue, setQboEditValue] = useState('')
  const [qboDeepLinkLoading, setQboDeepLinkLoading] = useState(false)
  const [billingDetailOpen, setBillingDetailOpen] = useState(false)

  useEffect(() => {
    const raw = sessionStorage.getItem('jamm_concierge_pending')
    if (!raw) return
    try {
      const action = JSON.parse(raw)
      if (Date.now() - (action._ts ?? 0) > 10000) {
        sessionStorage.removeItem('jamm_concierge_pending')
        return
      }
      if (action.modal === 'new-engagement') {
        sessionStorage.removeItem('jamm_concierge_pending')
        if (action.prefill?.engagementType) setInitialEngagementType(action.prefill.engagementType)
        setNewEngagementOpen(true)
      }
    } catch {
      sessionStorage.removeItem('jamm_concierge_pending')
    }
  }, [])

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'new-engagement') {
        setActiveTab('engagements')
        if (action.prefill?.engagementType) setInitialEngagementType(action.prefill.engagementType)
        setNewEngagementOpen(true)
      }
      if (action.modal === 'portal-magic-link') {
        setActiveTab('overview')
        setPortalLinkHighlight(true)
        setTimeout(() => {
          portalLinkRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 100)
        setTimeout(() => setPortalLinkHighlight(false), 3000)
      }
      if (action.type === 'prefill-message' && action.prefillMessage) {
        setActiveTab('messages')
        setMessageCompose(action.prefillMessage)
      }
    })
  }, [])

  const [clientDocs, setClientDocs] = useState<Document[]>([])
  const [docsLoading, setDocsLoading] = useState(false)
  const [showArchived, setShowArchived] = useState(false)

  const [clientMessages, setClientMessages] = useState<Array<{
    id: string
    body: string
    senderName: string | null
    senderRole: string
    createdAt: string
  }>>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [messageCompose, setMessageCompose] = useState('')
  useEffect(() => {
    const raw = sessionStorage.getItem('jamm_concierge_pending')
    if (!raw) return
    try {
      const action = JSON.parse(raw)
      if (Date.now() - (action._ts ?? 0) > 10000) {
        sessionStorage.removeItem('jamm_concierge_pending')
        return
      }
      if (action.prefillMessage && action.clientId === clientId) {
        sessionStorage.removeItem('jamm_concierge_pending')
        setMessageCompose(action.prefillMessage)
      }
    } catch {
      sessionStorage.removeItem('jamm_concierge_pending')
    }
  }, [clientId])
  useEffect(() => {
    if (messageComposeRef.current) {
      messageComposeRef.current.style.height = 'auto'
      messageComposeRef.current.style.height = Math.min(messageComposeRef.current.scrollHeight, 120) + 'px'
    }
  }, [messageCompose])
  const [messageSending, setMessageSending] = useState(false)

  const [clientEmailThreads, setClientEmailThreads] = useState<Array<{
    thread_id: string
    subject: string
    from: string
    date: string
    snippet: string
    unread: boolean
    client_id: string | null
    provider: string
  }>>([])
  const [emailsLoading, setEmailsLoading] = useState(false)
  const [emailsNoIntegration, setEmailsNoIntegration] = useState(false)

  const { data: client, isLoading: clientLoading, refetch: refetchClient } = useFetch(
    () => clientsApi.get(clientId),
    [clientId]
  )
  const { data: engagementsData, isLoading: engagementsLoading } = useFetch(
    () => engagementsApi.list(0, 50, clientId),
    [clientId]
  )
  const engagements = engagementsData?.items ?? []

  const { data: invoicesData, isLoading: invoicesLoading } = useFetch(
    () => invoicesApi.list(0, 50, clientId),
    [clientId]
  )
  const clientInvoices = invoicesData?.items ?? []

  const { data: qboAr, isLoading: qboLoading, isError: qboError } = useQuery<QBOARBalance>({
    queryKey: ['qbo-ar', clientId],
    queryFn: () => clientsApi.getQboAr(clientId),
    staleTime: 15 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const { unreadCount: unreadMessages, markAsRead: markMessagesRead } = useUnreadMessages(clientId)
  const { unreadCount: unreadNotes } = useNotes({ entityType: 'client', entityId: clientId })

  useEffect(() => {
    if (activeTab !== 'documents' || !clientId) return
    setDocsLoading(true)
    api.get(`/documents/?client_id=${clientId}&limit=100`)
      .then((r) => setClientDocs(r.data?.items ?? []))
      .catch(() => {})
      .finally(() => setDocsLoading(false))
  }, [activeTab, clientId])

  useEffect(() => {
    if (activeTab !== 'messages' || !clientId) return
    setMessagesLoading(true)
    api.get(`/clients/${clientId}/messages`)
      .then((res) => {
        const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
        setClientMessages(items.map((m: Record<string, unknown>) => ({
          id: String(m.id),
          body: String(m.body ?? ''),
          senderName: m.sender_name ? String(m.sender_name) : null,
          senderRole: String(m.sender_role ?? 'staff'),
          createdAt: String(m.created_at ?? ''),
        })))
      })
      .catch(() => {})
      .finally(() => setMessagesLoading(false))
  }, [activeTab, clientId])

  useEffect(() => {
    if (activeTab !== 'emails' || !clientId || !client?.email) return
    setEmailsLoading(true)
    setEmailsNoIntegration(false)
    const providers = ['gmail', 'outlook']
    Promise.allSettled(
      providers.map((p) => api.get(`/api/v1/inbox/threads?provider=${p}`))
    ).then((results) => {
      const allConnected = results.some((r) => r.status === 'fulfilled')
      if (!allConnected) {
        setEmailsNoIntegration(true)
        return
      }
      const clientEmail = (client.email ?? '').toLowerCase()
      const matched: typeof clientEmailThreads = []
      results.forEach((r, idx) => {
        if (r.status !== 'fulfilled') return
        const threads = r.value.data?.threads ?? []
        threads.forEach((t: {
          thread_id: string; subject: string; from: string; to: string
          date: string; snippet: string; unread: boolean; client_id: string | null
        }) => {
          const addrs = `${t.from},${t.to}`.toLowerCase()
          if (addrs.includes(clientEmail)) {
            matched.push({ ...t, provider: providers[idx] })
          }
        })
      })
      setClientEmailThreads(matched)
      api.post('/api/v1/inbox/events', { event_type: 'client.emails_tab_viewed', client_id: clientId }).catch(() => {})
    }).catch(() => {
      setEmailsNoIntegration(true)
    }).finally(() => setEmailsLoading(false))
  }, [activeTab, clientId, client?.email])

  const handleSendMessage = async () => {
    if (!messageCompose.trim() || messageSending) return
    setMessageSending(true)
    try {
      const res = await api.post(`/clients/${clientId}/messages`, { body: messageCompose.trim() })
      const m = res.data
      setClientMessages((prev) => [...prev, {
        id: String(m.id),
        body: String(m.body ?? ''),
        senderName: m.sender_name ? String(m.sender_name) : null,
        senderRole: String(m.sender_role ?? 'staff'),
        createdAt: String(m.created_at ?? ''),
      }])
      setMessageCompose('')
    } catch {
      toast.error('Failed to send message')
    } finally {
      setMessageSending(false)
    }
  }

  const handleViewPortal = async () => {
    setViewingPortal(true)
    try {
      const res = await api.get<{ portal_url: string }>(
        `/portal/admin/portal-access/${clientId}`
      )
      // Navigate current tab — avoids popup blocker
      window.location.href = res.data.portal_url
    } catch {
      toast.error('Could not open client portal — please try again')
      setViewingPortal(false)
    }
  }

  async function handleQboSave() {
    try {
      await api.patch(`/clients/${clientId}`, {
        quickbooks_customer_id: qboEditValue.trim() || null,
      })
      toast.success('QuickBooks ID linked')
      setQboEditMode(false)
      refetchClient()
    } catch {
      toast.error('Failed to update QuickBooks ID')
    }
  }

  const handleSendPortalLink = async () => {
    setSendingPortalLink(true)
    try {
      await api.post('/portal/magic-link', { client_id: clientId, expiry_hours: 48 })
      const email = client?.email ?? 'the client'
      toast.success(`Portal link sent to ${email} — expires in 48 hours`)
    } catch {
      toast.error('Could not send portal link — please try again')
    } finally {
      setSendingPortalLink(false)
    }
  }

  if (clientLoading) {
    return (
        <div className="flex flex-col items-center justify-center h-full gap-3 p-6">
          <div className="h-6 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
    )
  }

  if (!client) {
    return (
        <div className="flex flex-col items-center justify-center h-full gap-3 p-6">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            Client not found
          </p>
          <button
            onClick={() => router.push('/clients')}
            className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] flex items-center gap-1 transition-colors"
          >
            <ArrowLeft className="h-3 w-3" /> Back to Clients
          </button>
        </div>
    )
  }

  return (<>
      <div className="p-6">
        <Breadcrumb
          items={[
            { label: 'Clients', href: '/clients' },
            { label: client.name },
          ]}
        />

        {/* Client header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1 flex items-center gap-3">
              {client.name}
              <HealthDot clientId={clientId} showLabel />
            </h1>
            <div className="flex items-center gap-2">
              <StatusBadge variant={client.isActive ? 'active' : 'inactive'} />
              <IrsAuthBadge
                clientId={clientId}
                onClick={() => setActiveTab('irs-auth')}
              />
              {client.entityType && (
                <span className="text-[12px] text-[#6B7280]">{formatEntityType(client.entityType)}</span>
              )}
              {client.entitySubtype && (
                <span className="text-[12px] text-[#6B7280]">{formatEntitySubtype(client.entitySubtype)}</span>
              )}
            </div>
          </div>
          <button
            onClick={() => setIsEditOpen(true)}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
          >
            Edit Client
          </button>
        </div>

        {/* Tab row — inline to support unread badge on Messages tab */}
        <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border mb-6">
          {CLIENT_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                if (tab.key === 'messages') markMessagesRead()
                setActiveTab(tab.key)
              }}
              className={cn(
                'px-4 py-2.5 text-[13px] transition-colors relative flex items-center gap-1.5',
                activeTab === tab.key
                  ? 'text-brand dark:text-[#4A7FA5] font-medium'
                  : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal',
              )}
            >
              {tab.label}
              {tab.key === 'messages' && unreadMessages > 0 && (
                <span
                  className="inline-flex items-center justify-center bg-brand text-white"
                  style={{
                    height: 18,
                    minWidth: 18,
                    padding: '0 6px',
                    borderRadius: 9999,
                    fontSize: 11,
                    fontWeight: 500,
                    lineHeight: 1,
                  }}
                >
                  {unreadMessages > 99 ? '99+' : unreadMessages}
                </span>
              )}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand dark:bg-[#4A7FA5]" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'overview' && (
          <div>
          <div className="flex items-center justify-end gap-2 mb-4">
            {(user?.role === 'firm_owner' || user?.role === 'manager') && (
              <button
                ref={portalLinkRef}
                onClick={handleSendPortalLink}
                disabled={sendingPortalLink}
                className={`flex items-center gap-1.5 h-8 px-3 text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] border border-[0.5px] rounded-md bg-transparent hover:bg-surface-card dark:hover:bg-dark-card transition-colors disabled:opacity-60 ${portalLinkHighlight ? 'border-[#3A6A94] ring-2 ring-[#3A6A94]/40 animate-pulse' : 'border-[#C8CDD6] dark:border-[#484848]'}`}
              >
                {sendingPortalLink ? (
                  <Loader2 className="h-[14px] w-[14px] animate-spin" />
                ) : (
                  <Send className="h-[14px] w-[14px]" />
                )}
                Send Portal Link
              </button>
            )}
            <button
              onClick={handleViewPortal}
              disabled={viewingPortal}
              className="flex items-center gap-1.5 h-8 px-3 text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-md bg-transparent hover:bg-surface-card dark:hover:bg-dark-card transition-colors disabled:opacity-60"
            >
              {viewingPortal ? (
                <Loader2 className="h-[14px] w-[14px] animate-spin" />
              ) : (
                <ExternalLink className="h-[14px] w-[14px]" />
              )}
              View Client Portal
            </button>
          </div>
          <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Contact info card */}
            <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
              <h2 className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-3">
                Contact Information
              </h2>
              <div className="space-y-2.5">
                <div className="flex items-center gap-2.5">
                  <Mail className="h-4 w-4 text-[#6B7280] flex-shrink-0" />
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {client.email ?? '—'}
                  </span>
                </div>
                <div className="flex items-center gap-2.5">
                  <Phone className="h-4 w-4 text-[#6B7280] flex-shrink-0" />
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {client.phone ?? '—'}
                  </span>
                </div>
                {(client.addressLine1 || client.city || client.state) && (
                  <div className="flex items-center gap-2.5">
                    <MapPin className="h-4 w-4 text-[#6B7280] flex-shrink-0" />
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                      {[client.addressLine1, client.city, client.state, client.postalCode]
                        .filter(Boolean)
                        .join(', ')}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* QBO AR Balance card */}
            <div className={`bg-surface-card dark:bg-dark-card rounded-card p-4 ${qboAr && !qboAr.connected ? 'opacity-50' : ''}`}>
              <div className="flex items-center gap-1.5 mb-3">
                <svg width="16" height="16" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="16" cy="16" r="16" fill="#2CA01C" />
                  <path d="M8 16c0-4.418 3.582-8 8-8s8 3.582 8 8-3.582 8-8 8-8-3.582-8-8z" fill="white" fillOpacity="0.2" />
                  <path d="M13 16.5l2.5 2.5 4.5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className="text-[12px] font-medium text-brand-light dark:text-brand-light">QuickBooks AR</span>
              </div>
              {qboLoading ? (
                <div className="space-y-2">
                  <div className="h-6 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-4 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </div>
              ) : qboError || !qboAr ? (
                <p className="text-[12px] text-[#6B7280]">QBO data unavailable</p>
              ) : !qboAr.connected ? (
                <p className="text-[12px] text-[#6B7280]">Not connected to QuickBooks</p>
              ) : (
                <div className="space-y-1">
                  <p className={`text-[14px] font-medium ${(qboAr.outstanding_balance ?? 0) > 0 ? 'text-status-amber-text' : 'text-status-green-text'}`}>
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(qboAr.outstanding_balance ?? 0)} outstanding
                  </p>
                  <p className="text-[11px] text-[#6B7280]">
                    {qboAr.last_payment_date
                      ? `Last payment: ${new Date(qboAr.last_payment_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`
                      : 'No payments recorded'}
                  </p>
                  {client.quickbooksCustomerId && (
                    <a
                      href={`https://app.qbo.intuit.com/app/customerdetail?nameId=${client.quickbooksCustomerId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-brand-light dark:text-brand-light hover:underline inline-flex items-center gap-1 mt-1"
                    >
                      Open in QuickBooks
                      <svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M2 10L10 2M10 2H5M10 2V7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </a>
                  )}
                </div>
              )}
            </div>

            {/* QuickBooks Customer ID card */}
            {(user?.role === 'firm_owner' || user?.role === 'manager') && (
              <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
                <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">QuickBooks Customer ID</p>
                {qboEditMode ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={qboEditValue}
                      onChange={(e) => setQboEditValue(e.target.value)}
                      className="flex-1 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand"
                      placeholder="e.g. 123456"
                      autoFocus
                    />
                    <button
                      onClick={handleQboSave}
                      className="px-3 py-1.5 text-[12px] font-medium bg-brand dark:bg-brand-btn text-white rounded-[6px] hover:opacity-90"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setQboEditMode(false)}
                      className="px-3 py-1.5 text-[12px] text-[#6B7280] hover:text-brand"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className={`text-[13px] ${client.quickbooksCustomerId ? 'text-brand dark:text-[#EDEEF0]' : 'text-[#9CA3AF]'}`}>
                      {client.quickbooksCustomerId ?? 'Not linked'}
                    </span>
                    <button
                      onClick={() => { setQboEditValue(client.quickbooksCustomerId ?? ''); setQboEditMode(true) }}
                      className="p-1 rounded text-[#6B7280] hover:text-brand hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                      title="Edit QuickBooks Customer ID"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    {client.quickbooksCustomerId && (
                      <button
                        onClick={async () => {
                          setQboDeepLinkLoading(true)
                          try {
                            const res = await api.get(`/api/v1/integrations/quickbooks/deep-link/client/${clientId}`)
                            window.open(res.data.url, '_blank')
                          } catch {
                            toast.error('Could not open QuickBooks link.')
                          } finally {
                            setQboDeepLinkLoading(false)
                          }
                        }}
                        disabled={qboDeepLinkLoading}
                        className="flex items-center gap-1 text-[12px] text-[#6B7280] hover:text-brand transition-colors disabled:opacity-60"
                      >
                        {qboDeepLinkLoading ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ExternalLink className="h-3.5 w-3.5" />
                        )}
                        Open in QuickBooks
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Engagement summary card */}
            <div className="bg-surface-card dark:bg-dark-card rounded-card p-4 xl:col-span-2">
              <h2 className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-3">
                Recent Engagements
              </h2>
              {engagementsLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-10 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  ))}
                </div>
              ) : engagements.length === 0 ? (
                <p className="text-[12px] text-[#6B7280]">No engagements yet.</p>
              ) : (
                <div className="space-y-2">
                  {engagements.slice(0, 3).map((eng) => (
                    <div
                      key={eng.id}
                      className="flex items-center justify-between py-2 border-b border-[0.5px] border-surface-border dark:border-dark-border last:border-0"
                    >
                      <div>
                        <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                          {eng.name}
                        </p>
                        {eng.endDate && (
                          <p className="text-[11px] text-[#6B7280]">
                            Due {eng.endDate}
                          </p>
                        )}
                      </div>
                      <EngagementStatusBadge status={eng.status} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Document Expiry Tracking */}
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <DocumentExpirySection clientId={clientId} />
          </div>
          </div>
          </div>
        )}

        {activeTab === 'engagements' && (
          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface-card dark:bg-[#252525]">
                  {['Engagement', 'Type', 'Due Date', 'Status'].map((col) => (
                    <th
                      key={col}
                      className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {engagementsLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={4} className="px-4 py-3">
                        <div className="h-4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      </td>
                    </tr>
                  ))
                ) : engagements.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[12px] text-[#6B7280]">
                      No engagements yet.
                    </td>
                  </tr>
                ) : (
                  engagements.map((eng, i) => (
                    <tr
                      key={eng.id}
                      onClick={() => router.push(`/engagements/${eng.id}`)}
                      className={[
                        'bg-surface-page dark:bg-dark-page hover:bg-[#DDDFE3] dark:hover:bg-[#323232] transition-colors cursor-pointer',
                        i !== engagements.length - 1
                          ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                          : '',
                      ].join(' ')}
                    >
                      <td className="px-4 py-3">
                        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                          {eng.name}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                          {formatEngagementType(eng.engagementType)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                          {eng.endDate ?? '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <EngagementStatusBadge status={eng.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'documents' && (() => {
          const activeDocs = clientDocs.filter((d) => !d.is_superseded)
          const archivedDocs = clientDocs.filter((d) => d.is_superseded)
          return (
            <div className="flex flex-col gap-4">
              {docsLoading ? (
                <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="flex gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0">
                      {Array.from({ length: 4 }).map((_, j) => (
                        <div key={j} className="h-4 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      ))}
                    </div>
                  ))}
                </div>
              ) : activeDocs.length === 0 && archivedDocs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                    <span className="text-[18px]">📄</span>
                  </div>
                  <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                    No documents yet
                  </p>
                  <p className="text-[12px] text-[#6B7280]">
                    Documents uploaded by this client will appear here.
                  </p>
                </div>
              ) : (
                <>
                  {activeDocs.length === 0 ? (
                    <p className="text-[12px] text-[#6B7280]">All documents are archived</p>
                  ) : (
                    <DocumentTable documents={activeDocs} />
                  )}
                  {archivedDocs.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
                          Archived ({archivedDocs.length})
                        </span>
                        <button
                          onClick={() => setShowArchived((v) => !v)}
                          className="p-0.5 rounded text-[#6B7280] hover:text-brand"
                        >
                          {showArchived ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                        </button>
                      </div>
                      {showArchived && (
                        <div style={{ opacity: 0.6 }}>
                          <DocumentTable documents={archivedDocs} />
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )
        })()}

        {activeTab === 'billing' && (
          <div className="flex flex-col gap-4">
          <div className="flex items-center justify-end">
            <button
              onClick={() => setBillingDetailOpen(true)}
              className="h-8 px-3 text-[12px] font-medium text-brand dark:text-[#EDEEF0] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-md bg-transparent hover:bg-surface-card dark:hover:bg-dark-card transition-colors"
            >
              Billing Detail
            </button>
          </div>
          {invoicesLoading ? (
            <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-auto">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <div key={j} className="h-4 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  ))}
                </div>
              ))}
            </div>
          ) : clientInvoices.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                <span className="text-[18px]">💳</span>
              </div>
              <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                No invoices yet
              </p>
              <p className="text-[12px] text-[#6B7280]">
                Invoices for this client will appear here.
              </p>
            </div>
          ) : (
            <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-surface-card dark:bg-[#252525]">
                    {['Invoice', 'Amount', 'Due', 'Status'].map((col) => (
                      <th key={col} className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {clientInvoices.map((inv, i) => (
                    <tr
                      key={inv.id}
                      onClick={() => router.push(`/billing/${inv.id}`)}
                      className={[
                        'cursor-pointer transition-colors bg-surface-page dark:bg-dark-page hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                        i !== clientInvoices.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card' : '',
                      ].join(' ')}
                    >
                      <td className="px-4 py-3">
                        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{inv.invoiceNumber}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                          {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(inv.totalAmount)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">{inv.dueDate ?? '—'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge variant={inv.status as Parameters<typeof StatusBadge>[0]['variant']} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
          }
          </div>
        )}

        {activeTab === 'irs-auth' && (
          <IrsAuthTab clientId={clientId} />
        )}

        {activeTab === 'organizer' && (
          <TaxOrganizerTab clientId={clientId} userRole={user?.role ?? ''} />
        )}

        {activeTab === 'portal' && (
          <PortalPreview clientId={clientId} clientName={client?.name ?? ''} />
        )}

        {activeTab === 'emails' && (
          <div>
            {emailsNoIntegration ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
                <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">
                  Connect your email in My Integrations to see client email threads.
                </p>
                <a
                  href="/settings?tab=my_integrations"
                  className="text-[12px] font-medium text-[#4A7FA5] hover:underline"
                >
                  Go to My Integrations
                </a>
              </div>
            ) : emailsLoading ? (
              <div className="space-y-0 animate-pulse">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="px-0 py-3 border-b border-[#C8CDD6] dark:border-[#484848]">
                    <div className="h-2.5 bg-[#D5D8DE] dark:bg-[#444444] rounded w-2/5 mb-1.5" />
                    <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-full" />
                  </div>
                ))}
              </div>
            ) : clientEmailThreads.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-2">
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No email threads found</p>
                <p className="text-[12px] text-[#6B7280]">
                  Emails involving this client's address will appear here.
                </p>
              </div>
            ) : (
              <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
                {clientEmailThreads.map((thread, i) => (
                  <a
                    key={`${thread.provider}-${thread.thread_id}`}
                    href={`/inbox?thread_id=${thread.thread_id}&provider=${thread.provider}`}
                    onClick={() => {
                      api.post('/api/v1/inbox/events', { event_type: 'client.email_thread_clicked', client_id: clientId, thread_id: thread.thread_id, provider: thread.provider }).catch(() => {})
                    }}
                    className={[
                      'flex items-start gap-3 px-4 py-3 transition-colors bg-surface-page dark:bg-dark-page hover:bg-[#F3F4F6] dark:hover:bg-[#323232]',
                      i !== clientEmailThreads.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card' : '',
                    ].join(' ')}
                  >
                    {thread.unread && (
                      <div className="w-1.5 h-1.5 rounded-full bg-[#4A7FA5] mt-1.5 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-0.5">
                        <span className={`text-[12px] truncate ${thread.unread ? 'font-semibold text-[#1F3148] dark:text-[#EDEEF0]' : 'font-normal text-[#374151] dark:text-[#9CA3AF]'}`}>
                          {thread.subject || '(no subject)'}
                        </span>
                        <span className="text-[11px] text-[#6B7280] flex-shrink-0">
                          {thread.date ? new Date(thread.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#6B7280] truncate">{thread.snippet}</p>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'messages' && (
          <div className="flex flex-col" style={{ minHeight: 400 }}>
            {/* Messages list */}
            <div className="overflow-y-auto px-4 py-4 space-y-3" style={{ minHeight: 300 }}>
              {messagesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-[#6B7280]" />
                </div>
              ) : clientMessages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-2">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                    <span className="text-[18px]">💬</span>
                  </div>
                  <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No messages yet</p>
                  <p className="text-[12px] text-[#6B7280]">Send the first message below.</p>
                </div>
              ) : (
                clientMessages.map((msg) => {
                  const isStaff = msg.senderRole === 'staff'
                  return (
                    <div key={msg.id} className={`flex flex-col gap-1 ${isStaff ? 'items-end' : 'items-start'}`}>
                      <div
                        className={`max-w-[70%] px-3 py-2 rounded-xl text-[13px] leading-relaxed ${
                          isStaff
                            ? 'bg-[#1F3148] text-white rounded-br-sm'
                            : 'bg-surface-card dark:bg-dark-card text-[#374151] dark:text-[#EDEEF0] rounded-bl-sm border border-[#C8CDD6] dark:border-[#484848]'
                        }`}
                      >
                        {parseMessage(msg.body)}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] text-[#6B7280]">
                          {msg.senderName ?? (isStaff ? 'You' : 'Client')}
                        </span>
                        <span className="text-[11px] text-[#9CA3AF]">
                          {new Date(msg.createdAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Compose box */}
            <div className="flex-shrink-0 border-t border-[#C8CDD6] dark:border-[#484848] px-4 pt-2 pb-3 relative">
              <div className="flex gap-2 items-end">
                <textarea
                  ref={messageComposeRef}
                  value={messageCompose}
                  onChange={(e) => setMessageCompose(e.target.value)}
                  onInput={(e) => {
                    const el = e.currentTarget
                    el.style.height = 'auto'
                    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSendMessage()
                    }
                  }}
                  placeholder="Send a message to this client..."
                  rows={1}
                  className="flex-1 resize-none bg-surface-input dark:bg-dark-page border border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors"
                  style={{ minHeight: 36, maxHeight: 120 }}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!messageCompose.trim() || messageSending}
                  className="flex-shrink-0 h-9 w-9 flex items-center justify-center rounded-lg bg-[#1F3148] text-white hover:bg-[#3A6A94] disabled:opacity-40 transition-colors"
                >
                  {messageSending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>

      <NotesTab unreadCount={unreadNotes} onClick={() => setNotesOpen(true)} />
      <NotesPanel
        isOpen={notesOpen}
        onClose={() => setNotesOpen(false)}
        entityType="client"
        entityId={clientId}
        contextLabel={client.name}
      />

      {isEditOpen && (
        <EditClientModal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          client={client}
          onSuccess={() => { refetchClient(); setIsEditOpen(false) }}
        />
      )}

      <BillingDetailModal
        open={billingDetailOpen}
        onClose={() => setBillingDetailOpen(false)}
        clientId={clientId}
        clientName={client?.name ?? ''}
      />

      <NewEngagementModal
        open={newEngagementOpen}
        onClose={() => { setNewEngagementOpen(false); setInitialEngagementType(undefined) }}
        onAdd={(eng: Engagement) => {
          setNewEngagementOpen(false)
          setInitialEngagementType(undefined)
          void eng
        }}
        preselectedClientId={clientId}
        initialEngagementType={initialEngagementType}
      />
  </>)
}

export default function ClientDetailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </div>
    }>
      <ClientDetailContent />
    </Suspense>
  )
}
