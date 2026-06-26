// path: frontend/src/components/settings/SecurityTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { Loader2, CheckCircle2 } from 'lucide-react'
import { settingsApi, type StaffAuthPolicy } from '@/lib/api/settingsApi'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

interface PolicyOption {
  value: StaffAuthPolicy
  label: string
  description: string
}

const POLICY_OPTIONS: PolicyOption[] = [
  {
    value: 'either',
    label: 'Password or magic link',
    description:
      'Staff can sign in with either a password or a one-time email link. Recommended for most firms.',
  },
  {
    value: 'password_only',
    label: 'Password only',
    description:
      'Staff must use their password to sign in. Magic links are disabled. Best for firms with strict security requirements.',
  },
  {
    value: 'magic_link_only',
    label: 'Magic link only',
    description:
      'Staff sign in via one-time email links. No passwords required. Eliminates weak password risk.',
  },
]

interface TimeoutOption {
  value: number
  label: string
  description: string
}

const TIMEOUT_OPTIONS: TimeoutOption[] = [
  { value: 30, label: '30 minutes', description: 'High security. Staff sign in frequently.' },
  { value: 60, label: '1 hour', description: 'Recommended for shared workstations.' },
  { value: 120, label: '2 hours', description: 'Balanced security for most firms.' },
  { value: 240, label: '4 hours', description: 'Standard for dedicated work machines.' },
  { value: 480, label: '8 hours', description: 'Default. One sign-in per workday.' },
  { value: 1440, label: '24 hours', description: 'Convenient for trusted devices.' },
]

