// path: frontend/src/app/(auth)/login/reset-password/page.tsx
'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Loader2, Eye, EyeOff } from 'lucide-react'

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

  const leftPanel = (
    <div className="hidden md:flex w-1/2 bg-brand flex-col p-10">
      <div className="flex items-center gap-2.5">
        <img src="/jamm-logo-mark.svg" alt="" width={60} className="flex-shrink-0" />
        <span className="text-white text-3xl font-medium">
          JAMM <span style={{ color: '#B07D3A' }}>PX</span>
        </span>
      </div>
      <div className="flex flex-1 items-center">
        <div className="flex flex-col">
          <div className="h-[2px] mb-3" style={{ backgroundColor: '#B07D3A', width: '48px' }} />
          <h2 className="text-white text-7xl font-bold leading-tight">
            Your firm.<br /><span style={{ color: '#B07D3A' }}>Under control.</span>
          </h2>
        </div>
      </div>
    </div>
  )

  // No token in URL — invalid link state
  if (!token) {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Invalid link</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              This password reset link is missing a token and cannot be used.
            </p>
            <Link
              href="/login/forgot-password"
              className="text-[13px] text-brand dark:text-[#4A7FA5] underline hover:opacity-80"
            >
              Request a new reset link
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Success state
  if (success) {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Password updated</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              Your password has been changed. You can now sign in with your new password.
            </p>
            <Link
              href="/login"
              className="text-[13px] text-brand dark:text-[#4A7FA5] underline hover:opacity-80"
            >
              Go to sign in
            </Link>
          </div>
        </div>
      </div>
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
    <div className="min-h-screen flex">
      {leftPanel}
      <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10">
          <div className="mb-6">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Set a new password</h1>
            <p className="text-[14px] text-[#6B7280] mt-2">
              Choose a strong password for your account.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* New password */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-[#6B7280]">New password</label>
              <div className="relative">
                <input
                  type={showNew ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  className="w-full h-11 px-3 rounded-md text-base bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-2 top-1/2 -translate-y-1/2"
                >
                  {showNew ? (
                    <EyeOff className="text-[#6B7280]" style={{ width: 14, height: 14 }} />
                  ) : (
                    <Eye className="text-[#6B7280]" style={{ width: 14, height: 14 }} />
                  )}
                </button>
              </div>
            </div>

            {/* Confirm password */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-[#6B7280]">Confirm new password</label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full h-11 px-3 rounded-md text-base bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-2 top-1/2 -translate-y-1/2"
                >
                  {showConfirm ? (
                    <EyeOff className="text-[#6B7280]" style={{ width: 14, height: 14 }} />
                  ) : (
                    <Eye className="text-[#6B7280]" style={{ width: 14, height: 14 }} />
                  )}
                </button>
              </div>
            </div>

            {matchError && <p className="text-[11px] text-[#991B1B]">{matchError}</p>}

            {submitError && (
              <div className="flex flex-col gap-1">
                <p className="text-[11px] text-[#991B1B]">{submitError}</p>
                <Link
                  href="/login/forgot-password"
                  className="text-[11px] text-brand dark:text-[#4A7FA5] underline hover:opacity-80"
                >
                  Request a new reset link
                </Link>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 mt-2 rounded-md text-sm font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Updating...
                </>
              ) : (
                'Update password'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  )
}
