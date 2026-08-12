// path: frontend/src/app/intake/[slug]/page.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'

interface FirmConfig {
  firm_name: string
  slug: string
  turnstile_site_key: string
}

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: string | HTMLElement,
        params: {
          sitekey: string
          callback: (token: string) => void
          'expired-callback': () => void
        }
      ) => string
      reset: (widgetId: string) => void
    }
  }
}

const inputClass =
  'w-full h-10 px-3 rounded-[6px] text-[13px] bg-white border border-[#D1D5DB] text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const labelClass = 'block text-[12px] font-medium text-[#374151] mb-1'

export default function IntakePage() {
  const { slug } = useParams<{ slug: string }>()
  const searchParams = useSearchParams()

  const [config, setConfig] = useState<FirmConfig | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadingConfig, setLoadingConfig] = useState(true)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [serviceInterest, setServiceInterest] = useState('')
  const [howDidYouHear, setHowDidYouHear] = useState('')

  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const turnstileRef = useRef<HTMLDivElement>(null)
  const widgetIdRef = useRef<string | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Silently capture UTM params from URL -- never surfaced to the visitor.
  const utmCampaign = searchParams.get('utm_campaign')
  const utmSource = searchParams.get('utm_source')
  const utmMedium = searchParams.get('utm_medium')
  const utmContent = searchParams.get('utm_content')
  const utmTerm = searchParams.get('utm_term')

  // Load firm config on mount.
  useEffect(() => {
    fetch(`/api/backend/intake/${slug}/config`)
      .then(async (res) => {
        if (res.status === 404) {
          setNotFound(true)
          return
        }
        const data = await res.json()
        setConfig(data)
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoadingConfig(false))
  }, [slug])

  // Load Turnstile script and render widget once config is available.
  useEffect(() => {
    if (!config) return
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
    script.async = true
    script.defer = true
    script.onload = () => {
      if (turnstileRef.current && window.turnstile) {
        widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
          sitekey: config.turnstile_site_key,
          callback: (token) => setTurnstileToken(token),
          'expired-callback': () => setTurnstileToken(null),
        })
      }
    }
    document.head.appendChild(script)
    return () => {
      document.head.removeChild(script)
    }
  }, [config])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!turnstileToken) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch(`/api/backend/intake/${slug}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          email,
          phone: phone || undefined,
          service_interest: serviceInterest || undefined,
          how_did_you_hear: howDidYouHear || undefined,
          utm_campaign: utmCampaign || undefined,
          utm_source: utmSource || undefined,
          utm_medium: utmMedium || undefined,
          utm_content: utmContent || undefined,
          utm_term: utmTerm || undefined,
          turnstile_token: turnstileToken,
        }),
      })
      if (res.ok) {
        setSubmitted(true)
      } else if (res.status === 429) {
        setError(
          "We've received several submissions from this email recently. Please wait a few minutes and try again."
        )
        if (widgetIdRef.current && window.turnstile) {
          window.turnstile.reset(widgetIdRef.current)
          setTurnstileToken(null)
        }
      } else if (res.status === 400) {
        setError('Security check failed. Please refresh and try again.')
        if (widgetIdRef.current && window.turnstile) {
          window.turnstile.reset(widgetIdRef.current)
          setTurnstileToken(null)
        }
      } else {
        setError('Something went wrong. Please try again in a moment.')
      }
    } catch {
      setError('Something went wrong. Please check your connection and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loadingConfig) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F9FAFB]">
        <Loader2 className="w-6 h-6 animate-spin text-[#9CA3AF]" />
      </div>
    )
  }

  if (notFound || !config) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F9FAFB]">
        <div className="text-center max-w-sm px-6">
          <p className="text-[15px] font-medium text-[#111827] mb-2">Page not found</p>
          <p className="text-[13px] text-[#6B7280]">
            This intake form link doesn&apos;t exist. Please check your link or contact the firm directly.
          </p>
        </div>
      </div>
    )
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F9FAFB]">
        <div className="w-full max-w-md px-6 py-10 text-center">
          <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-6 h-6 text-green-600"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-[18px] font-semibold text-[#111827] mb-2">
            Thanks, we&apos;ll be in touch.
          </p>
          <p className="text-[13px] text-[#6B7280]">
            {config.firm_name} received your information and will reach out shortly.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md">
        {/* Firm header */}
        <div className="mb-8 text-center">
          <p className="text-[22px] font-semibold text-[#111827]">{config.firm_name}</p>
          <p className="text-[13px] text-[#6B7280] mt-1">
            Tell us about yourself and how we can help.
          </p>
        </div>

        <div className="bg-white rounded-[10px] border border-[#E5E7EB] shadow-sm p-8">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {/* Name */}
            <div>
              <label className={labelClass}>
                Full name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Smith"
                required
                className={inputClass}
              />
            </div>

            {/* Email */}
            <div>
              <label className={labelClass}>
                Email <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@example.com"
                required
                className={inputClass}
              />
            </div>

            {/* Phone */}
            <div>
              <label className={labelClass}>Phone (optional)</label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="(555) 000-0000"
                className={inputClass}
              />
            </div>

            {/* Service interest */}
            <div>
              <label className={labelClass}>What can we help you with? (optional)</label>
              <textarea
                value={serviceInterest}
                onChange={(e) => setServiceInterest(e.target.value)}
                placeholder="e.g. Individual tax return, business bookkeeping, IRS letter..."
                rows={3}
                className="w-full px-3 py-2.5 rounded-[6px] text-[13px] bg-white border border-[#D1D5DB] text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors resize-none"
              />
            </div>

            {/* How did you hear */}
            <div>
              <label className={labelClass}>How did you hear about us? (optional)</label>
              <input
                type="text"
                value={howDidYouHear}
                onChange={(e) => setHowDidYouHear(e.target.value)}
                placeholder="Friend referral, Google search, social media..."
                className={inputClass}
              />
            </div>

            {/* Turnstile widget */}
            <div ref={turnstileRef} />

            {/* Error */}
            {error && (
              <p className="text-[12px] text-red-600 bg-red-50 border border-red-200 rounded-[6px] px-3 py-2">
                {error}
              </p>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting || !turnstileToken}
              className="w-full h-10 rounded-[6px] text-[13px] font-medium text-white flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
              style={{ backgroundColor: '#1F3148' }}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Sending...
                </>
              ) : (
                'Get in touch'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