export default function SecurityTab() {
  const [policy, setPolicy] = useState<StaffAuthPolicy>('either')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  // Password policy
  const [minLength, setMinLength] = useState(8)
  const [minLengthStr, setMinLengthStr] = useState('8')
  const [requireUppercase, setRequireUppercase] = useState(false)
  const [requireNumber, setRequireNumber] = useState(false)
  const [requireSpecial, setRequireSpecial] = useState(false)
  const [maxFailedAttempts, setMaxFailedAttempts] = useState(5)
  const [maxFailedStr, setMaxFailedStr] = useState('5')
  const [savingPassword, setSavingPassword] = useState(false)

  // Session timeout
  const [sessionTimeout, setSessionTimeout] = useState(480)
  const [savingTimeout, setSavingTimeout] = useState(false)

  // 2FA
  const [twoFAStatus, setTwoFAStatus] = useState<{ totp_enabled: boolean; is_required: boolean } | null>(null)
  const [twoFAView, setTwoFAView] = useState<'idle' | 'setup' | 'verify' | 'enabled'>('idle')
  const [setupData, setSetupData] = useState<{ secret: string; qr_code_base64: string; backup_codes: string[] } | null>(null)
  const [verifyCode, setVerifyCode] = useState('')
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null)
  const [disabling, setDisabling] = useState(false)
  const [setupLoading, setSetupLoading] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  useEffect(() => {
    const firmPromise = settingsApi
      .getMyFirm()
      .then((r) => {
        const data = r.data as {
          staff_auth_policy?: string
          settings?: Record<string, unknown> | null
        }
        if (data.staff_auth_policy) {
          setPolicy(data.staff_auth_policy as StaffAuthPolicy)
        }
        const passwordPolicy = (data.settings?.password_policy as Record<string, unknown>) || {}
        setMinLength((passwordPolicy.min_length as number) ?? 8)
        setRequireUppercase((passwordPolicy.require_uppercase as boolean) ?? false)
        setRequireNumber((passwordPolicy.require_number as boolean) ?? false)
        setRequireSpecial((passwordPolicy.require_special as boolean) ?? false)
        setMaxFailedAttempts((passwordPolicy.max_failed_attempts as number) ?? 5)
        setSessionTimeout((data.settings?.session_timeout_minutes as number) ?? 480)
      })

    const twoFAPromise = api.get('/auth/2fa/status').then((r) => {
      const status = r.data as { totp_enabled: boolean; is_required: boolean }
      setTwoFAStatus(status)
      setTwoFAView(status.totp_enabled ? 'enabled' : 'idle')
    }).catch(() => {})

    Promise.all([firmPromise, twoFAPromise]).finally(() => setLoading(false))
  }, [])

  async function handleSave(selected: StaffAuthPolicy) {
    setPolicy(selected)
    setSaving(true)
    try {
      await settingsApi.updateStaffAuthPolicy(selected)
      toast.success('Login policy updated.')
    } catch {
      toast.error('Could not save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleSavePasswordPolicy() {
    setSavingPassword(true)
    try {
      await settingsApi.updateFirmSettings({
        password_policy: {
          min_length: minLength,
          require_uppercase: requireUppercase,
          require_number: requireNumber,
          require_special: requireSpecial,
          max_failed_attempts: maxFailedAttempts,
        },
      })
      toast.success('Password policy saved.')
    } catch {
      toast.error('Could not save. Please try again.')
    } finally {
      setSavingPassword(false)
    }
  }

  async function handleSetup2FA() {
    setSetupLoading(true)
    try {
      const r = await api.post('/auth/2fa/setup')
      setSetupData(r.data as { secret: string; qr_code_base64: string; backup_codes: string[] })
      setVerifyCode('')
      setVerifyError(null)
      setTwoFAView('setup')
    } catch {
      toast.error('Could not start 2FA setup. Please try again.')
    } finally {
      setSetupLoading(false)
    }
  }

  async function handleVerify2FA() {
    if (!setupData) return
    setVerifying(true)
    setVerifyError(null)
    const codes = setupData.backup_codes
    try {
      await api.post('/auth/2fa/verify', { code: verifyCode })
      setTwoFAView('enabled')
      setSetupData(null)
      setBackupCodes(codes)
      toast.success('2FA enabled.')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setVerifyError(detail ?? 'Invalid code. Please try again.')
    } finally {
      setVerifying(false)
    }
  }

  async function handleDisable2FA() {
    setDisabling(true)
    try {
      await api.post('/auth/2fa/disable')
      setTwoFAView('idle')
      setBackupCodes(null)
      toast.success('2FA disabled.')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      toast.error(detail ?? 'Could not disable 2FA. Please try again.')
    } finally {
      setDisabling(false)
    }
  }

  async function handleRegenerate() {
    setRegenerating(true)
    try {
      const r = await api.post('/auth/2fa/backup-codes/regenerate')
      setBackupCodes((r.data as { backup_codes: string[] }).backup_codes)
      toast.success('New backup codes generated. Save them now.')
    } catch {
      toast.error('Could not regenerate backup codes. Please try again.')
    } finally {
      setRegenerating(false)
    }
  }

  async function handleSaveSessionTimeout(minutes: number) {
    setSessionTimeout(minutes)
    setSavingTimeout(true)
    try {
      await settingsApi.updateFirmSettings({ session_timeout_minutes: minutes })
      toast.success('Session timeout updated.')
    } catch {
      toast.error('Could not save. Please try again.')
    } finally {
      setSavingTimeout(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-[#6B7280]" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 max-w-lg">
      {/* Section 1: Staff login policy */}
      <div>
        <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
          Staff login policy
        </p>
        <p className="text-[12px] text-[#6B7280] mb-4">
          Control how your staff members sign in to JAMM PX.
        </p>

        <div className="flex flex-col gap-2">
          {POLICY_OPTIONS.map((opt) => {
            const selected = policy === opt.value
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSave(opt.value)}
                disabled={saving}
                className={cn(
                  'flex items-start gap-3 rounded-[8px] px-3.5 py-3 text-left transition-colors disabled:opacity-70 cursor-pointer',
                  selected
                    ? 'border-[1.5px] border-[#1F3148]'
                    : 'border border-[0.5px] border-[#C8CDD6] hover:border-[#A0A8B4]',
                )}
                style={{ backgroundColor: '#EDEEF0' }}
              >
                <div
                  className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center"
                  style={{
                    border: selected ? '1.5px solid #1F3148' : '1.5px solid #C8CDD6',
                    backgroundColor: selected ? '#1F3148' : 'transparent',
                  }}
                >
                  {selected && (
                    <div className="w-1.5 h-1.5 rounded-full bg-white" />
                  )}
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-[13px] font-[500] text-[#1F3148]">{opt.label}</span>
                  <span className="text-[11px] text-[#6B7280] leading-snug">{opt.description}</span>
                </div>
              </button>
            )
          })}
        </div>

        <div
          className="mt-3 rounded-[6px] px-3 py-2 text-[11px]"
          style={{ backgroundColor: '#FEF3C7', color: '#92400E' }}
        >
          Your own login always requires a password regardless of this setting.
        </div>

        {saving && (
          <div className="flex items-center gap-2 mt-3 text-[11px] text-[#6B7280]">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Saving...
          </div>
        )}
      </div>

      <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] my-6" />

      {/* Section 2: Password policy */}
      <div>
        <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
          Password policy
        </p>
        <p className="text-[12px] text-[#6B7280] mb-4">
          Set requirements for staff passwords at your firm.
        </p>

        {/* Minimum length */}
        <div
          className="flex items-center justify-between px-3 py-3 rounded-[8px] border border-[0.5px] border-[#C8CDD6] mb-2"
          style={{ backgroundColor: '#EDEEF0' }}
        >
          <span className="text-[13px] text-[#1F3148]">Minimum length</span>
          <input
            type="number"
            value={minLengthStr}
            min={6}
            max={32}
            onChange={(e) => { setMinLengthStr(e.target.value); const v = parseInt(e.target.value, 10); if (!isNaN(v) && v >= 6 && v <= 32) setMinLength(v) }}
            onBlur={() => setMinLengthStr(String(minLength))}
            className="w-16 text-center text-[13px] text-[#1F3148] rounded-[6px] border border-[#C8CDD6] bg-white px-2 py-1 outline-none focus:border-[#1F3148]"
          />
        </div>

        {/* Toggle rows */}
        {(
          [
            { label: 'Require uppercase letter', value: requireUppercase, set: setRequireUppercase },
            { label: 'Require number', value: requireNumber, set: setRequireNumber },
            { label: 'Require special character', value: requireSpecial, set: setRequireSpecial },
          ] as { label: string; value: boolean; set: (v: boolean) => void }[]
        ).map(({ label, value, set }) => (
          <div
            key={label}
            className="flex items-center justify-between px-3 py-3 rounded-[8px] border border-[0.5px] border-[#C8CDD6] mb-2"
            style={{ backgroundColor: '#EDEEF0' }}
          >
            <span className="text-[13px] text-[#1F3148]">{label}</span>
            <button
              type="button"
              role="switch"
              aria-checked={value}
              onClick={() => set(!value)}
              className={cn(
                'relative w-9 h-5 rounded-full transition-colors flex-shrink-0 overflow-hidden',
                value ? 'bg-[#1F3148]' : 'bg-[#C8CDD6]',
              )}
            >
              <span
                className={cn(
                  'absolute top-[3px] left-[3px] w-3.5 h-3.5 rounded-full bg-white shadow transition-transform',
                  value ? 'translate-x-[16px]' : 'translate-x-0',
                )}
              />
            </button>
          </div>
        ))}

        {/* Max failed attempts */}
        <div
          className="px-3 py-3 rounded-[8px] border border-[0.5px] border-[#C8CDD6] mb-2"
          style={{ backgroundColor: '#EDEEF0' }}
        >
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[#1F3148]">Lock account after N failed attempts</span>
            <input
              type="number"
              value={maxFailedStr}
              min={3}
              max={20}
              onChange={(e) => { setMaxFailedStr(e.target.value); const v = parseInt(e.target.value, 10); if (!isNaN(v) && v >= 3 && v <= 20) setMaxFailedAttempts(v) }}
              onBlur={() => setMaxFailedStr(String(maxFailedAttempts))}
              className="w-16 text-center text-[13px] text-[#1F3148] rounded-[6px] border border-[#C8CDD6] bg-white px-2 py-1 outline-none focus:border-[#1F3148]"
            />
          </div>
          <p className="text-[11px] text-[#6B7280] mt-1">
            Account is locked for 30 minutes after this many consecutive failed logins.
          </p>
        </div>

        {/* Save button */}
        <div className="flex justify-end mt-4">
          <button
            type="button"
            onClick={handleSavePasswordPolicy}
            disabled={savingPassword}
            className="flex items-center gap-2 h-8 px-4 rounded-[6px] text-[13px] font-[500] text-white disabled:opacity-70 cursor-pointer"
            style={{ backgroundColor: '#1F3148' }}
          >
            {savingPassword && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Save password policy
          </button>
        </div>
      </div>

      <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] my-6" />

      {/* Section 3: Session timeout */}
      <div>
        <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
          Session timeout
        </p>
        <p className="text-[12px] text-[#6B7280] mb-4">
          How long staff stay logged in before being asked to sign in again.
        </p>

        <div className="flex flex-col gap-2">
          {TIMEOUT_OPTIONS.map((opt) => {
            const selected = sessionTimeout === opt.value
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSaveSessionTimeout(opt.value)}
                disabled={savingTimeout}
                className={cn(
                  'flex items-start gap-3 rounded-[8px] px-3.5 py-3 text-left transition-colors disabled:opacity-70 cursor-pointer',
                  selected
                    ? 'border-[1.5px] border-[#1F3148]'
                    : 'border border-[0.5px] border-[#C8CDD6] hover:border-[#A0A8B4]',
                )}
                style={{ backgroundColor: '#EDEEF0' }}
              >
                <div
                  className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center"
                  style={{
                    border: selected ? '1.5px solid #1F3148' : '1.5px solid #C8CDD6',
                    backgroundColor: selected ? '#1F3148' : 'transparent',
                  }}
                >
                  {selected && (
                    <div className="w-1.5 h-1.5 rounded-full bg-white" />
                  )}
                </div>
                <div className="flex flex-col gap-0.5 flex-1">
                  <span className="text-[13px] font-[500] text-[#1F3148]">{opt.label}</span>
                  <span className="text-[11px] text-[#6B7280] leading-snug">{opt.description}</span>
                </div>
                {selected && savingTimeout && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#6B7280] mt-0.5 flex-shrink-0" />
                )}
              </button>
            )
          })}
        </div>

        <div
          className="mt-3 rounded-[6px] px-3 py-2 text-[11px]"
          style={{ backgroundColor: '#FEF3C7', color: '#92400E' }}
        >
          Changes take effect on the next login. Active sessions are not affected.
        </div>
      </div>

      <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] my-6" />

      {/* Section 4: Two-factor authentication */}
      <div>
        {twoFAView === 'idle' && (
          <>
            <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
              Two-factor authentication
            </p>
            <p className="text-[12px] text-[#6B7280] mb-4">
              Add an extra layer of security to your account. Once enabled, you will need your authenticator app each time you sign in.
            </p>
            <button
              type="button"
              onClick={handleSetup2FA}
              disabled={setupLoading}
              className="flex items-center gap-2 h-8 px-4 rounded-[6px] text-[13px] font-[500] text-white disabled:opacity-70 cursor-pointer"
              style={{ backgroundColor: '#1F3148' }}
            >
              {setupLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Set up 2FA
            </button>
          </>
        )}

        {twoFAView === 'setup' && setupData && (
          <>
            <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
              Scan this QR code
            </p>
            <p className="text-[12px] text-[#6B7280] mb-4">
              Open your authenticator app (Google Authenticator, Authy, 1Password, or any TOTP app) and scan the QR code below.
            </p>
            <img
              src={setupData.qr_code_base64.startsWith('data:') ? setupData.qr_code_base64 : `data:image/png;base64,${setupData.qr_code_base64}`}
              alt="2FA QR code"
              className="w-40 h-40 rounded-[6px] border border-[0.5px] border-[#C8CDD6]"
            />
            <p className="text-[11px] text-[#6B7280] mt-3">
              Can not scan? Enter this code manually:
            </p>
            <span className="font-mono text-[11px] bg-[#EDEEF0] dark:bg-[#383838] px-2 py-1 rounded select-all break-all inline-block mt-1">
              {setupData.secret}
            </span>

            <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] my-4" />

            <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
              Enter the 6-digit code
            </p>
            <p className="text-[12px] text-[#6B7280] mb-3">
              Type the code shown in your authenticator app to confirm setup.
            </p>
            <input
              type="text"
              value={verifyCode}
              onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              inputMode="numeric"
              autoComplete="off"
              placeholder="000000"
              className="w-36 h-10 text-center font-mono text-[18px] text-[#1F3148] rounded-[6px] border border-[#C8CDD6] bg-white px-2 outline-none focus:border-[#1F3148] block"
            />
            {verifyError && (
              <p className="text-[12px] text-[#DC2626] mt-1">{verifyError}</p>
            )}

            <div className="mt-4">
              <p className="text-[12px] font-[500] text-[#1F3148] mb-1">Save your backup codes</p>
              <p className="text-[11px] text-[#6B7280] mb-2">
                Store these somewhere safe. Each code can only be used once to sign in if you lose access to your authenticator app.
              </p>
              <div className="grid grid-cols-2 gap-1">
                {setupData.backup_codes.map((code) => (
                  <span
                    key={code}
                    className="font-mono text-[11px] bg-[#EDEEF0] dark:bg-[#383838] px-2 py-1 rounded"
                  >
                    {code}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => { setTwoFAView('idle'); setSetupData(null); setVerifyCode(''); setVerifyError(null) }}
                className="h-8 px-4 rounded-[6px] border border-[0.5px] border-[#C8CDD6] text-[13px] font-[500] text-[#6B7280] hover:bg-[#EDEEF0] dark:hover:bg-[#383838] transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleVerify2FA}
                disabled={verifyCode.length !== 6 || verifying}
                className="flex items-center gap-2 h-8 px-4 rounded-[6px] text-[13px] font-[500] text-white disabled:opacity-70 cursor-pointer"
                style={{ backgroundColor: '#1F3148' }}
              >
                {verifying && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Verify and enable
              </button>
            </div>
          </>
        )}

        {twoFAView === 'enabled' && (
          <>
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 className="w-4 h-4 text-[#065F46]" />
              <span className="text-[13px] font-[500] text-[#065F46]">
                Two-factor authentication is enabled
              </span>
            </div>
            <p className="text-[12px] text-[#6B7280] mb-4">
              Your account is protected with an authenticator app. You will be prompted for a code each time you sign in.
            </p>

            {/* Row 1: Regenerate backup codes */}
            <div className="flex items-start justify-between gap-4 py-3">
              <div>
                <p className="text-[12px] font-[500] text-[#1F3148]">Backup codes</p>
                <p className="text-[11px] text-[#6B7280] mt-0.5">
                  Generate a new set of backup codes. Your old codes will stop working immediately.
                </p>
              </div>
              <button
                type="button"
                onClick={handleRegenerate}
                disabled={regenerating}
                className="flex-shrink-0 flex items-center gap-1.5 h-8 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] text-[12px] text-[#6B7280] hover:bg-[#EDEEF0] dark:hover:bg-[#383838] transition-colors cursor-pointer disabled:opacity-70"
              >
                {regenerating && <Loader2 className="w-3 h-3 animate-spin" />}
                Regenerate codes
              </button>
            </div>

            {backupCodes && (
              <div className="mb-3">
                <div className="grid grid-cols-2 gap-1">
                  {backupCodes.map((code) => (
                    <span
                      key={code}
                      className="font-mono text-[11px] bg-[#EDEEF0] dark:bg-[#383838] px-2 py-1 rounded"
                    >
                      {code}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848]" />

            {/* Row 2: Disable 2FA */}
            <div className="flex items-start justify-between gap-4 py-3">
              <div>
                <p className="text-[12px] font-[500] text-[#991B1B]">Disable two-factor authentication</p>
                <p className="text-[11px] text-[#6B7280] mt-0.5">
                  Removing 2FA makes your account less secure.
                </p>
              </div>
              <button
                type="button"
                onClick={handleDisable2FA}
                disabled={disabling}
                className="flex-shrink-0 flex items-center gap-1.5 h-8 px-3 text-[12px] rounded-[6px] border border-[#991B1B] text-[#991B1B] hover:bg-[#FEE2E2] transition-colors cursor-pointer disabled:opacity-70"
              >
                {disabling && <Loader2 className="w-3 h-3 animate-spin" />}
                Disable 2FA
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
