// path: frontend/src/app/(auth)/login/forgot-password/page.tsx
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await fetch('/api/backend/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      setSubmitted(true)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const inputClass =
    'w-full h-11 px-3 rounded-lg text-[15px] bg-surface-input dark:bg-dark-card border border-surface-border dark:border-dark-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]'

  const btnPrimary =
    'w-full h-11 rounded-lg text-[15px] font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2 transition-opacity hover:opacity-90'

  return (
    <div className="min-h-screen bg-[#1F3148] flex flex-col items-center justify-center px-4 py-12">

      {/* Logo block */}
      <div className="flex flex-col items-center mb-8">
        <div className="inline-flex flex-col items-stretch">
          <div className="flex items-center gap-3">
            <img src="/jamm-brain-logo.png" alt="" className="w-auto flex-shrink-0" style={{ height: 52 }} />
            <span
              className="text-white leading-none tracking-tight"
              style={{ fontSize: 72, fontWeight: 500, fontStyle: 'normal', fontFamily: 'var(--font-playfair)' }}
            >
              JAMM
            </span>
          </div>
          <span
            className="mt-2 uppercase font-medium text-[16px] tracking-[0.28em] text-center whitespace-nowrap"
            style={{ color: '#B07D3A' }}
          >
            Practice Experience
          </span>
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-[400px] bg-white rounded-lg px-10 py-10">

        {submitted ? (
          <>
            <h1 className="text-[28px] font-medium text-brand dark:text-[#EDEEF0] text-center mb-1 leading-tight">
              Check your inbox
            </h1>
            <p className="text-[14px] text-[#6B7280] text-center mb-7">
              If an account with that email exists, we sent a reset link. Check your inbox.
            </p>
            <Link
              href="/login"
              className="text-[12px] text-brand-light dark:text-brand-light hover:underline block text-center"
            >
              Back to sign in
            </Link>
          </>
        ) : (
          <>
            <h1 className="text-[28px] font-medium text-brand dark:text-[#EDEEF0] text-center mb-1 leading-tight">
              Forgot password
            </h1>
            <p className="text-[14px] text-[#6B7280] text-center mb-7">
              Enter your email and we will send a link to reset your password.
            </p>

            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-[#6B7280]">Email address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email address"
                  className={inputClass}
                />
              </div>

              {error && <p className="text-[12px] text-status-red-text">{error}</p>}

              <button type="submit" disabled={loading} className={btnPrimary}>
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  'Send reset link'
                )}
              </button>

              <Link
                href="/login"
                className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] underline text-center"
              >
                Back to sign in
              </Link>
            </form>
          </>
        )}

      </div>

      {/* Footer below card */}
      <div className="mt-8 flex flex-col items-center gap-3 w-full max-w-[400px]">
        <p className="text-[12px] text-[#7DA3C4] text-center">
          Need help signing in?{' '}
          <span className="text-[#7DA3C4]">Contact support</span>
        </p>
        <div className="w-full h-px bg-[#2D4463]" />
        <p className="text-[11px] text-[#7DA3C4] text-center">
          &copy; 2026 JAMM PX. All rights reserved.
        </p>
      </div>

    </div>
  )
}
