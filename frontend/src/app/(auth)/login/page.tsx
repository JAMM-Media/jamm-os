// path: frontend/src/app/(auth)/login/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/hooks/useAuth'
import { Eye, EyeOff, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [backupCode, setBackupCode] = useState('')
  const [showBackupCode, setShowBackupCode] = useState(false)
  const [step, setStep] = useState<'password' | 'code'>('password')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const [magicEmail, setMagicEmail] = useState('')
  const [magicLoading, setMagicLoading] = useState(false)
  const [magicSent, setMagicSent] = useState(false)
  const [magicError, setMagicError] = useState('')

  const { login, isAuthenticated, user } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isAuthenticated) {
      if (user?.role === 'staff') {
        router.push('/tasks')
      } else {
        router.push('/dashboard')
      }
    }
  }, [isAuthenticated, user, router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (step === 'password') {
      if (!email.trim()) { setError('Please enter your email.'); return }
      if (!password.trim()) { setError('Please enter your password.'); return }
    } else {
      if (!showBackupCode && !totpCode.trim()) { setError('Please enter your authenticator code.'); return }
      if (showBackupCode && !backupCode.trim()) { setError('Please enter a backup code.'); return }
    }
    setIsLoading(true)

    const result = step === 'code'
      ? await login(
          email,
          password,
          !showBackupCode ? (totpCode || undefined) : undefined,
          showBackupCode ? (backupCode || undefined) : undefined,
        )
      : await login(email, password)

    setIsLoading(false)

    if (result.requires_2fa) {
      setStep('code')
    } else if (result.success) {
      router.push('/dashboard')
    } else {
      if (result.message?.toLowerCase().includes('magic link')) {
        setError('Your firm requires magic link login. Check your email for a login link.')
      } else {
        setError(result.message ?? 'Sign in failed. Please try again.')
      }
    }
  }

  function handleBack() {
    setStep('password')
    setError('')
    setTotpCode('')
    setBackupCode('')
    setShowBackupCode(false)
  }

  function handleToggleBackupCode() {
    setShowBackupCode((v) => !v)
    setTotpCode('')
    setBackupCode('')
  }

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault()
    setMagicError('')
    setMagicSent(false)
    if (!(magicEmail || email).trim()) { setMagicError('Please enter your email.'); return }
    setMagicLoading(true)
    try {
      const target = magicEmail || email
      const res = await fetch('/api/backend/auth/request-magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: target }),
      })
      if (res.status === 429) {
        setMagicError('Too many requests. Please wait a few minutes.')
        return
      }
      setMagicSent(true)
    } catch {
      setMagicError('Something went wrong. Please try again.')
    } finally {
      setMagicLoading(false)
    }
  }

  const effectiveMagicEmail = magicEmail || email

  return (
    <div className="min-h-screen bg-surface-page dark:bg-dark-page">
      {/* Page header -- logo + wordmark, top-left */}
      <div className="px-16 pt-10">
        <div className="flex items-center gap-2.5">
          <img src="/jamm-logo-mark.svg" alt="" width={60} className="flex-shrink-0" />
          <span className="text-brand dark:text-[#EDEEF0] text-2xl font-medium">
            JAMM <span style={{ color: '#B07D3A' }}>PX</span>
          </span>
        </div>
      </div>

      {/* Centered content column */}
      <div className="flex flex-col items-center px-4 pt-14 pb-16">
        <div className="w-full max-w-[460px]">
          {/* Headline block */}
          <div className="mb-8">
            <h1 className="text-4xl font-extrabold leading-tight text-center dark:text-[#EDEEF0]" style={{ color: '#16233A' }}>Sign in to JAMM <span style={{ color: '#B07D3A' }}>PX</span></h1>
          </div>

          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            {step === 'password' ? (
              <>
                {/* Email */}
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-medium text-[#6B7280]">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    className="w-full h-12 px-3 rounded-xl text-base bg-surface-input dark:bg-dark-card border border-surface-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                  />
                </div>

                {/* Password */}
                <div className="flex flex-col gap-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-medium text-[#6B7280]">Password</label>
                    <Link href="/login/forgot-password" className="text-[11px] text-brand dark:text-[#4A7FA5] hover:underline">Forgot password?</Link>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      className="w-full h-12 px-3 rounded-xl text-base bg-surface-input dark:bg-dark-card border border-surface-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2"
                    >
                      {showPassword ? (
                        <EyeOff className="text-[#6B7280]" style={{ width: 14, height: 14 }} />
                      ) : (
                        <Eye className="text-[#6B7280]" style={{ width: 14, height: 14 }} />
                      )}
                    </button>
                  </div>
                </div>

                {/* Error */}
                {error && (
                  <p className="text-[11px] text-[#991B1B] mt-1">{error}</p>
                )}

                {/* Submit */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full h-12 mt-2 rounded-xl text-sm font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Signing in...
                    </>
                  ) : (
                    'Sign in'
                  )}
                </button>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-brand dark:text-[#EDEEF0]">
                  Enter your authentication code
                </p>

                {/* Authenticator input */}
                {!showBackupCode && (
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium text-[#6B7280]">
                      Authenticator Code
                    </label>
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      value={totpCode}
                      onChange={(e) => setTotpCode(e.target.value)}
                      autoFocus
                      className="w-full h-12 px-3 rounded-xl text-base bg-surface-input dark:bg-dark-card border border-surface-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                    />
                    <p className="text-[11px] text-[#6B7280] mt-1">
                      Enter the 6-digit code from your authenticator app.
                    </p>
                  </div>
                )}

                {/* Backup code input */}
                {showBackupCode && (
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium text-[#6B7280]">
                      Backup Code
                    </label>
                    <input
                      type="text"
                      value={backupCode}
                      onChange={(e) => setBackupCode(e.target.value)}
                      autoFocus
                      className="w-full h-12 px-3 rounded-xl text-base bg-surface-input dark:bg-dark-card border border-surface-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                    />
                    <p className="text-[11px] text-[#6B7280] mt-1">
                      Enter one of your saved backup codes.
                    </p>
                  </div>
                )}

                {/* Error */}
                {error && (
                  <p className="text-[11px] text-[#991B1B] mt-1">{error}</p>
                )}

                {/* Submit */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full h-12 mt-2 rounded-xl text-sm font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    'Verify'
                  )}
                </button>

                {/* Toggle backup code */}
                <p className="text-[11px] text-[#6B7280] mt-1 text-center">
                  <button
                    type="button"
                    onClick={handleToggleBackupCode}
                    className="underline text-[#6B7280] hover:text-brand"
                  >
                    {showBackupCode
                      ? 'Use authenticator app instead'
                      : "Can't use your authenticator? Enter a backup code"}
                  </button>
                </p>

                {/* Back */}
                <p className="text-[11px] text-[#6B7280] text-center">
                  <button
                    type="button"
                    onClick={handleBack}
                    className="underline text-[#6B7280] hover:text-brand"
                  >
                    Back
                  </button>
                </p>
              </>
            )}
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-surface-border dark:bg-dark-border" />
            <span className="text-[11px] text-[#9CA3AF]">or</span>
            <div className="flex-1 h-px bg-surface-border dark:bg-dark-border" />
          </div>

          {/* Magic link section */}
          <div className="flex flex-col gap-2">
            <p className="text-[13px] font-[500] text-[#1F3148] dark:text-[#EDEEF0]">
              Sign in with a magic link
            </p>
            <p className="text-[11px] text-[#6B7280]">
              We&apos;ll email you a one-time link valid for 15 minutes.
            </p>

            <form onSubmit={handleMagicLink} noValidate className="flex flex-col gap-2 mt-1">
              <input
                type="email"
                value={effectiveMagicEmail}
                onChange={(e) => setMagicEmail(e.target.value)}
                placeholder="Enter your email"
                className="w-full h-12 px-3 rounded-xl text-base bg-surface-input dark:bg-dark-card border border-surface-border hover:border-brand-light focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-0 text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
              />

              {magicSent ? (
                <p className="text-[12px] text-[#10B981] text-center py-1">
                  Link sent — check your email. It expires in 30 minutes.
                </p>
              ) : (
                <button
                  type="submit"
                  disabled={magicLoading}
                  className="w-full h-12 rounded-xl text-sm font-[500] text-[#1F3148] dark:text-[#EDEEF0] flex items-center justify-center gap-2 disabled:opacity-60 transition-colors hover:bg-[#E4E6EA] dark:hover:bg-[#333333]"
                  style={{ border: '0.5px solid #1F3148' }}
                >
                  {magicLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    'Send link'
                  )}
                </button>
              )}

              {magicError && (
                <p className="text-[11px] text-[#991B1B]">{magicError}</p>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
