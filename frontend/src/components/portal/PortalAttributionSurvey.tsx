// frontend/src/components/portal/PortalAttributionSurvey.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { X, Check, Loader2 } from 'lucide-react'
import {
  getAttributionSurvey,
  submitAttributionSurvey,
  type SurveyOption,
} from '@/lib/portal-api'

const JAMM_GOLD = '#B07D3A'
const CARD_BG = '#1A2535'
const OPTION_BG = 'rgba(255, 255, 255, 0.12)'
const OPTION_HOVER_BG = 'rgba(255, 255, 255, 0.18)'
const OPTION_SELECTED_BG = 'rgba(176, 125, 58, 0.33)'
const DO_NOT_REMEMBER_VALUE = 'do_not_remember'

interface Props {
  onClose: () => void
  onComplete: () => void
}

export function PortalAttributionSurvey({ onClose, onComplete }: Props) {
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [question, setQuestion] = useState('')
  const [options, setOptions] = useState<SurveyOption[]>([])
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [hoveredOption, setHoveredOption] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const loadSurvey = useCallback(() => {
    setLoadingOptions(true)
    setFetchError(null)
    getAttributionSurvey()
      .then(data => {
        setQuestion(data.question)
        setOptions(data.options)
      })
      .catch(() => setFetchError('Could not load the question. Please try again.'))
      .finally(() => setLoadingOptions(false))
  }, [])

  useEffect(() => {
    loadSurvey()
  }, [loadSurvey])

  // Auto-close after brief success display
  useEffect(() => {
    if (!done) return
    const t = setTimeout(onComplete, 1500)
    return () => clearTimeout(t)
  }, [done, onComplete])

  const handleSubmit = async () => {
    if (!selected || submitting) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      await submitAttributionSurvey(selected)
      setDone(true)
    } catch {
      setSubmitError('Something went wrong. Please try again.')
      setSubmitting(false)
    }
  }

  const mainOptions = options.filter(o => o.value !== DO_NOT_REMEMBER_VALUE)
  const doNotRemember = options.find(o => o.value === DO_NOT_REMEMBER_VALUE)

  const canSubmit = !!selected && !submitting

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.72)' }}
    >
      <div
        className="w-full max-w-[400px] max-h-[85vh] rounded-2xl flex flex-col overflow-hidden"
        style={{
          backgroundColor: CARD_BG,
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b flex-shrink-0"
          style={{ borderColor: 'rgba(255,255,255,0.08)' }}
        >
          <span className="text-[13px] font-semibold text-white">Quick question</span>
          <button
            type="button"
            onClick={onClose}
            className="flex items-center justify-center w-6 h-6 rounded transition-opacity hover:opacity-70"
            style={{ color: '#9CA3AF' }}
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="survey-scroll overflow-y-auto max-h-[320px]">
          {/* Loading */}
          {loadingOptions && (
            <div className="flex items-center justify-center py-14">
              <Loader2 size={20} className="animate-spin" style={{ color: '#6B7280' }} />
            </div>
          )}

          {/* Fetch error */}
          {!loadingOptions && fetchError && (
            <div className="px-5 py-10 flex flex-col items-center gap-3">
              <p className="text-[13px] text-center" style={{ color: '#9CA3AF' }}>
                {fetchError}
              </p>
              <button
                type="button"
                onClick={loadSurvey}
                className="text-[12px] transition-opacity hover:opacity-70"
                style={{ color: '#60A5FA' }}
              >
                Try again
              </button>
            </div>
          )}

          {/* Success */}
          {done && (
            <div className="flex flex-col items-center justify-center py-14 px-5 gap-4">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor: 'rgba(176, 125, 58, 0.28)',
                  border: '2px solid rgba(176, 125, 58, 0.45)',
                }}
              >
                <Check size={30} style={{ color: JAMM_GOLD }} />
              </div>
              <p className="text-[17px] font-semibold text-white">Thank you!</p>
              <p className="text-[13px] text-center" style={{ color: '#9CA3AF' }}>
                Your answer has been saved.
              </p>
            </div>
          )}

          {/* Question and options */}
          {!loadingOptions && !fetchError && !done && (
            <div className="px-5 py-5 flex flex-col gap-4">
              <p className="text-[14px] font-medium text-white leading-snug">{question}</p>

              {/* Main options */}
              <div className="flex flex-col gap-2">
                {mainOptions.map(opt => {
                  const isSelected = selected === opt.value
                  const isHovered = hoveredOption === opt.value
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setSelected(opt.value)}
                      onMouseEnter={() => setHoveredOption(opt.value)}
                      onMouseLeave={() => setHoveredOption(null)}
                      className="w-full text-left px-4 py-3 rounded-xl text-[13px] transition-colors"
                      style={{
                        backgroundColor: isSelected
                          ? OPTION_SELECTED_BG
                          : isHovered
                          ? OPTION_HOVER_BG
                          : OPTION_BG,
                        color: isSelected ? '#EDEEF0' : '#D1D5DB',
                        border: isSelected
                          ? `2px solid ${JAMM_GOLD}`
                          : '1px solid rgba(255,255,255,0.10)',
                      }}
                    >
                      {opt.label}
                    </button>
                  )
                })}
              </div>

              {/* "Do not remember" -- plain text link, visually distinct from real options */}
              {doNotRemember && (
                <button
                  type="button"
                  onClick={() => setSelected(doNotRemember.value)}
                  className="w-full text-center py-1 text-[11px] transition-opacity hover:opacity-70"
                  style={{
                    color: selected === doNotRemember.value ? '#D1D5DB' : '#6B7280',
                    textDecoration:
                      selected === doNotRemember.value ? 'underline' : 'none',
                  }}
                >
                  {doNotRemember.label}
                </button>
              )}

              {/* Submit error */}
              {submitError && (
                <p className="text-[11px] text-center" style={{ color: '#F87171' }}>
                  {submitError}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer -- submit button, hidden during loading / error / success */}
        {!loadingOptions && !fetchError && !done && (
          <div
            className="px-5 py-4 border-t flex-shrink-0"
            style={{ borderColor: 'rgba(255,255,255,0.08)' }}
          >
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="w-full py-3 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 transition-colors"
              style={{
                backgroundColor: canSubmit ? JAMM_GOLD : 'rgba(255,255,255,0.08)',
                color: canSubmit ? '#ffffff' : '#6B7280',
                cursor: canSubmit ? 'pointer' : 'default',
              }}
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitting ? 'Saving...' : 'Submit'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
