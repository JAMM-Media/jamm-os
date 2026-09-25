// path: frontend/src/app/(auth)/login/reset-password/page.tsx
'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Loader2, Eye, EyeOff } from 'lucide-react'

const inputClass =
  'w-full h-11 px-3 rounded-lg text-[15px] bg-surface-input dark:bg-dark-card border border-surface-border dark:border-dark-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]'

const btnPrimary =
  'w-full h-11 rounded-lg text-[15px] font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2 transition-opacity hover:opacity-90'

function Shell({ children }: { children: React.ReactNode }) {
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
        {children}
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

function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [matchError, setMatchError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [success, setSuccess] = useState(false)

  // No token in URL — invalid link state
  if (!token) {
    return (
      <Shell>
        <h1 className="text-[28px] font-medium text-brand dark:text-[#EDEEF0] text-center mb-1 leading-tight">
          Invalid link
        </h1>
        <p className="text-[14px] text-[#6B7280] text-center mb-7">
          This password reset link is missing a token and cannot be used.
        </p>
        <Link
          href="/login/forgot-password"
          className="text-[12px] text-brand-light dark:text-brand-light hover:underline block text-center"
        >
          Request a new reset link
        </Link>
      </Shell>
    )
  }

  // Success state
  if (success) {
    return (
      <Shell>
        <h1 className="text-[28px] font-medium text-brand dark:text-[#EDEEF0] text-center mb-1 leading-tight">
          Password updated
        </h1>
        <p className="text-[14px] text-[#6B7280] text-center mb-7">
          Your password has been changed. You can now sign in with your new password.
        </p>
        <Link
          href="/login"
          className="text-[12px] text-brand-light dark:text-brand-light hover:underline block text-center"
        >
          Go to sign in
        </Link>
      </Shell>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMatchError('')
    setSubmitError('')

    if (newPassword !== confirmPassword) {
      setMatchError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch('/api/backend/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setSubmitError(data.detail ?? 'Invalid or expired reset token.')
        return
      }
      setSuccess(true)
    } catch {
      setSubmitError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Shell>
      <h1 className="text-[28px] font-medium text-brand dark:text-[#EDEEF0] text-center mb-1 leading-tight">
        Set a new password
      </h1>
      <p className="text-[14px] text-[#6B7280] text-center mb-7">
        Choose a strong password for your account.
      </p>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {/* New password */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-medium text-[#6B7280]">New password</label>
          <div className="relative">
            <input
              type={showNew ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className={inputClass + ' pr-9'}
            />
            <button
              type="button"
              onClick={() => setShowNew(!showNew)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280]"
            >
              {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>

        {/* Confirm password */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[12px] font-medium text-[#6B7280]">Confirm new password</label>
          <div className="relative">
            <input
              type={showConfirm ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className={inputClass + ' pr-9'}
            />
            <button
              type="button"
              onClick={() => setShowConfirm(!showConfirm)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280]"
            >
              {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>

        {matchError && <p className="text-[12px] text-status-red-text">{matchError}</p>}

        {submitError && (
          <div className="flex flex-col gap-1.5">
            <p className="text-[12px] text-status-red-text">{submitError}</p>
            <Link
              href="/login/forgot-password"
              className="text-[12px] text-brand-light dark:text-brand-light hover:underline"
            >
              Request a new reset link
            </Link>
          </div>
        )}

        <button type="submit" disabled={loading} className={btnPrimary}>
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Updating...
            </>
          ) : (
            'Update password'
          )}
        </button>
      </form>
    </Shell>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#1F3148] flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-white" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  )
}
