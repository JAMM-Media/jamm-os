// path: frontend/src/app/(auth)/login/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/hooks/useAuth'
import { Eye, EyeOff, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [showTotp, setShowTotp] = useState(false)
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
    setIsLoading(true)
    const result = await login(email, password, showTotp ? totpCode : undefined)
    setIsLoading(false)
    if (result.success) {
      router.push('/dashboard')
    } else {
      if (result.message?.toLowerCase().includes('magic link')) {
        setError('Your firm requires magic link login. Check your email for a login link.')
      } else {
        setError(result.message ?? 'Sign in failed. Please try again.')
      }
    }
  }

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault()
    setMagicError('')
    setMagicSent(false)
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
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden md:flex w-1/2 bg-brand flex-col items-center justify-center gap-3">
        <span className="text-white text-2xl font-medium">
          JAMM <span style={{ color: '#B07D3A' }}>PX</span>
        </span>
        <span className="text-brand-muted text-sm font-normal text-center px-8">
          Practice experience for accounting firms.
        </span>
      </div>

      {/* Right panel */}
      <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[380px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-8">
          <h1 className="text-base font-medium text-brand dark:text-[#EDEEF0] mb-6">
            Sign in to JAMM <span style={{ color: '#B07D3A' }}>PX</span>
          </h1>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Email */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-[#6B7280]">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@firm.com"
                required
                className="w-full h-9 px-3 rounded-md text-sm bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
              />
            </div>

            {/* Password */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-[#6B7280]">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full h-9 px-3 rounded-md text-sm bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
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

            {/* TOTP */}
            {showTotp && (
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
                  className="w-full h-9 px-3 rounded-md text-sm bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
                />
                <p className="text-[11px] text-[#6B7280] mt-1">
                  Enter the 6-digit code from your authenticator app.
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
              className="w-full h-9 mt-2 rounded-md text-xs font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2"
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

            {/* TOTP toggle */}
            <p className="text-[11px] text-[#6B7280] mt-3 text-center">
              Have a 2FA code?{' '}
              <button
                type="button"
                onClick={() => setShowTotp(!showTotp)}
                className="underline text-[#6B7280] hover:text-brand"
              >
                {showTotp ? 'Hide' : 'Enter it here'}
              </button>
            </p>
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

            <form onSubmit={handleMagicLink} className="flex flex-col gap-2 mt-1">
              <input
                type="email"
                value={effectiveMagicEmail}
                onChange={(e) => setMagicEmail(e.target.value)}
                placeholder="you@firm.com"
                required
                className="w-full h-9 px-3 rounded-md text-sm bg-surface-input dark:bg-dark-card border border-surface-border focus:border-brand-light focus:outline-none focus:ring-1 focus:ring-brand-light text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
              />

              {magicSent ? (
                <p className="text-[12px] text-[#10B981] text-center py-1">
                  Link sent — check your email. It expires in 15 minutes.
                </p>
              ) : (
                <button
                  type="submit"
                  disabled={magicLoading}
                  className="w-full h-9 rounded-md text-[12px] font-[500] text-[#1F3148] dark:text-[#EDEEF0] flex items-center justify-center gap-2 disabled:opacity-60 transition-colors hover:bg-[#E4E6EA] dark:hover:bg-[#333333]"
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
