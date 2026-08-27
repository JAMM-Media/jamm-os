// path: frontend/src/app/portal/auth/page.tsx
//
// Magic-link token exchange. This page is only reached via a magic-link URL:
//   /portal/auth?token=<raw_token>
//
// It exchanges the token for a session and redirects to /portal.
// If the exchange fails the client sees an error with a "Return to sign in" link.
//
// All login UI (password form, magic-link request form) now lives at /portal/login.
// Do not add login UI back here -- this page is intentionally minimal.
'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

export default function PortalAuthPage() {
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token')
    if (!token) {
      setError('No login token found. Please request a new magic link.')
      return
    }
    fetch(`/api/backend/portal/auth?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (!res.ok) {
          setError('This link has expired or is invalid. Please request a new one.')
          return
        }
        const data = await res.json()
        if (!data.access_token) {
          setError('Invalid response from server. Please try again.')
          return
        }
        localStorage.setItem('portal_access_token', data.access_token)
        if (localStorage.getItem('portal_access_token')) {
          const params = new URLSearchParams(window.location.search)
          const redirect = params.get('redirect')
          window.location.replace(redirect || '/portal')
        } else {
          setError('Could not store session. Please try again.')
        }
      })
      .catch(() => {
        setError('This link has expired or is invalid. Please request a new one.')
      })
  }, [])

  if (error) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center gap-4 p-8"
        style={{ backgroundColor: '#F7F8FA' }}
      >
        <p className="text-[14px] text-center" style={{ color: '#DC2626' }}>{error}</p>
        <a
          href="/portal/login"
          className="text-[13px] font-medium underline transition-opacity hover:opacity-70"
          style={{ color: '#1F3148' }}
        >
          Return to sign in
        </a>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-3"
      style={{ backgroundColor: '#F7F8FA' }}
    >
      <Loader2 className="h-6 w-6 animate-spin" style={{ color: '#1F3148' }} />
      <p className="text-[13px]" style={{ color: '#6B7280' }}>Signing you in...</p>
    </div>
  )
}
