// frontend/src/components/portal/PortalOrganizer.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { Briefcase, Calendar, Check, ChevronRight, DollarSign, FileText, Home, Info, Receipt, TrendingUp, User } from 'lucide-react'

interface PortalOrganizerProps {
  clientId: string
  initialOrganizerId?: string | null
  cardColor?: string
  portalMode?: 'light' | 'dark'
  textPrimary?: string
  textMuted?: string
}

interface OrganizerListItem {
  id: string
  tax_year: number
  status: 'sent' | 'in_progress' | 'submitted'
  client_message?: string
  submitted_at?: string
}

interface Question {
  id: string
  label: string
  type: 'text' | 'number' | 'boolean' | 'select' | 'textarea'
  required?: boolean
  options?: string[]
}

interface Section {
  id: string
  title: string
  description?: string
  questions: Question[]
}

interface OrganizerDetail {
  id: string
  tax_year: number
  status: string
  template: { sections: Section[] }
  responses: Record<string, Record<string, string>>
  submitted_at?: string
  client_message?: string
}

function portalFetch(path: string, options?: RequestInit): Promise<Response> {
  const token =
    typeof window !== 'undefined' ? localStorage.getItem('portal_access_token') : null
  return fetch(`/api/backend${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...((options?.headers as Record<string, string>) ?? {}),
    },
  })
}

const inputClass =
  'w-full rounded-[6px] border border-[#C8CDD6] bg-white focus:border-[#1F3148] text-[#1F3148] text-[13px] px-3 py-2 outline-none transition-colors'

type SectionStatus = 'complete' | 'in_progress' | 'not_started'

function getSectionStatus(section: Section, responses: Record<string, Record<string, string>>): SectionStatus {
  const sectionResponses = responses[section.id] ?? {}
  const answered = section.questions.filter(
    (q) => sectionResponses[q.id] != null && String(sectionResponses[q.id]).trim() !== ''
  )
  if (answered.length === 0) return 'not_started'
  const required = section.questions.filter((q) => q.required)
  // When no questions are required, all must be answered for Complete.
  // An empty required list satisfies every() vacuously, so we explicitly
  // fall back to the full question list as the completion target.
  const completionSet = required.length > 0 ? required : section.questions
  if (completionSet.every((q) => sectionResponses[q.id] != null && String(sectionResponses[q.id]).trim() !== '')) {
    return 'complete'
  }
  return 'in_progress'
}

const STATUS_CONFIG: Record<SectionStatus, {
  chipBg: string
  chipColor: string
  label: string
  labelColor: string
}> = {
  complete: {
    chipBg: '#D1FAE5',
    chipColor: '#059669',
    label: 'Complete',
    labelColor: '#059669',
  },
  in_progress: {
    chipBg: '#FEF3C7',
    chipColor: '#D97706',
    label: 'In progress',
    labelColor: '#D97706',
  },
  not_started: {
    chipBg: '#F3F4F6',
    chipColor: '#9CA3AF',
    label: 'Not started',
    labelColor: '#9CA3AF',
  },
}

function getSectionIcon(title: string): React.ComponentType<{ size?: number; style?: React.CSSProperties }> {
  const t = title.toLowerCase()
  if (t.includes('personal') || t.includes('individual')) return User
  if (t.includes('income') || t.includes('wages') || t.includes('salary')) return DollarSign
  if (t.includes('deduction') || t.includes('adjust')) return FileText
  if (t.includes('tax payment') || t.includes('withhold') || t.includes('estimated')) return Receipt
  if (t.includes('invest') || t.includes('capital') || t.includes('dividend')) return TrendingUp
  if (t.includes('business') || t.includes('self-employ')) return Briefcase
  if (t.includes('home') || t.includes('property') || t.includes('mortgage')) return Home
  return FileText
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function PortalOrganizer({ clientId: _clientId, initialOrganizerId = null, cardColor: _cardColor, portalMode: _portalMode, textPrimary: _textPrimary, textMuted: _textMuted }: PortalOrganizerProps) {
  const [organizers, setOrganizers] = useState<OrganizerListItem[]>([])
  const [loading, setLoading] = useState(true)

  const [activeOrganizer, setActiveOrganizer] = useState<OrganizerDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [readOnly, setReadOnly] = useState(false)
  const [readOnlyFromList, setReadOnlyFromList] = useState(false)

  const [sectionIndex, setSectionIndex] = useState<number | null>(null)
  const [responses, setResponses] = useState<Record<string, Record<string, string>>>({})
  const [requiredHints, setRequiredHints] = useState<Record<string, boolean>>({})

  const [saving, setSaving] = useState(false)
  const [savedNotice, setSavedNotice] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  function loadOrganizers() {
    setLoading(true)
    portalFetch('/portal/organizers')
      .then(async (res) => {
        if (!res.ok) return
        const data: unknown = await res.json()
        const list: OrganizerListItem[] = Array.isArray(data)
          ? (data as OrganizerListItem[])
          : ((data as { items?: OrganizerListItem[] })?.items ?? [])
        setOrganizers(list)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadOrganizers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const deepLinkHandled = useRef(false)

  useEffect(() => {
    if (!initialOrganizerId || loading || organizers.length === 0 || deepLinkHandled.current) return
    const match = organizers.find((o) => o.id === initialOrganizerId)
    if (match) {
      deepLinkHandled.current = true
      openOrganizer(match.id, match.status === 'submitted')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, organizers])

  async function openOrganizer(id: string, isReadOnly: boolean) {
    setLoadingDetail(true)
    setSubmitted(false)
    setSectionIndex(null)
    setRequiredHints({})
    try {
      const res = await portalFetch(`/portal/organizers/${id}`)
      if (!res.ok) return
      const data = (await res.json()) as OrganizerDetail
      setActiveOrganizer(data)
      setResponses(data.responses ?? {})
      setReadOnly(isReadOnly)
      setReadOnlyFromList(isReadOnly)
    } catch {
      // ignore
    } finally {
      setLoadingDetail(false)
    }
  }

  function closeOrganizer() {
    setActiveOrganizer(null)
    setSubmitted(false)
    setReadOnly(false)
    setReadOnlyFromList(false)
    setSectionIndex(null)
    loadOrganizers()
  }

  async function saveProgress(submit = false) {
    if (!activeOrganizer) return
    setSaving(true)
    try {
      await portalFetch(`/portal/organizers/${activeOrganizer.id}/save`, {
        method: 'POST',
        body: JSON.stringify({ responses, submit }),
      })
      if (!submit) {
        setSavedNotice(true)
        setTimeout(() => setSavedNotice(false), 2000)
      }
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  function validateSection(section: Section): boolean {
    const hints: Record<string, boolean> = {}
    let valid = true
    for (const q of section.questions) {
      if (q.required && !responses[section.id]?.[q.id]) {
        hints[q.id] = true
        valid = false
      }
    }
    setRequiredHints(hints)
    return valid
  }

  async function handleSectionNext(idx: number) {
    if (!activeOrganizer) return
    const sections = activeOrganizer.template.sections
    const section = sections[idx]
    if (!validateSection(section)) return
    if (idx < sections.length - 1) {
      setSectionIndex(idx + 1)
      setRequiredHints({})
    } else {
      await saveProgress(true)
      setSubmitted(true)
    }
  }

  function handleAnswerChange(sectionId: string, questionId: string, value: string) {
    setResponses((r) => ({
      ...r,
      [sectionId]: {
        ...(r[sectionId] ?? {}),
        [questionId]: value,
      },
    }))
    if (requiredHints[questionId]) {
      setRequiredHints((h) => ({ ...h, [questionId]: false }))
    }
  }

  function renderQuestion(q: Question, sectionId: string) {
    const value = responses[sectionId]?.[q.id] ?? ''
    const hint = requiredHints[q.id]

    let input: React.ReactNode

    if (q.type === 'boolean') {
      input = (
        <div className="flex gap-2">
          {['Yes', 'No'].map((opt) => (
            <button
              key={opt}
              type="button"
              disabled={readOnly}
              onClick={() => handleAnswerChange(sectionId, q.id, opt)}
              className="px-4 py-1.5 rounded-full text-[13px] font-medium transition-colors disabled:cursor-default"
              style={{
                backgroundColor: value === opt ? '#1F3148' : '#F3F4F6',
                color: value === opt ? '#FFFFFF' : '#6B7280',
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      )
    } else if (q.type === 'select') {
      input = (
        <select
          value={value}
          disabled={readOnly}
          onChange={(e) => handleAnswerChange(sectionId, q.id, e.target.value)}
          className={`${inputClass} disabled:opacity-70`}
        >
          <option value="">Select...</option>
          {(q.options ?? []).map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      )
    } else if (q.type === 'textarea') {
      input = (
        <textarea
          rows={3}
          value={value}
          disabled={readOnly}
          onChange={(e) => handleAnswerChange(sectionId, q.id, e.target.value)}
          className={`${inputClass} resize-none disabled:opacity-70`}
        />
      )
    } else if (q.type === 'number') {
      const formatted = value && value.trim()
        ? Number(value.replace(/,/g, '')).toLocaleString('en-US')
        : ''
      input = (
        <div className="relative flex items-center">
          <span
            className="absolute left-3 select-none pointer-events-none text-[13px]"
            style={{ color: '#6B7280' }}
          >
            $
          </span>
          <input
            type="text"
            inputMode="decimal"
            value={formatted}
            disabled={readOnly}
            onChange={(e) => {
              const raw = e.target.value.replace(/,/g, '').replace(/[^0-9.]/g, '')
              handleAnswerChange(sectionId, q.id, raw)
            }}
            className={`${inputClass} pl-7 disabled:opacity-70`}
          />
        </div>
      )
    } else {
      input = (
        <input
          type="text"
          value={value}
          disabled={readOnly}
          onChange={(e) => handleAnswerChange(sectionId, q.id, e.target.value)}
          className={`${inputClass} disabled:opacity-70`}
        />
      )
    }

    return (
      <div key={q.id} className="flex flex-col gap-1">
        <label className="text-[13px]" style={{ color: '#6B7280' }}>
          {q.label}
          {q.required && !readOnly && <span className="ml-0.5" style={{ color: '#DC2626' }}>*</span>}
        </label>
        {input}
        {hint && <span className="text-[11px]" style={{ color: '#DC2626' }}>This field is required</span>}
      </div>
    )
  }

  // ---- SUBMITTED ----
  if (submitted) {
    return (
      <div className="p-6 flex flex-col items-center justify-center gap-4 py-16">
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center"
          style={{ backgroundColor: '#D1FAE5' }}
        >
          <Check className="h-6 w-6" style={{ color: '#059669' }} />
        </div>
        <p className="text-[16px] font-semibold text-center" style={{ color: '#1F3148' }}>
          Thank you! Your tax organizer has been submitted.
        </p>
        <p className="text-[13px] text-center" style={{ color: '#6B7280' }}>
          Your accountant will review your responses.
        </p>
        <button
          onClick={closeOrganizer}
          className="mt-4 h-9 px-6 rounded-lg text-[13px] font-medium text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: '#1F3148' }}
        >
          Back to organizers
        </button>
      </div>
    )
  }

  // ---- LOADING DETAIL ----
  if (loadingDetail) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-col gap-3">
          <div className="h-3 w-36 rounded animate-pulse bg-gray-100" />
          <div className="h-2 w-full rounded-full animate-pulse bg-gray-100" />
          <div className="h-3 w-16 rounded animate-pulse bg-gray-100" />
        </div>
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-3 p-4 border-b border-gray-100 last:border-b-0">
              <div className="w-8 h-8 rounded-full animate-pulse bg-gray-100 flex-shrink-0" />
              <div className="flex-1 flex flex-col gap-1.5">
                <div className="h-3 w-40 rounded animate-pulse bg-gray-100" />
                <div className="h-2.5 w-56 rounded animate-pulse bg-gray-100" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ---- READ-ONLY SUMMARY ----
  if (activeOrganizer && readOnly) {
    const sections = activeOrganizer.template.sections
    return (
      <div className="p-6 flex flex-col gap-4 max-w-[680px]">
        <button
          onClick={() => {
            if (readOnlyFromList) {
              closeOrganizer()
            } else {
              setReadOnly(false)
              setSectionIndex(null)
            }
          }}
          className="self-start text-[13px] transition-opacity hover:opacity-70"
          style={{ color: '#6B7280' }}
        >
          {readOnlyFromList ? 'Back to organizers' : 'Back to organizer'}
        </button>

        {activeOrganizer.submitted_at && (
          <div
            className="rounded-xl px-4 py-3 border"
            style={{ backgroundColor: '#D1FAE5', borderColor: '#A7F3D0' }}
          >
            <p className="text-[12px]" style={{ color: '#059669' }}>
              Submitted on{' '}
              {new Date(activeOrganizer.submitted_at).toLocaleDateString('en-US', {
                month: 'long', day: 'numeric', year: 'numeric',
              })}
            </p>
          </div>
        )}

        {sections.map((section, si) => (
          <div key={si} className="bg-white rounded-xl border border-gray-100 p-5 flex flex-col gap-4">
            <div>
              <p className="text-[15px] font-semibold" style={{ color: '#1F3148' }}>{section.title}</p>
              {section.description && (
                <p className="text-[12px] mt-0.5" style={{ color: '#6B7280' }}>{section.description}</p>
              )}
            </div>
            <div className="flex flex-col gap-4">
              {section.questions.map((q) => renderQuestion(q, section.id))}
            </div>
          </div>
        ))}

        <div className="flex justify-center pb-4">
          <button
            onClick={() => {
              if (readOnlyFromList) {
                closeOrganizer()
              } else {
                setReadOnly(false)
                setSectionIndex(null)
              }
            }}
            className="h-9 px-6 rounded-lg text-[13px] border border-gray-200 transition-colors hover:bg-gray-50"
            style={{ color: '#6B7280' }}
          >
            Close
          </button>
        </div>
      </div>
    )
  }

  // ---- SECTION FORM ----
  if (activeOrganizer && sectionIndex !== null) {
    const sections = activeOrganizer.template.sections
    const section = sections[sectionIndex]
    const isLast = sectionIndex === sections.length - 1

    return (
      <div className="p-6 flex flex-col gap-4 max-w-[680px]">
        <button
          onClick={() => { setSectionIndex(null); setRequiredHints({}) }}
          className="self-start text-[13px] transition-opacity hover:opacity-70"
          style={{ color: '#6B7280' }}
        >
          Back to sections
        </button>

        <p className="text-[12px]" style={{ color: '#9CA3AF' }}>
          Section {sectionIndex + 1} of {sections.length}
        </p>

        <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-col gap-4">
          <div>
            <p className="text-[15px] font-semibold" style={{ color: '#1F3148' }}>{section.title}</p>
            {section.description && (
              <p className="text-[12px] mt-0.5" style={{ color: '#6B7280' }}>{section.description}</p>
            )}
          </div>
          <div className="flex flex-col gap-4">
            {section.questions.map((q) => renderQuestion(q, section.id))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => { setSectionIndex(null); setRequiredHints({}) }}
            className="flex-1 h-9 rounded-lg text-[13px] border border-gray-200 transition-colors hover:bg-gray-50"
            style={{ color: '#6B7280' }}
          >
            Back
          </button>
          <button
            onClick={() => saveProgress(false)}
            disabled={saving}
            className="flex-1 h-9 rounded-lg text-[13px] border border-gray-200 transition-colors hover:bg-gray-50 disabled:opacity-60"
            style={{ color: '#6B7280' }}
          >
            {savedNotice ? 'Saved' : saving ? 'Saving...' : 'Save progress'}
          </button>
          <button
            onClick={() => handleSectionNext(sectionIndex)}
            disabled={saving}
            className="flex-1 h-9 rounded-lg text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
            style={{ backgroundColor: '#1F3148' }}
          >
            {isLast ? 'Submit' : 'Continue'}
          </button>
        </div>
      </div>
    )
  }

  // ---- SECTION OVERVIEW ----
  if (activeOrganizer) {
    const sections = activeOrganizer.template.sections
    const completedCount = sections.filter((s) => getSectionStatus(s, responses) === 'complete').length
    const pct = sections.length > 0 ? Math.round((completedCount / sections.length) * 100) : 0

    return (
      <div className="p-6 flex flex-col gap-5">
        <button
          onClick={closeOrganizer}
          className="self-start text-[13px] transition-opacity hover:opacity-70"
          style={{ color: '#6B7280' }}
        >
          Back to organizers
        </button>

        <div>
          <h1 className="text-[20px] font-bold" style={{ color: '#1F3148' }}>
            Tax Organizer {activeOrganizer.tax_year}
          </h1>
          <p className="text-[13px] mt-0.5" style={{ color: '#6B7280' }}>
            {activeOrganizer.client_message || 'Complete the sections below and upload your documents.'}
          </p>
        </div>

        {/* Progress card */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <div className="flex items-start gap-6">
            <div className="flex-1 flex flex-col gap-2 min-w-0">
              <p className="text-[12px]" style={{ color: '#6B7280' }}>Your progress</p>
              <div className="flex items-center justify-between">
                <p className="text-[14px] font-medium" style={{ color: '#1F3148' }}>
                  {completedCount} of {sections.length} sections complete
                </p>
                <p className="text-[13px] font-semibold" style={{ color: '#1F3148' }}>{pct}%</p>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#F3F4F6' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: '#F59E0B' }}
                />
              </div>
            </div>

            <div className="flex flex-col gap-1 flex-shrink-0 min-w-[140px]">
              <p className="text-[12px]" style={{ color: '#6B7280' }}>Due date</p>
              <div className="flex items-center gap-1.5">
                <Calendar size={13} style={{ color: '#9CA3AF' }} />
                <p className="text-[13px]" style={{ color: '#9CA3AF' }}>Not set</p>
              </div>
            </div>

            <button
              onClick={() => setReadOnly(true)}
              className="h-9 px-4 rounded-lg text-[13px] font-medium text-white flex-shrink-0 self-start transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#1F3148' }}
            >
              View summary
            </button>
          </div>
        </div>

        {/* Section list + help panel */}
        <div className="flex gap-5 items-start">
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            <p className="text-[14px] font-semibold" style={{ color: '#1F3148' }}>Organizer sections</p>
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              {sections.map((section, idx) => {
                const status = getSectionStatus(section, responses)
                const cfg = STATUS_CONFIG[status]
                const TopicIcon = getSectionIcon(section.title)
                return (
                  <button
                    key={idx}
                    onClick={() => { setSectionIndex(idx); setRequiredHints({}) }}
                    className="w-full flex items-center gap-3 p-4 text-left transition-colors hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                  >
                    <div
                      className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center"
                      style={{ backgroundColor: cfg.chipBg }}
                    >
                      <TopicIcon size={14} style={{ color: cfg.chipColor }} />
                    </div>
                    <div className="flex-1 min-w-0 text-left">
                      <p className="text-[13px] font-medium" style={{ color: '#1F3148' }}>{section.title}</p>
                      {section.description && (
                        <p className="text-[12px] mt-0.5" style={{ color: '#6B7280' }}>{section.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-[12px] font-medium" style={{ color: cfg.labelColor }}>
                        {cfg.label}
                      </span>
                      <ChevronRight size={14} style={{ color: '#9CA3AF' }} />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Help panel */}
          <div className="w-[200px] flex-shrink-0 flex flex-col gap-3">
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <p className="text-[13px] font-semibold mb-1" style={{ color: '#1F3148' }}>Need help?</p>
              <p className="text-[12px] mb-3" style={{ color: '#6B7280' }}>
                Let us know if you have questions about any sections.
              </p>
              <button
                className="w-full h-8 rounded-lg text-[12px] font-medium text-white transition-opacity hover:opacity-90"
                style={{ backgroundColor: '#1F3148' }}
              >
                Send a message
              </button>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <div className="flex items-start gap-2">
                <div
                  className="w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5"
                  style={{ backgroundColor: '#DBEAFE' }}
                >
                  <Info size={12} style={{ color: '#1E40AF' }} />
                </div>
                <div>
                  <p className="text-[11px] font-semibold mb-0.5" style={{ color: '#1F3148' }}>Tip</p>
                  <p className="text-[11px]" style={{ color: '#6B7280' }}>
                    You can save your progress and return to any section at any time.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ---- ORGANIZER LIST ----
  return (
    <div className="p-6 flex flex-col gap-4">
      <div>
        <h1 className="text-[20px] font-bold" style={{ color: '#1F3148' }}>Tax Organizer</h1>
        <p className="text-[13px] mt-0.5" style={{ color: '#6B7280' }}>
          Your personalized tax organizer. Complete the sections below and upload your documents.
        </p>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {[1, 2].map((i) => (
            <div key={i} className="flex items-center gap-4 p-4 border-b border-gray-100 last:border-b-0">
              <div className="flex-1 flex flex-col gap-1.5">
                <div className="h-3 w-24 rounded animate-pulse bg-gray-100" />
                <div className="h-2.5 w-40 rounded animate-pulse bg-gray-100" />
              </div>
              <div className="h-5 w-20 rounded-full animate-pulse bg-gray-100 flex-shrink-0" />
              <div className="w-3.5 h-3.5 animate-pulse bg-gray-100 flex-shrink-0" />
            </div>
          ))}
        </div>
      ) : organizers.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 p-10 text-center">
          <p className="text-[13px]" style={{ color: '#6B7280' }}>
            Your accountant has not sent you a tax organizer yet. Check back here when your tax preparation begins.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {organizers.map((org) => {
            const isSubmitted = org.status === 'submitted'
            const isInProgress = org.status === 'in_progress'
            const statusLabel = isSubmitted ? 'Submitted' : isInProgress ? 'In progress' : 'Ready to complete'
            const statusColor = isSubmitted ? '#059669' : '#D97706'
            const statusBg = isSubmitted ? '#D1FAE5' : '#FEF3C7'

            return (
              <button
                key={org.id}
                onClick={() => openOrganizer(org.id, isSubmitted)}
                className="w-full flex items-center gap-4 p-4 text-left transition-colors hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] font-semibold" style={{ color: '#1F3148' }}>
                    {org.tax_year} Tax Organizer
                  </p>
                  {org.client_message && (
                    <p className="text-[12px] mt-0.5 truncate" style={{ color: '#6B7280' }}>
                      {org.client_message}
                    </p>
                  )}
                </div>
                <span
                  className="text-[11px] font-medium px-2.5 py-0.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: statusBg, color: statusColor }}
                >
                  {statusLabel}
                </span>
                <ChevronRight size={14} style={{ color: '#9CA3AF' }} className="flex-shrink-0" />
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
