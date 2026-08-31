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

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden md:flex w-1/2 bg-brand flex-col p-10">
        <div className="flex items-center gap-2.5">
          <img src="/jamm-logo-mark-light.svg" alt="" className="flex-shrink-0 h-8 w-auto" />
          <span className="text-white text-3xl font-medium">
            JAMM <span style={{ color: '#B07D3A' }}>PX</span>
          </span>
        </div>
        <div className="flex flex-1 items-center">
          <div className="flex flex-col">
            <div className="h-[2px] mb-3" style={{ backgroundColor: '#B07D3A', width: '48px' }} />
            <h2 className="text-white text-7xl font-bold leading-tight">
              Trusted guidance.<br /><span style={{ color: '#B07D3A' }}>Real partnership.</span>
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.65)' }}>
              We're here to help you succeed every step of the way.
            </p>
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10">
          {submitted ? (
            <div className="flex flex-col gap-4">
              <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Check your inbox</h1>
              <p className="text-[14px] text-[#6B7280] leading-relaxed">
                {"If an account with that email exists, we've sent a password reset link. Check your inbox."}
              </p>
              <Link
                href="/login"
                className="text-[13px] text-brand dark:text-[#4A7FA5] underline hover:opacity-80 mt-2"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Reset your password</h1>
                <p className="text-[14px] text-[#6B7280] mt-2">
                  {"Enter your email and we'll send you a link to reset your password."}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-medium text-[#6B7280]">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@firm.com"
                    required
                    className="w-full h-11 px-3 rounded-md text-base bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                  />
                </div>

                {error && <p className="text-[11px] text-[#991B1B]">{error}</p>}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full h-11 mt-2 rounded-md text-sm font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    'Send reset link'
                  )}
                </button>

                <Link
                  href="/login"
                  className="text-[12px] text-[#6B7280] hover:text-brand text-center mt-1"
                >
                  Back to sign in
                </Link>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
