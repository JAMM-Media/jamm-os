// path: frontend/src/app/portal/settings/page.tsx
// Sections built: Profile (name/email/phone editing), Security (password + active sessions).
// Explicitly out of scope -- no backend infrastructure exists for either:
//   - Two-factor authentication: no TOTP or SMS verification backend exists. SMS specifically
//     is already deferred elsewhere in this project. Not a styling gap.
//   - Notification preferences: no notification-preference backend exists. Building toggles
//     here would be fake functionality.
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, Monitor } from 'lucide-react'
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

interface PortalSession {
  id: string
  created_at: string
  last_active_at: string
  ip_address: string | null
  user_agent: string | null
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

function formatSessionDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  })
}

function formatUserAgent(ua: string | null): string {
  if (!ua) return 'Unknown device'
  let browser = 'Browser'
  if (ua.includes('Edg/') || ua.includes('Edge/')) browser = 'Edge'
  else if (ua.includes('Chrome')) browser = 'Chrome'
  else if (ua.includes('Firefox')) browser = 'Firefox'
  else if (ua.includes('Safari')) browser = 'Safari'
  let os = ''
  if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS'
  else if (ua.includes('Android')) os = 'Android'
  else if (ua.includes('Windows')) os = 'Windows'
  else if (ua.includes('Mac OS X') || ua.includes('Macintosh')) os = 'Mac'
  else if (ua.includes('Linux')) os = 'Linux'
  return os ? browser + ' on ' + os : browser
}

