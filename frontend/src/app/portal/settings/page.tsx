// path: frontend/src/app/portal/settings/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'

export const dynamic = 'force-dynamic'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] text-[13px] bg-[#2D2D2D] border border-[#484848] text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'

interface Toast {
  id: number
  message: string
  type: 'success' | 'error'
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => onDismiss(t.id)}
          className="cursor-pointer flex items-start gap-3 rounded-[8px] px-4 py-3 text-[12px] min-w-[260px] max-w-[320px] shadow-lg"
          style={{
            backgroundColor: '#383838',
            borderLeft: `3px solid ${t.type === 'success' ? '#10B981' : '#E24B4A'}`,
          }}
        >
          <span style={{ color: '#EDEEF0' }}>{t.message}</span>
        </div>
      ))}
    </div>
  )
}

export default function PortalSettingsPage() {
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

  return (
    <div
      className="min-h-screen flex justify-center py-12 px-4"
      style={{ backgroundColor: '#2D2D2D' }}
    >
      <div className="w-full max-w-[420px] flex flex-col gap-6">
        <div>
          <p className="text-[16px] font-[500]" style={{ color: '#EDEEF0' }}>
            Account Settings
          </p>
          <p className="text-[12px] mt-1" style={{ color: '#9CA3AF' }}>
            Manage your portal account preferences.
          </p>
        </div>

        {/* Password card */}
        <div
          className="rounded-[10px] p-6"
          style={{ backgroundColor: '#383838', border: '0.5px solid #484848' }}
        >
          {hasPassword === null ? (
            <div className="flex justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#9CA3AF' }} />
            </div>
          ) : (
            <>
              <p className="text-[13px] font-[500] mb-1" style={{ color: '#EDEEF0' }}>
                {hasPassword ? 'Change password' : 'Set a password'}
              </p>
              <p className="text-[12px] mb-5" style={{ color: '#9CA3AF' }}>
                {hasPassword
                  ? 'Update your current portal password.'
                  : 'Optional. Set a password if you prefer to log in without a magic link each time.'}
              </p>

              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                {hasPassword && (
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-[500]" style={{ color: '#EDEEF0' }}>
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
                  <label className="text-[11px] font-[500]" style={{ color: '#EDEEF0' }}>
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
                  <label className="text-[11px] font-[500]" style={{ color: '#EDEEF0' }}>
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
                  <p className="text-[11px]" style={{ color: '#E24B4A' }}>
                    {fieldError}
                  </p>
                )}

                <div className="flex justify-end mt-1">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="h-9 px-4 rounded-[6px] text-[12px] font-[500] text-white flex items-center gap-2 disabled:opacity-60"
                    style={{ backgroundColor: '#3A6A94' }}
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

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
