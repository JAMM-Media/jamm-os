// path: frontend/src/app/portal/login/page.tsx
'use client'

import { useState } from 'react'
import { Eye, EyeOff, Link2, Loader2, Lock, Mail, Shield } from 'lucide-react'

type Tab = 'password' | 'magic'

// JAMM gold (#B07D3A) used for the active-tab underline only
const GOLD = '#B07D3A'

// Inputs: rounded-md for financial product crispness
const inputBase =
  'w-full h-10 rounded-md text-[13px] bg-white border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-50 focus:border-[#1F3148] transition-colors'

export default function PortalLoginPage() {
  const [activeTab, setActiveTab] = useState<Tab>('password')

  // Shared email (used in both tabs)
  const [email, setEmail] = useState('')

  // Password tab state
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState('')
  const [noPasswordSet, setNoPasswordSet] = useState(false)

  // Magic link tab state
  const [magicEmail, setMagicEmail] = useState('')
  const [magicLoading, setMagicLoading] = useState(false)
  const [magicSent, setMagicSent] = useState(false)
  const [magicDisabled, setMagicDisabled] = useState(false)

  function switchToMagicLink() {
    if (email) setMagicEmail(email)
    setActiveTab('magic')
  }

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
      window.location.replace('/portal')
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
    const target = magicEmail || email
    try {
      await fetch('/api/backend/portal/request-magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: target }),
      })
    } catch {
      // never surface errors -- always show success to prevent user enumeration
    } finally {
      setMagicLoading(false)
      setMagicSent(true)
    }
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-12"
      style={{ backgroundColor: '#F7F8FA' }}
    >
      <div className="w-full max-w-[400px] flex flex-col items-center">
        {/* Heading */}
        <h1 className="text-[24px] font-bold mb-1" style={{ color: '#1F3148' }}>
          Welcome back
        </h1>
        <p className="text-[13px] mb-6 text-center" style={{ color: '#6B7280' }}>
          Sign in to access your client portal.
        </p>

        {/* Card -- rounded-xl */}
        <div className="w-full bg-white rounded-xl border border-gray-100 p-7 shadow-sm">
          {/* Tab toggle -- active underline uses gold accent */}
          <div className="flex border-b border-gray-100 mb-6">
            <button
              type="button"
              onClick={() => setActiveTab('password')}
              className="flex-1 pb-3 text-[13px] font-medium transition-colors"
              style={{
                color: activeTab === 'password' ? '#1F3148' : '#9CA3AF',
                borderBottom: activeTab === 'password'
                  ? `2px solid ${GOLD}`
                  : '2px solid transparent',
                marginBottom: '-1px',
              }}
            >
              Email &amp; password
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('magic')}
              className="flex-1 pb-3 text-[13px] font-medium transition-colors"
              style={{
                color: activeTab === 'magic' ? '#1F3148' : '#9CA3AF',
                borderBottom: activeTab === 'magic'
                  ? `2px solid ${GOLD}`
                  : '2px solid transparent',
                marginBottom: '-1px',
              }}
            >
              Magic link
            </button>
          </div>

          {/* Email & password tab */}
          {activeTab === 'password' && (
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium" style={{ color: '#374151' }}>
                  Email address
                </label>
                <div className="relative flex items-center">
                  <Mail
                    size={14}
                    className="absolute left-3 pointer-events-none"
                    style={{ color: '#9CA3AF' }}
                  />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    required
                    autoComplete="email"
                    className={`${inputBase} pl-9`}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium" style={{ color: '#374151' }}>
                  Password
                </label>
                <div className="relative flex items-center">
                  <Lock
                    size={14}
                    className="absolute left-3 pointer-events-none"
                    style={{ color: '#9CA3AF' }}
                  />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    autoComplete="current-password"
                    className={`${inputBase} pl-9 pr-10`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 p-0.5 transition-opacity hover:opacity-70"
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword
                      ? <EyeOff size={14} style={{ color: '#9CA3AF' }} />
                      : <Eye size={14} style={{ color: '#9CA3AF' }} />}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={switchToMagicLink}
                  className="self-end text-[11px] transition-opacity hover:opacity-70"
                  style={{ color: '#6B7280' }}
                >
                  Forgot your password? Use a magic link instead.
                </button>
              </div>

              {loginError && !noPasswordSet && (
                <p className="text-[12px]" style={{ color: '#DC2626' }}>{loginError}</p>
              )}

              {noPasswordSet && (
                <p className="text-[12px]" style={{ color: '#D97706' }}>
                  No password set yet.{' '}
                  <button
                    type="button"
                    onClick={switchToMagicLink}
                    className="underline font-medium"
                    style={{ color: '#D97706' }}
                  >
                    Use a magic link instead.
                  </button>
                </p>
              )}

              <button
                type="submit"
                disabled={loginLoading}
                className="w-full h-10 rounded-md text-[13px] font-semibold text-white flex items-center justify-center gap-2 disabled:opacity-60 transition-opacity hover:opacity-90"
                style={{ backgroundColor: '#1F3148' }}
              >
                {loginLoading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />Signing in...</>
                ) : (
                  'Sign in'
                )}
              </button>

              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-gray-100" />
                <span className="text-[11px]" style={{ color: '#9CA3AF' }}>or</span>
                <div className="flex-1 h-px bg-gray-100" />
              </div>

              <button
                type="button"
                onClick={switchToMagicLink}
                className="w-full h-10 rounded-md text-[13px] font-medium border border-gray-200 flex items-center justify-center gap-2 transition-colors hover:bg-gray-50"
                style={{ color: '#6B7280' }}
              >
                <Link2 size={14} />
                Send me a magic link
              </button>
            </form>
          )}

          {/* Magic link tab */}
          {activeTab === 'magic' && (
            <div className="flex flex-col gap-4">
              {magicSent ? (
                <div className="text-center py-6">
                  <p className="text-[14px] font-semibold mb-2" style={{ color: '#059669' }}>
                    Link sent!
                  </p>
                  <p className="text-[12px]" style={{ color: '#6B7280' }}>
                    If a portal account exists for that email, a magic link is on its way.
                    Check your inbox.
                  </p>
                  <button
                    type="button"
                    onClick={() => { setMagicSent(false); setActiveTab('password') }}
                    className="mt-4 text-[12px] transition-opacity hover:opacity-70"
                    style={{ color: '#1F3148' }}
                  >
                    Back to sign in
                  </button>
                </div>
              ) : (
                <form onSubmit={handleMagicLink} className="flex flex-col gap-4">
                  <p className="text-[12px]" style={{ color: '#6B7280' }}>
                    Enter your email and we will send you a one-time sign-in link. No password needed.
                  </p>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[12px] font-medium" style={{ color: '#374151' }}>
                      Email address
                    </label>
                    <div className="relative flex items-center">
                      <Mail
                        size={14}
                        className="absolute left-3 pointer-events-none"
                        style={{ color: '#9CA3AF' }}
                      />
                      <input
                        type="email"
                        value={magicEmail || email}
                        onChange={(e) => setMagicEmail(e.target.value)}
                        placeholder="Enter your email"
                        required
                        autoComplete="email"
                        className={`${inputBase} pl-9`}
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={magicLoading || magicDisabled}
                    className="w-full h-10 rounded-md text-[13px] font-semibold text-white flex items-center justify-center gap-2 disabled:opacity-60 transition-opacity hover:opacity-90"
                    style={{ backgroundColor: '#1F3148' }}
                  >
                    {magicLoading ? (
                      <><Loader2 className="w-4 h-4 animate-spin" />Sending...</>
                    ) : (
                      <><Link2 size={14} />Send me a magic link</>
                    )}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>

        {/* Security reassurance -- small inline line, not a bordered panel */}
        <div className="flex items-center gap-1.5 mt-4">
          <Shield size={12} style={{ color: '#9CA3AF' }} />
          <p className="text-[11px]" style={{ color: '#9CA3AF' }}>
            Your information is protected with industry-standard security.
          </p>
        </div>

        {/* Need help */}
        <p className="text-[12px] mt-3 text-center" style={{ color: '#9CA3AF' }}>
          Need help?{' '}
          <span style={{ color: '#6B7280' }}>Contact your accounting team.</span>
        </p>

        {/* Powered by footer */}
        <p className="text-[11px] mt-6" style={{ color: '#C4C9D1' }}>
          Powered by{' '}
          <span className="font-semibold" style={{ color: '#9CA3AF' }}>JAMM PX</span>
        </p>
      </div>
    </div>
  )
}
