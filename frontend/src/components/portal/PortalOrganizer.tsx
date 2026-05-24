// frontend/src/components/portal/PortalOrganizer.tsx
'use client'

import { useState, useEffect } from 'react'
import { Check } from 'lucide-react'

interface PortalOrganizerProps {
  clientId: string
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
  title: string
  description?: string
  questions: Question[]
}

interface OrganizerDetail {
  id: string
  tax_year: number
  status: string
  template: { sections: Section[] }
  responses: Record<string, string>
  submitted_at?: string
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

function getInputClass(portalMode: 'light' | 'dark') {
  return portalMode === 'light'
    ? 'w-full rounded-[6px] border border-[#C8CDD6] bg-white focus:border-[#1F3148] text-[#1F3148] text-[13px] px-3 py-2 outline-none transition-colors'
    : 'w-full rounded-[6px] border border-[#484848] bg-[#2D2D2D] focus:border-[#4A7FA5] text-[#EDEEF0] text-[13px] px-3 py-2 outline-none transition-colors'
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function PortalOrganizer({ clientId: _clientId, cardColor = '#383838', portalMode = 'dark', textPrimary = '#EDEEF0', textMuted = '#9CA3AF' }: PortalOrganizerProps) {
  const primaryText = textPrimary
  const mutedText = textMuted

  const [organizers, setOrganizers] = useState<OrganizerListItem[]>([])
  const [loading, setLoading] = useState(true)

  const [activeOrganizer, setActiveOrganizer] = useState<OrganizerDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [readOnly, setReadOnly] = useState(false)

  const [currentSection, setCurrentSection] = useState(0)
  const [responses, setResponses] = useState<Record<string, string>>({})
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

  async function openOrganizer(id: string, isReadOnly: boolean) {
    setLoadingDetail(true)
    setSubmitted(false)
    setCurrentSection(0)
    setRequiredHints({})
    try {
      const res = await portalFetch(`/portal/organizers/${id}`)
      if (!res.ok) return
      const data = (await res.json()) as OrganizerDetail
      setActiveOrganizer(data)
      setResponses(data.responses ?? {})
      setReadOnly(isReadOnly)
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
      if (q.required && !responses[q.id]) {
        hints[q.id] = true
        valid = false
      }
    }
    setRequiredHints(hints)
    return valid
  }

  async function handleNext() {
    if (!activeOrganizer) return
    const sections = activeOrganizer.template.sections
    const section = sections[currentSection]
    if (!validateSection(section)) return
    if (currentSection < sections.length - 1) {
      setCurrentSection((s) => s + 1)
      setRequiredHints({})
    } else {
      await saveProgress(true)
      setSubmitted(true)
    }
  }

  function handleAnswerChange(questionId: string, value: string) {
    setResponses((r) => ({ ...r, [questionId]: value }))
    if (requiredHints[questionId]) {
      setRequiredHints((h) => ({ ...h, [questionId]: false }))
    }
  }

  function renderQuestion(q: Question) {
    const value = responses[q.id] ?? ''
    const hint = requiredHints[q.id]
    const inputClass = getInputClass(portalMode)

    let input: React.ReactNode

    if (q.type === 'boolean') {
      input = (
        <div className="flex gap-2">
          {['Yes', 'No'].map((opt) => (
            <button
              key={opt}
              type="button"
              disabled={readOnly}
              onClick={() => handleAnswerChange(q.id, opt)}
              className={`px-4 py-1.5 rounded-full text-[13px] font-medium transition-colors disabled:cursor-default ${
                value === opt ? 'text-white' : ''
              }`}
              style={{
                backgroundColor: value === opt ? '#3A6A94' : cardColor,
                color: value === opt ? '#FFFFFF' : mutedText,
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
          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
          className={`${inputClass} disabled:opacity-70`}
        >
          <option value="">Select...</option>
          {(q.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      )
    } else if (q.type === 'textarea') {
      input = (
        <textarea
          rows={3}
          value={value}
          disabled={readOnly}
          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
          className={`${inputClass} resize-none disabled:opacity-70`}
        />
      )
    } else if (q.type === 'number') {
      input = (
        <input
          type="number"
          value={value}
          disabled={readOnly}
          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
          className={`${inputClass} disabled:opacity-70`}
        />
      )
    } else {
      input = (
        <input
          type="text"
          value={value}
          disabled={readOnly}
          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
          className={`${inputClass} disabled:opacity-70`}
        />
      )
    }

    return (
      <div key={q.id} className="flex flex-col gap-1">
        <label className="text-[13px]" style={{ color: mutedText }}>
          {q.label}
          {q.required && !readOnly && <span className="text-amber-400 ml-0.5">*</span>}
        </label>
        {input}
        {hint && <span className="text-[11px] text-amber-400">This field is required</span>}
      </div>
    )
  }

  if (submitted) {
    return (
      <div className="p-5 max-w-2xl mx-auto w-full flex flex-col items-center justify-center gap-4 py-16">
        <div className="w-12 h-12 rounded-full bg-green-600 flex items-center justify-center">
          <Check className="h-6 w-6 text-white" />
        </div>
        <p className="text-[16px] font-medium text-center" style={{ color: primaryText }}>
          Thank you! Your tax organizer has been submitted.
        </p>
        <p className="text-[13px] text-center" style={{ color: mutedText }}>
          Your accountant will review your responses.
        </p>
        <button
          onClick={closeOrganizer}
          className="mt-4 px-6 py-2 rounded-[6px] bg-[#3A6A94] text-[13px] font-medium hover:bg-[#4A7FA5] transition-colors"
          style={{ color: '#EDEEF0' }}
        >
          Back to organizers
        </button>
      </div>
    )
  }

  if (loadingDetail) {
    return (
      <div className="p-5 max-w-2xl mx-auto w-full flex flex-col gap-3">
        {[1, 2].map((i) => (
          <div key={i} className="h-16 rounded-[8px] animate-pulse" style={{ backgroundColor: cardColor }} />
        ))}
      </div>
    )
  }

  if (activeOrganizer) {
    const sections = activeOrganizer.template.sections

    if (readOnly) {
      return (
        <div className="p-5 max-w-2xl mx-auto w-full flex flex-col gap-4">
          <button
            onClick={closeOrganizer}
            className="self-start text-[13px] transition-colors"
            style={{ color: mutedText }}
          >
            ← Back to organizers
          </button>

          {activeOrganizer.submitted_at && (
            <div className="bg-green-900/20 border border-green-700/40 rounded-[6px] px-4 py-2">
              <p className="text-[12px] text-green-400">
                Submitted on{' '}
                {new Date(activeOrganizer.submitted_at).toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </p>
            </div>
          )}

          {sections.map((section, si) => (
            <div key={si} className="rounded-[8px] p-5 flex flex-col gap-4" style={{ backgroundColor: cardColor }}>
              <div>
                <p className="text-[16px] font-medium" style={{ color: primaryText }}>{section.title}</p>
                {section.description && (
                  <p className="text-[12px] mt-1" style={{ color: mutedText }}>{section.description}</p>
                )}
              </div>
              <div className="flex flex-col gap-4">
                {section.questions.map((q) => renderQuestion(q))}
              </div>
            </div>
          ))}

          <div className="flex justify-center">
            <button
              onClick={closeOrganizer}
              className="px-6 h-9 rounded-[6px] text-[13px] transition-colors"
              style={{ border: `1px solid ${mutedText}`, color: mutedText }}
            >
              Close
            </button>
          </div>
        </div>
      )
    }

    const section = sections[currentSection]
    const isFirst = currentSection === 0
    const isLast = currentSection === sections.length - 1

    return (
      <div className="p-5 max-w-2xl mx-auto w-full flex flex-col gap-4">
        <button
          onClick={closeOrganizer}
          className="self-start text-[13px] transition-colors"
          style={{ color: mutedText }}
        >
          ← Back to organizers
        </button>

        <p className="text-[12px] text-center" style={{ color: mutedText }}>
          Section {currentSection + 1} of {sections.length}
        </p>

        <div className="rounded-[8px] p-5 flex flex-col gap-4" style={{ backgroundColor: cardColor }}>
          <div>
            <p className="text-[16px] font-medium" style={{ color: primaryText }}>{section.title}</p>
            {section.description && (
              <p className="text-[12px] mt-1" style={{ color: mutedText }}>{section.description}</p>
            )}
          </div>
          <div className="flex flex-col gap-4">
            {section.questions.map((q) => renderQuestion(q))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setCurrentSection((s) => s - 1)
              setRequiredHints({})
            }}
            disabled={isFirst}
            className="flex-1 h-9 rounded-[6px] text-[13px] disabled:opacity-0 transition-colors"
            style={{ border: `1px solid ${mutedText}`, color: mutedText }}
          >
            Previous
          </button>
          <button
            onClick={() => saveProgress(false)}
            disabled={saving}
            className="flex-1 h-9 rounded-[6px] text-[13px] transition-colors"
            style={{ border: `1px solid ${mutedText}`, color: mutedText }}
          >
            {savedNotice ? 'Saved' : saving ? 'Saving...' : 'Save Progress'}
          </button>
          <button
            onClick={handleNext}
            disabled={saving}
            className="flex-1 h-9 rounded-[6px] text-[13px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity"
            style={{ backgroundColor: '#1F3148', color: '#EDEEF0' }}
          >
            {isLast ? 'Submit' : 'Next'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-5 max-w-2xl mx-auto w-full flex flex-col gap-3">
      {loading ? (
        [1, 2].map((i) => (
          <div key={i} className="h-16 rounded-[8px] animate-pulse" style={{ backgroundColor: cardColor }} />
        ))
      ) : organizers.length === 0 ? (
        <div className="text-[13px] py-12 text-center" style={{ color: mutedText }}>
          Your accountant hasn&apos;t sent you a tax organizer yet. Check back here when your tax
          preparation begins.
        </div>
      ) : (
        organizers.map((org) => {
          const isSubmitted = org.status === 'submitted'
          const isInProgress = org.status === 'in_progress'
          const isSent = org.status === 'sent'

          return (
            <div key={org.id} className="rounded-[8px] p-4 flex flex-col gap-2" style={{ backgroundColor: cardColor }}>
              <div className="flex items-center justify-between">
                <p className="text-[14px] font-medium" style={{ color: primaryText }}>{org.tax_year}</p>
                {isSubmitted && (
                  <span className="flex items-center gap-1 text-[12px] text-green-400 font-medium">
                    <Check className="h-3.5 w-3.5" /> Submitted
                  </span>
                )}
                {isInProgress && (
                  <span className="text-[12px] text-blue-400 font-medium">In progress</span>
                )}
                {isSent && (
                  <span className="text-[12px] text-amber-400 font-medium">Ready to complete</span>
                )}
              </div>

              {org.client_message && (
                <p className="text-[12px] italic" style={{ color: mutedText }}>{org.client_message}</p>
              )}

              {!isSubmitted && (
                <button
                  onClick={() => openOrganizer(org.id, false)}
                  className="self-start px-4 py-1.5 rounded-[6px] bg-[#3A6A94] text-[12px] font-medium hover:bg-[#4A7FA5] transition-colors"
                  style={{ color: '#EDEEF0' }}
                >
                  {isInProgress ? 'Continue' : 'Complete Now'}
                </button>
              )}
              {isSubmitted && (
                <button
                  onClick={() => openOrganizer(org.id, true)}
                  className="self-start px-4 py-1.5 rounded-[6px] text-[12px] transition-colors"
                  style={{ border: `1px solid ${mutedText}`, color: mutedText }}
                >
                  View Submission
                </button>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
