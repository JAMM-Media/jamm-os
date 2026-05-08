// path: frontend/src/app/portal/auth/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'

export const dynamic = 'force-dynamic'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] text-[13px] bg-[#2D2D2D] border text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const borderNormal = 'border-[#484848]'

export default function PortalAuthPage() {
  const router = useRouter()

  const [exchanging, setExchanging] = useState(true)
  const [exchangeError, setExchangeError] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState('')
  const [noPasswordSet, setNoPasswordSet] = useState(false)

  const [magicEmail, setMagicEmail] = useState('')
  const [magicLoading, setMagicLoading] = useState(false)
  const [magicSent, setMagicSent] = useState(false)
  const [magicDisabled, setMagicDisabled] = useState(false)

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token')
    if (!token) {
      setExchanging(false)
      return
    }
    fetch(`/api/backend/portal/auth?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (!res.ok) {
          setExchangeError('This link has expired. Please request a new one.')
          setExchanging(false)
          return
        }
        const data = await res.json()
        localStorage.setItem('portal_access_token', data.access_token)
        router.replace('/portal')
      })
      .catch(() => {
        setExchangeError('This link has expired. Please request a new one.')
        setExchanging(false)
      })
  }, [router])

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoginError('')
    setNoPasswordSet(false)
    setLoginLoading(true)
    try {
      const res = await fetch('/api/backend/portal/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail: string = data.detail ?? ''
        if (detail.toLowerCase().includes('no password')) {
          setNoPasswordSet(true)
        } else {
          setLoginError(detail || 'Sign in failed. Please try again.')
        }
        return
      }
      localStorage.setItem('portal_access_token', data.access_token)
      router.replace('/portal')
    } catch {
      setLoginError('Sign in failed. Please try again.')
    } finally {
      setLoginLoading(false)
    }
  }

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault()
    setMagicLoading(true)
    setMagicDisabled(true)
    setTimeout(() => setMagicDisabled(false), 60_000)
    try {
      const target = magicEmail || email
      await fetch('/api/backend/portal/request-magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: target }),
      })
    } catch {
      // never surface errors — always show success
    } finally {
      setMagicLoading(false)
      setMagicSent(true)
    }
  }

  if (exchanging) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center gap-3"
        style={{ backgroundColor: '#2D2D2D' }}
      >
        <Loader2 className="h-6 w-6 animate-spin text-[#4A7FA5]" />
        <p className="text-[13px] text-[#6B7280]">Signing you in...</p>
      </div>
    )
  }

  const effectiveMagicEmail = magicEmail || email

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: '#2D2D2D' }}
    >
      <div
        className="w-[400px] flex flex-col gap-0 rounded-[10px] p-8"
        style={{ backgroundColor: '#383838', border: '0.5px solid #484848' }}
      >
        <div className="flex items-center gap-2 mb-5">
          <span className="text-[12px] font-[500] text-white">Your Firm</span>
          <span className="text-[10px]" style={{ color: '#7DA3C4' }}>
            Client Portal
          </span>
        </div>

        {exchangeError && (
          <div
            className="mb-4 px-3 py-2 rounded-[6px] text-[12px]"
            style={{ backgroundColor: '#7F1D1D', color: '#FCA5A5' }}
          >
            {exchangeError}
          </div>
        )}

        <p className="text-[16px] font-[500] mb-1" style={{ color: '#EDEEF0' }}>
          Sign in
        </p>
        <p className="text-[12px] mb-6" style={{ color: '#9CA3AF' }}>
          Access your documents, invoices, and to-do items.
        </p>

        <form onSubmit={handleLogin} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-[500]" style={{ color: '#EDEEF0' }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className={`${inputClass} ${borderNormal}`}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-[500]" style={{ color: '#EDEEF0' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={`${inputClass} ${borderNormal}`}
            />
          </div>

          <button
            type="submit"
            disabled={loginLoading}
            className="w-full h-9 rounded-[6px] text-[12px] font-[500] text-white flex items-center justify-center gap-2 disabled:opacity-60"
            style={{ backgroundColor: '#3A6A94' }}
          >
            {loginLoading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign in'
            )}
          </button>

          {noPasswordSet && (
            <p className="text-[11px]" style={{ color: '#E24B4A' }}>
              No password set yet. Use a magic link below to log in, then set a password in your
              account settings.
            </p>
          )}
          {loginError && !noPasswordSet && (
            <p className="text-[11px]" style={{ color: '#E24B4A' }}>
              {loginError}
            </p>
          )}
        </form>

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px" style={{ backgroundColor: '#484848' }} />
          <span className="text-[11px]" style={{ color: '#9CA3AF' }}>
            or
          </span>
          <div className="flex-1 h-px" style={{ backgroundColor: '#484848' }} />
        </div>

        <p className="text-[13px] font-[500] mb-1" style={{ color: '#EDEEF0' }}>
          Get a magic link
        </p>
        <p className="text-[11px] mb-3" style={{ color: '#9CA3AF' }}>
          We&apos;ll email you a one-time link. No password needed.
        </p>

        {magicSent ? (
          <p className="text-[12px] text-center py-2" style={{ color: '#10B981' }}>
            If a portal account exists for that email, a link has been sent. Check your inbox.
          </p>
        ) : (
          <form onSubmit={handleMagicLink} className="flex flex-col gap-3">
            <input
              type="email"
              value={effectiveMagicEmail}
              onChange={(e) => setMagicEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className={`${inputClass} ${borderNormal}`}
            />
            <button
              type="submit"
              disabled={magicLoading || magicDisabled}
              className="w-full h-9 rounded-[6px] text-[12px] font-[500] flex items-center justify-center gap-2 disabled:opacity-60 transition-colors"
              style={{
                backgroundColor: 'transparent',
                border: '0.5px solid #3A6A94',
                color: '#4A7FA5',
              }}
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
          </form>
        )}
      </div>
    </div>
  )
}
