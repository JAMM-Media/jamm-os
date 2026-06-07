// path: frontend/src/app/portal/login/page.tsx
'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] text-[13px] bg-[#2D2D2D] border text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const borderNormal = 'border-[#484848]'

export default function PortalLoginPage() {
  const [magicEmail, setMagicEmail] = useState('')
  const [magicLoading, setMagicLoading] = useState(false)
  const [magicSent, setMagicSent] = useState(false)
  const [magicDisabled, setMagicDisabled] = useState(false)

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault()
    setMagicLoading(true)
    setMagicDisabled(true)
    setTimeout(() => setMagicDisabled(false), 60_000)
    try {
      await fetch('/api/backend/portal/request-magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: magicEmail }),
      })
    } catch {
      // never surface errors — always show success
    } finally {
      setMagicLoading(false)
      setMagicSent(true)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: '#2D2D2D' }}
    >
      <div
        className="w-[400px] flex flex-col gap-0 rounded-[10px] p-8"
        style={{
          backgroundColor: '#383838',
          border: '0.5px solid #484848',
        }}
      >
        {/* Top bar echo */}
        <div className="flex items-center gap-2 mb-5">
          <span className="text-[12px] font-[500] text-white">Client Portal</span>
          <span className="text-[10px]" style={{ color: '#7DA3C4' }}>
            Client Portal
          </span>
        </div>

        {/* Heading */}
        <p className="text-[16px] font-[500] mb-1" style={{ color: '#EDEEF0' }}>
          Sign in to your portal
        </p>
        <p className="text-[12px] mb-6" style={{ color: '#9CA3AF' }}>
          Enter your email and we&apos;ll send you a one-time link.
        </p>

        {magicSent ? (
          <p className="text-[12px] text-center py-2" style={{ color: '#10B981' }}>
            If a portal account exists for that email, a link has been sent. Check your inbox.
          </p>
        ) : (
          <form onSubmit={handleMagicLink} className="flex flex-col gap-3">
            <input
              type="email"
              value={magicEmail}
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
                'Send magic link'
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
