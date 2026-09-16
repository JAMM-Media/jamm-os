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

  const [showMagicLink, setShowMagicLink] = useState(false)
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

  function handleShowMagicLink() {
    setShowMagicLink(true)
    setError('')
    setMagicSent(false)
    setMagicError('')
  }

  function handleHideMagicLink() {
    setShowMagicLink(false)
    setMagicSent(false)
    setMagicError('')
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
            <img src="/jamm-logo-mark-light.svg" alt="" className="w-auto flex-shrink-0" style={{ height: 52 }} />
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

        <h1 className="text-[28px] font-medium text-brand dark:text-[#EDEEF0] text-center mb-1 leading-tight">
          Sign in
        </h1>
        <p className="text-[14px] text-[#6B7280] text-center mb-7">
          Welcome back to JAMM PX.
        </p>

        {/* Two-factor step */}
        {step === 'code' && (
          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">
              Enter your authentication code
            </p>

            {!showBackupCode && (
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-[#6B7280]">Authenticator Code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  autoFocus
                  placeholder="6-digit code"
                  className={inputClass}
                />
                <p className="text-[11px] text-[#9CA3AF]">
                  Enter the 6-digit code from your authenticator app.
                </p>
              </div>
            )}

            {showBackupCode && (
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-[#6B7280]">Backup Code</label>
                <input
                  type="text"
                  value={backupCode}
                  onChange={(e) => setBackupCode(e.target.value)}
                  autoFocus
                  placeholder="Backup code"
                  className={inputClass}
                />
                <p className="text-[11px] text-[#9CA3AF]">
                  Enter one of your saved backup codes.
                </p>
              </div>
            )}

            {error && <p className="text-[12px] text-status-red-text">{error}</p>}

            <button type="submit" disabled={isLoading} className={btnPrimary}>
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                'Verify'
              )}
            </button>

            <div className="flex flex-col items-center gap-2 mt-1">
              <button
                type="button"
                onClick={handleToggleBackupCode}
                className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] underline"
              >
                {showBackupCode ? 'Use authenticator app instead' : "Can't use your authenticator? Enter a backup code"}
              </button>
              <button
                type="button"
                onClick={handleBack}
                className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] underline"
              >
                Back
              </button>
            </div>
          </form>
        )}

        {/* Magic link form */}
        {step === 'password' && showMagicLink && (
          <form onSubmit={handleMagicLink} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-medium text-[#6B7280]">Email address</label>
              <input
                type="email"
                value={effectiveMagicEmail}
                onChange={(e) => setMagicEmail(e.target.value)}
                placeholder="Enter your email address"
                autoFocus
                className={inputClass}
              />
            </div>

            <p className="text-[12px] text-[#9CA3AF]">
              We will email you a one-time link valid for 30 minutes.
            </p>

            {magicSent ? (
              <p className="text-[13px] text-status-green-text text-center py-1">
                Link sent. Check your email. It expires in 30 minutes.
              </p>
            ) : (
              <button type="submit" disabled={magicLoading} className={btnPrimary}>
                {magicLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  'Send link'
                )}
              </button>
            )}

            {magicError && <p className="text-[12px] text-status-red-text">{magicError}</p>}

            <button
              type="button"
              onClick={handleHideMagicLink}
              className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] underline text-center"
            >
              Back to password sign in
            </button>
          </form>
        )}

        {/* Password form */}
        {step === 'password' && !showMagicLink && (
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

            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-medium text-[#6B7280]">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className={inputClass + ' pr-9'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280]"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <div className="flex items-center justify-between mt-0.5">
                <Link
                  href="/login/forgot-password"
                  className="text-[12px] text-brand-light dark:text-brand-light hover:underline"
                >
                  Forgot password?
                </Link>
                <button
                  type="button"
                  onClick={handleShowMagicLink}
                  className="text-[12px] text-brand-light dark:text-brand-light hover:underline"
                >
                  Use a magic link instead
                </button>
              </div>
            </div>

            {error && <p className="text-[12px] text-status-red-text">{error}</p>}

            <button type="submit" disabled={isLoading} className={btnPrimary + ' mt-1'}>
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
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
