// frontend/src/components/tax-organizer/TaxOrganizerTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { X } from 'lucide-react'
import api from '@/lib/api'

interface TaxOrganizerTabProps {
  clientId: string
  userRole: string
}

interface Template {
  id: string
  name: string
  sections: TemplateSection[]
}

interface TemplateSection {
  title: string
  questions: TemplateQuestion[]
}

interface TemplateQuestion {
  id: string
  label: string
  type: string
  required?: boolean
  options?: string[]
}

interface Engagement {
  id: string
  name: string
}

interface OrganizerListItem {
  id: string
  tax_year: number
  template_id: string
  status: 'sent' | 'in_progress' | 'submitted'
  sent_at: string
  created_at?: string
}

interface OrganizerDetail {
  id: string
  tax_year: number
  template: Template
  responses: Record<string, string>
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })
}

const inputClass =
  'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'
const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'

function TaxOrganizerListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center justify-between px-4 py-3 bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border">
          <div className="flex flex-col gap-1.5">
            <div className="h-4 w-12 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-3 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-3 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          </div>
          <div className="h-5 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full" />
        </div>
      ))}
    </div>
  )
}

export default function TaxOrganizerTab({ clientId, userRole }: TaxOrganizerTabProps) {
  const isManagerPlus = userRole === 'firm_owner' || userRole === 'manager'
  const currentYear = new Date().getFullYear()

  const [templates, setTemplates] = useState<Template[]>([])
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [organizers, setOrganizers] = useState<OrganizerListItem[]>([])
  const [loadingOrganizers, setLoadingOrganizers] = useState(true)

  const [templateId, setTemplateId] = useState('')
  const [engagementId, setEngagementId] = useState('')
  const [taxYear, setTaxYear] = useState(currentYear)
  const [clientMessage, setClientMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [engHint, setEngHint] = useState(false)

  const [viewingOrganizer, setViewingOrganizer] = useState<OrganizerDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [sendingLink, setSendingLink] = useState<string | null>(null)

  function fetchOrganizers() {
    setLoadingOrganizers(true)
    api
      .get('/tax-organizers/', { params: { client_id: clientId } })
      .then((r) => {
        const raw = r.data
        const list: OrganizerListItem[] = Array.isArray(raw) ? raw : (raw?.items ?? [])
        setOrganizers(list)
      })
      .catch(() => {})
      .finally(() => setLoadingOrganizers(false))
  }

  useEffect(() => {
    api
      .get('/tax-organizers/templates')
      .then((r) => {
        const raw = r.data
        const list: Template[] = Array.isArray(raw) ? raw : (raw?.items ?? [])
        setTemplates(list)
        if (list.length > 0) setTemplateId(list[0].id)
      })
      .catch(() => {})

    api
      .get('/engagements/', { params: { client_id: clientId, limit: 50 } })
      .then((r) => {
        const raw = r.data
        const list: Engagement[] = Array.isArray(raw) ? raw : (raw?.items ?? raw?.engagements ?? [])
        setEngagements(list)
      })
      .catch(() => {})

    fetchOrganizers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId])

  async function handleSend() {
    if (!engagementId) {
      setEngHint(true)
      return
    }
    setSending(true)
    try {
      await api.post('/tax-organizers/send', {
        client_id: clientId,
        engagement_id: engagementId,
        template_id: templateId,
        tax_year: taxYear,
        client_message: clientMessage || undefined,
      })
      toast.success('Tax organizer sent')
      setClientMessage('')
      setEngagementId('')
      setEngHint(false)
      fetchOrganizers()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to send organizer')
    } finally {
      setSending(false)
    }
  }

  async function handleSendLink(organizerId: string) {
    setSendingLink(organizerId)
    try {
      await api.post(`/tax-organizers/${organizerId}/send-link`)
      toast.success('Portal link sent to client')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail
      toast.error(detail ?? 'Failed to send link')
    } finally {
      setSendingLink(null)
    }
  }

  async function handleViewResponses(organizerId: string) {
    setLoadingDetail(true)
    try {
      const r = await api.get(`/tax-organizers/${organizerId}`)
      setViewingOrganizer(r.data as OrganizerDetail)
    } catch {
      toast.error('Failed to load responses')
    } finally {
      setLoadingDetail(false)
    }
  }

  function getTemplateName(tmplId: string): string {
    return templates.find((t) => t.id === tmplId)?.name ?? '—'
  }

  function statusBadge(status: string) {
    if (status === 'sent')
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
          Sent
        </span>
      )
    if (status === 'in_progress')
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
          In Progress
        </span>
      )
    if (status === 'submitted')
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
          Submitted
        </span>
      )
    return null
  }

  return (
    <div className="flex flex-col gap-4">
      {isManagerPlus && (
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-4 flex flex-col gap-4">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Send Tax Organizer</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Template</label>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className={inputClass}
              >
                {templates.length === 0 && <option value="">No templates available</option>}
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Engagement *</label>
              <select
                value={engagementId}
                onChange={(e) => {
                  setEngagementId(e.target.value)
                  setEngHint(false)
                }}
                className={inputClass}
              >
                <option value="">Select engagement...</option>
                {engagements.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                  </option>
                ))}
              </select>
              {engHint && (
                <span className="text-[11px] text-amber-500">Please select an engagement</span>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Tax Year</label>
              <input
                type="number"
                min={2000}
                max={currentYear + 1}
                value={taxYear}
                onChange={(e) => setTaxYear(Number(e.target.value))}
                className={inputClass}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Message to Client</label>
            <textarea
              rows={2}
              maxLength={500}
              value={clientMessage}
              onChange={(e) => setClientMessage(e.target.value)}
              placeholder="Add a personal message to the client (optional)"
              className={`${inputClass} resize-none`}
            />
          </div>

          <button
            onClick={handleSend}
            disabled={sending || !templateId}
            className="w-full h-9 rounded-[6px] bg-[#1F3148] text-white text-[13px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity"
          >
            {sending ? 'Sending...' : 'Send Tax Organizer'}
          </button>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {loadingOrganizers ? (
          <TaxOrganizerListSkeleton />
        ) : organizers.length === 0 ? (
          <div className="text-[13px] text-[#6B7280] py-8 text-center">
            No tax organizers sent yet. Send one above to collect structured tax information from
            this client.
          </div>
        ) : (
          organizers.map((org) => (
            <div
              key={org.id}
              className="flex items-center justify-between px-4 py-3 bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                  {org.tax_year}
                </span>
                <span className="text-[12px] text-[#6B7280]">
                  {getTemplateName(org.template_id)}
                </span>
                <span className="text-[11px] text-[#9CA3AF]">
                  {formatDate(org.created_at)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                {statusBadge(org.status)}
                {org.status === 'submitted' && (
                  <button
                    onClick={() => handleViewResponses(org.id)}
                    disabled={loadingDetail}
                    className="text-[12px] text-[#3A6A94] hover:text-[#4A7FA5] font-medium disabled:opacity-60"
                  >
                    View Responses
                  </button>
                )}
                {org.status !== 'submitted' && (
                  <button
                    onClick={() => handleSendLink(org.id)}
                    disabled={sendingLink === org.id}
                    className="text-[12px] font-medium text-brand dark:text-[#4A7FA5]
                      hover:underline disabled:opacity-50 disabled:no-underline"
                  >
                    {sendingLink === org.id ? 'Sending...' : 'Resend Magic Link'}
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {viewingOrganizer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-dark-card rounded-[10px] shadow-xl w-full max-w-2xl mx-4 flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border dark:border-dark-border flex-shrink-0">
              <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">
                Tax Organizer Responses — {viewingOrganizer.tax_year}
              </p>
              <button
                onClick={() => setViewingOrganizer(null)}
                className="p-1 rounded hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
              >
                <X className="h-4 w-4 text-[#6B7280]" />
              </button>
            </div>

            <div className="overflow-y-auto px-5 py-4 flex flex-col gap-5 flex-1">
              {viewingOrganizer.template.sections.map((section, si) => (
                <div key={si} className="flex flex-col gap-2">
                  <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] pb-1 border-b border-surface-border dark:border-dark-border">
                    {section.title}
                  </p>
                  {section.questions.map((q) => {
                    const answer = viewingOrganizer.responses?.[q.id]
                    return (
                      <div key={q.id} className="flex flex-col gap-0.5">
                        <span className="text-[11px] text-[#6B7280]">{q.label}</span>
                        {answer ? (
                          <span className="text-[13px] text-brand dark:text-[#EDEEF0]">
                            {answer}
                          </span>
                        ) : (
                          <span className="text-[13px] text-[#9CA3AF]">—</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>

            <div className="flex justify-end px-5 py-3 border-t border-surface-border dark:border-dark-border flex-shrink-0">
              <button
                onClick={() => setViewingOrganizer(null)}
                className="px-4 py-2 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