function formatPhone(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 10)
  if (digits.length <= 3) return digits
  if (digits.length <= 6) return `${digits.slice(0, 3)}-${digits.slice(3)}`
  return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`
}

export default function PortalSettingsPage() {
  const router = useRouter()
  const [me, setMe] = useState<PortalMe | null>(null)
  const [avatarColor, setAvatarColor] = useState('#3A6A94')

  // Profile state
  const [profileName, setProfileName] = useState('')
  const [profileEmail, setProfileEmail] = useState('')
  const [profilePhone, setProfilePhone] = useState('')
  const [profileLoading, setProfileLoading] = useState(true)
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileError, setProfileError] = useState('')

  // Password state
  const [hasPassword, setHasPassword] = useState<boolean | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pwSubmitting, setPwSubmitting] = useState(false)
  const [pwFieldError, setPwFieldError] = useState('')

  // Sessions state
  const [sessions, setSessions] = useState<PortalSession[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [revokingId, setRevokingId] = useState<string | null>(null)

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
        setAvatarColor(data.portal_avatar_color)
      })
      .catch(() => router.replace('/portal/login'))
  }, [router])

  // Fetch profile fields
  const fetchProfile = useCallback(() => {
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    setProfileLoading(true)
    fetch('/api/backend/portal/account/profile', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setProfileName(data.name ?? '')
        setProfileEmail(data.email ?? '')
        setProfilePhone(formatPhone(data.phone ?? ''))
      })
      .catch(() => {})
      .finally(() => setProfileLoading(false))
  }, [])

  useEffect(() => { fetchProfile() }, [fetchProfile])

  // Fetch password status (legacy endpoint; endpoint may not exist yet -- handled gracefully)
  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    fetch('/api/backend/portal/account/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => setHasPassword(!!data?.has_password))
      .catch(() => setHasPassword(false))
  }, [])

  // Fetch sessions
  const fetchSessions = useCallback(() => {
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    setSessionsLoading(true)
    fetch('/api/backend/portal/account/sessions', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setSessions(Array.isArray(data) ? data : []))
      .catch(() => setSessions([]))
      .finally(() => setSessionsLoading(false))
  }, [])

  useEffect(() => { fetchSessions() }, [fetchSessions])

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault()
    setProfileError('')
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    setProfileSaving(true)
    try {
      const res = await fetch('/api/backend/portal/account/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: profileName.trim(),
          email: profileEmail.trim(),
          phone: profilePhone.trim() || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setProfileError(data.detail || 'Something went wrong.')
        return
      }
      setProfileName(data.name ?? profileName)
      setProfileEmail(data.email ?? profileEmail)
      setProfilePhone(formatPhone(data.phone ?? ''))
      addToast('Profile updated.', 'success')
    } catch {
      addToast('Something went wrong. Please try again.', 'error')
    } finally {
      setProfileSaving(false)
    }
  }

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault()
    setPwFieldError('')
    if (newPassword !== confirmPassword) { setPwFieldError("Passwords don't match."); return }
    if (newPassword.length < 8) { setPwFieldError('Password must be at least 8 characters.'); return }
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    setPwSubmitting(true)
    try {
      const body: Record<string, string> = { new_password: newPassword, confirm_password: confirmPassword }
      if (hasPassword && currentPassword) body.current_password = currentPassword
      const res = await fetch('/api/backend/portal/account/set-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail: string = data.detail ?? ''
        setPwFieldError(detail.toLowerCase().includes('current password') ? 'Current password is incorrect.' : (detail || 'Something went wrong.'))
        return
      }
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('')
      setHasPassword(true)
      addToast('Password saved.', 'success')
    } catch {
      addToast('Something went wrong. Please try again.', 'error')
    } finally {
      setPwSubmitting(false)
    }
  }

  async function handleRevokeSession(sessionId: string) {
    const token = localStorage.getItem('portal_access_token')
    if (!token) return
    setRevokingId(sessionId)
    try {
      const res = await fetch(`/api/backend/portal/account/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok || res.status === 204) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId))
        addToast('Session revoked.', 'success')
      } else {
        addToast('Could not revoke session.', 'error')
      }
    } catch {
      addToast('Something went wrong.', 'error')
    } finally {
      setRevokingId(null)
    }
  }

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

  const initials = (profileName || me.client_name || '?').charAt(0).toUpperCase()

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
        <div className="p-6 flex flex-col gap-6 max-w-[520px]">
          <div>
            <h1 className="text-[22px] font-bold" style={{ color: '#1F3148' }}>Settings</h1>
            <p className="text-[13px] mt-1" style={{ color: '#6B7280' }}>
              Manage your portal account preferences.
            </p>
          </div>

          {/* Profile */}
          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <p className="text-[14px] font-semibold mb-1" style={{ color: '#1F3148' }}>Profile</p>
            <p className="text-[12px] mb-5" style={{ color: '#6B7280' }}>
              Update your personal information.
            </p>
            {profileLoading ? (
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((j) => (
                  <div key={j} className="flex flex-col gap-1.5">
                    <div className="h-3 w-24 rounded animate-pulse bg-gray-100" />
                    <div className="h-9 w-full rounded-lg animate-pulse bg-gray-100" />
                  </div>
                ))}
              </div>
            ) : (
              <form onSubmit={handleProfileSave} className="flex flex-col gap-4">
                <div className="flex items-center gap-4 mb-2">
                  <div
                    className="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 text-[16px] font-semibold text-white"
                    style={{ backgroundColor: avatarColor }}
                  >
                    {initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium" style={{ color: '#1F3148' }}>{profileName || me.client_name}</p>
                    <p className="text-[12px]" style={{ color: '#6B7280' }}>{profileEmail}</p>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-medium" style={{ color: '#374151' }}>Full name</label>
                  <input type="text" value={profileName} onChange={(e) => setProfileName(e.target.value)} required className={inputClass} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-medium" style={{ color: '#374151' }}>Email address</label>
                  <input type="email" value={profileEmail} onChange={(e) => setProfileEmail(e.target.value)} className={inputClass} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-medium" style={{ color: '#374151' }}>Phone number (optional)</label>
                  <input type="tel" value={profilePhone} onChange={(e) => setProfilePhone(formatPhone(e.target.value))} placeholder="413-427-5434" className={inputClass} />
                </div>
                {profileError && <p className="text-[11px]" style={{ color: '#DC2626' }}>{profileError}</p>}
                <div className="flex justify-end mt-1">
                  <button
                    type="submit"
                    disabled={profileSaving}
                    className="h-9 px-4 rounded-lg text-[13px] font-medium text-white flex items-center gap-2 disabled:opacity-60 transition-opacity"
                    style={{ backgroundColor: '#1F3148' }}
                  >
                    {profileSaving ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Saving...</> : 'Save changes'}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Security */}
          <div className="flex flex-col gap-4">
            <div>
              <h2 className="text-[14px] font-semibold" style={{ color: '#1F3148' }}>Security</h2>
              <p className="text-[12px] mt-0.5" style={{ color: '#6B7280' }}>Keep your account secure.</p>
            </div>

            {/* Change password */}
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
                  <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-3">
                    {hasPassword && (
                      <div className="flex flex-col gap-1">
                        <label className="text-[11px] font-medium" style={{ color: '#374151' }}>Current password</label>
                        <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required className={inputClass} />
                      </div>
                    )}
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-medium" style={{ color: '#374151' }}>New password</label>
                      <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} className={inputClass} />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-medium" style={{ color: '#374151' }}>Confirm password</label>
                      <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required className={inputClass} />
                    </div>
                    {pwFieldError && <p className="text-[11px]" style={{ color: '#DC2626' }}>{pwFieldError}</p>}
                    <div className="flex justify-end mt-1">
                      <button
                        type="submit"
                        disabled={pwSubmitting}
                        className="h-9 px-4 rounded-lg text-[13px] font-medium text-white flex items-center gap-2 disabled:opacity-60 transition-opacity"
                        style={{ backgroundColor: '#1F3148' }}
                      >
                        {pwSubmitting ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Saving...</> : hasPassword ? 'Update password' : 'Set password'}
                      </button>
                    </div>
                  </form>
                </>
              )}
            </div>

            {/* Active sessions */}
            <div className="bg-white rounded-xl border border-gray-100 p-6">
              <p className="text-[14px] font-semibold mb-1" style={{ color: '#1F3148' }}>Active sessions</p>
              <p className="text-[12px] mb-5" style={{ color: '#6B7280' }}>
                These are devices that are currently signed in to your account.
                Revoking a session signs that device out immediately.
                If you revoke the session you are currently using, you will be signed out.
              </p>
              {sessionsLoading ? (
                <div className="flex flex-col gap-3">
                  {[1, 2].map((i) => (
                    <div key={i} className="h-12 rounded-lg animate-pulse bg-gray-100" />
                  ))}
                </div>
              ) : sessions.length === 0 ? (
                <p className="text-[13px]" style={{ color: '#6B7280' }}>No active sessions found.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {sessions.map((s) => (
                    <div key={s.id} className="flex items-start gap-3 p-3 rounded-lg border border-gray-100">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ backgroundColor: '#F3F4F6' }}>
                        <Monitor size={14} style={{ color: '#6B7280' }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-medium" style={{ color: '#1F3148' }}>
                          {formatUserAgent(s.user_agent)}
                        </p>
                        <p className="text-[11px] mt-0.5" style={{ color: '#9CA3AF' }}>
                          Signed in {formatSessionDate(s.created_at)} &middot; Active {formatSessionDate(s.last_active_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRevokeSession(s.id)}
                        disabled={revokingId === s.id}
                        className="text-[12px] font-medium flex-shrink-0 transition-opacity hover:opacity-70 disabled:opacity-40"
                        style={{ color: '#DC2626' }}
                      >
                        {revokingId === s.id ? 'Revoking...' : 'Revoke'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </PortalShell>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  )
}
