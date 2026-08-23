// path: frontend/src/app/portal/settings/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { PortalShell } from '@/components/portal/PortalShell'

const inputClass =
  'w-full h-9 px-3 rounded-lg text-[13px] bg-white border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-100 transition-colors'

interface Toast {
  id: number
  message: string
  type: 'success' | 'error'
}

interface PortalMe {
  client_id: string
  client_name: string
  firm_name: string
  portal_display_name: string
  portal_logo_url: string | null
  portal_mode: 'light' | 'dark'
  portal_top_bar_color: string
  portal_page_color: string
  portal_tab_bar_color: string
  portal_accent_color: string
  portal_avatar_color: string
  portal_subtitle_color: string
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => onDismiss(t.id)}
          className="cursor-pointer flex items-start gap-3 rounded-xl px-4 py-3 text-[12px] min-w-[260px] max-w-[320px] shadow-lg border border-gray-100 bg-white"
          style={{ borderLeft: `3px solid ${t.type === 'success' ? '#10B981' : '#DC2626'}` }}
        >
          <span style={{ color: '#1F3148' }}>{t.message}</span>
        </div>
      ))}
    </div>
  )
}

export default function PortalSettingsPage() {
  const router = useRouter()
  const [me, setMe] = useState<PortalMe | null>(null)
  const [hasPassword, setHasPassword] = useState<boolean | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [fieldError, setFieldError] = useState('')

  const [toasts, setToasts] = useState<Toast[]>([])
  const toastCounter = useState(0)

  function addToast(message: string, type: 'success' | 'error') {
    const id = ++toastCounter[0]
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
  }

  function dismissToast(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  // Fetch firm/client identity for PortalShell props
  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    fetch('/api/backend/portal/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (res) => {
        if (res.status === 401 || res.status === 403) {
          router.replace('/portal/login')
          return
        }
        if (!res.ok) return
        const data: PortalMe = await res.json()
        setMe(data)
      })
      .catch(() => router.replace('/portal/login'))
  }, [router])

  // Fetch whether the client already has a password set
  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    fetch('/api/backend/portal/account/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setHasPassword(!!data.has_password)
      })
      .catch(() => setHasPassword(false))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFieldError('')

    if (newPassword !== confirmPassword) {
      setFieldError("Passwords don't match.")
      return
    }
    if (newPassword.length < 8) {
      setFieldError('Password must be at least 8 characters.')
      return
    }

    const token = localStorage.getItem('portal_access_token')
    if (!token) return

    setSubmitting(true)
    try {
      const body: Record<string, string> = { new_password: newPassword, confirm_password: confirmPassword }
      if (hasPassword && currentPassword) {
        body.current_password = currentPassword
      }

      const res = await fetch('/api/backend/portal/account/set-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (!res.ok) {
        const detail: string = data.detail ?? ''
        if (detail.toLowerCase().includes('current password')) {
          setFieldError('Current password is incorrect.')
        } else {
          setFieldError(detail || 'Something went wrong.')
        }
        return
      }

      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setHasPassword(true)
      addToast('Password saved. You can now log in with your email and password.', 'success')
    } catch {
      addToast('Something went wrong. Please try again.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // Loading skeleton while identity resolves
  if (!me) {
    return (
      <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#2D2D2D' }}>
        <div className="h-12 flex-shrink-0 animate-pulse" style={{ backgroundColor: '#1F3148' }} />
        <div className="h-10 flex-shrink-0 animate-pulse" style={{ backgroundColor: '#252525' }} />
        <div className="flex-1" />
      </div>
    )
  }

  const logoImgSrc = me.portal_logo_url
    ? `https://api.jammpx.com${me.portal_logo_url}`
    : undefined

  return (
    <>
      <PortalShell
        firmName={me.portal_display_name || me.firm_name}
        logoUrl={logoImgSrc}
        brandColor={me.portal_top_bar_color}
        pageColor={me.portal_page_color}
        tabBarColor={me.portal_tab_bar_color}
        accentColor={me.portal_accent_color}
        avatarColor={me.portal_avatar_color}
        subtitleColor={me.portal_subtitle_color}
        portalMode={me.portal_mode}
        clientName={me.client_name}
        activeTab=""
        onTabChange={(tab) => router.push(`/portal?tab=${tab}`)}
      >
        <div className="p-6 flex flex-col gap-6 max-w-[480px]">
          <div>
            <h1 className="text-[22px] font-bold" style={{ color: '#1F3148' }}>Settings</h1>
            <p className="text-[13px] mt-1" style={{ color: '#6B7280' }}>
              Manage your portal account preferences.
            </p>
          </div>

          {/* Password card -- light theme */}
          <div className="bg-white rounded-xl border border-gray-100 p-6">
            {hasPassword === null ? (
              <div className="flex flex-col gap-3">
                <div className="h-4 w-32 rounded animate-pulse bg-gray-100" />
                {[1, 2].map((j) => (
                  <div key={j} className="flex flex-col gap-1.5">
                    <div className="h-3 w-24 rounded animate-pulse bg-gray-100" />
                    <div className="h-9 w-full rounded-lg animate-pulse bg-gray-100" />
                  </div>
                ))}
                <div className="flex justify-end">
                  <div className="h-9 w-28 rounded-lg animate-pulse bg-gray-100" />
                </div>
              </div>
            ) : (
              <>
                <p className="text-[14px] font-semibold mb-1" style={{ color: '#1F3148' }}>
                  {hasPassword ? 'Change password' : 'Set a password'}
                </p>
                <p className="text-[12px] mb-5" style={{ color: '#6B7280' }}>
                  {hasPassword
                    ? 'Update your current portal password.'
                    : 'Optional. Set a password if you prefer to log in without a magic link each time.'}
                </p>

                <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                  {hasPassword && (
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-medium" style={{ color: '#374151' }}>
                        Current password
                      </label>
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        required
                        className={inputClass}
                      />
                    </div>
                  )}

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium" style={{ color: '#374151' }}>
                      New password
                    </label>
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      required
                      minLength={8}
                      className={inputClass}
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium" style={{ color: '#374151' }}>
                      Confirm password
                    </label>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      className={inputClass}
                    />
                  </div>

                  {fieldError && (
                    <p className="text-[11px]" style={{ color: '#DC2626' }}>
                      {fieldError}
                    </p>
                  )}

                  <div className="flex justify-end mt-1">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="h-9 px-4 rounded-lg text-[13px] font-medium text-white flex items-center gap-2 disabled:opacity-60 transition-opacity"
                      style={{ backgroundColor: '#1F3148' }}
                    >
                      {submitting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Saving...
                        </>
                      ) : hasPassword ? (
                        'Update password'
                      ) : (
                        'Set password'
                      )}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      </PortalShell>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  )
}
