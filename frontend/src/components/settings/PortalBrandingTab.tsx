// path: frontend/src/components/settings/PortalBrandingTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Upload, X, Loader2 } from 'lucide-react'
import api from '@/lib/api'

interface ColorSet {
  top_bar: string
  page: string
  tab_bar: string
  accent: string
  avatar: string
  subtitle: string
  card: string
  text_primary: string
  text_muted: string
}

interface BrandingState {
  portal_display_name: string
  portal_logo_s3_key: string | null
  portal_mode: 'light' | 'dark'
  colors_dark: ColorSet
  colors_light: ColorSet
}

const DARK_DEFAULTS: ColorSet = {
  top_bar: '#1A2535',
  page: '#2D2D2D',
  tab_bar: '#252525',
  accent: '#4A7FA5',
  avatar: '#3A6A94',
  subtitle: '#7DA3C4',
  card: '#383838',
  text_primary: '#EDEEF0',
  text_muted: '#9CA3AF',
}

const LIGHT_DEFAULTS: ColorSet = {
  top_bar: '#1F3148',
  page: '#E4E6EA',
  tab_bar: '#EDEEF0',
  accent: '#1F3148',
  avatar: '#1F3148',
  subtitle: '#7DA3C4',
  card: '#EDEEF0',
  text_primary: '#111111',
  text_muted: '#6B7280',
}

const VALID_HEX = /^#[0-9A-Fa-f]{6}$/
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp']
const MAX_BYTES = 2 * 1024 * 1024

const COLOR_LABELS = [
  { key: 'top_bar', label: 'Top bar' },
  { key: 'page', label: 'Page background' },
  { key: 'tab_bar', label: 'Tab bar' },
  { key: 'accent', label: 'Accent (tabs & buttons)' },
  { key: 'avatar', label: 'Client avatar' },
  { key: 'subtitle', label: 'Subtitle text ("Client Portal")' },
  { key: 'card', label: 'Card / item background' },
  { key: 'text_primary', label: 'Primary text' },
  { key: 'text_muted', label: 'Secondary text' },
] as const

export default function PortalBrandingTab() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [firmId, setFirmId] = useState<string | null>(null)
  const [firmName, setFirmName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null)
  const [saveConfirmed, setSaveConfirmed] = useState(false)
  const [branding, setBranding] = useState<BrandingState>({
    portal_display_name: '',
    portal_logo_s3_key: null,
    portal_mode: 'dark',
    colors_dark: { ...DARK_DEFAULTS },
    colors_light: { ...LIGHT_DEFAULTS },
  })

  useEffect(() => {
    api.get('/users/firm').then((res) => {
      const data = res.data as {
        id: string
        name: string
        settings?: Record<string, unknown> | null
      }
      const settings = data.settings ?? {}
      setFirmId(data.id)
      setFirmName(data.name)
      const savedDark = (settings.portal_colors_dark as Partial<ColorSet>) || {}
      const savedLight = (settings.portal_colors_light as Partial<ColorSet>) || {}
      setBranding({
        portal_display_name: (settings.portal_display_name as string) || data.name,
        portal_logo_s3_key: (settings.portal_logo_s3_key as string | null) || null,
        portal_mode: (settings.portal_mode as 'light' | 'dark') || 'dark',
        colors_dark: { ...DARK_DEFAULTS, ...savedDark },
        colors_light: { ...LIGHT_DEFAULTS, ...savedLight },
      })
      if (settings.portal_logo_s3_key) {
        setLogoPreviewUrl(`https://api.jammpx.com/firms/logo/${data.id}`)
      }
    }).finally(() => setLoading(false))
  }, [])

  async function processFile(file: File) {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error('Logo must be PNG, JPG, SVG, or WEBP')
      return
    }
    if (file.size > MAX_BYTES) {
      toast.error('Logo must be 2MB or smaller')
      return
    }
    setUploading(true)
    try {
      const { data } = await api.post('/firms/logo/upload-url', {
        file_name: file.name,
        file_type: file.type,
        file_size: file.size,
      })
      const { upload_url, s3_key } = data as { upload_url: string; s3_key: string }
      const putRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type },
      })
      if (!putRes.ok) throw new Error('S3 upload failed')
      await api.patch('/users/firm/settings', { portal_logo_s3_key: s3_key })
      setBranding((b) => ({ ...b, portal_logo_s3_key: s3_key }))
      setLogoPreviewUrl(`https://api.jammpx.com/firms/logo/${firmId}?t=${Date.now()}`)
      toast.success('Logo uploaded')
    } catch {
      toast.error('Logo upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      processFile(file)
      e.target.value = ''
    }
  }

  async function handleRemoveLogo() {
    setSaving(true)
    try {
      await api.patch('/users/firm/settings', { portal_logo_s3_key: '' })
      setBranding((b) => ({ ...b, portal_logo_s3_key: null }))
      setLogoPreviewUrl(null)
      toast.success('Logo removed')
    } catch {
      toast.error('Failed to remove logo')
    } finally {
      setSaving(false)
    }
  }

  async function handleSave() {
    const allColors = [...Object.values(branding.colors_dark), ...Object.values(branding.colors_light)]
    if (allColors.some(c => !VALID_HEX.test(c))) {
      toast.error('All colors must be valid hex values — e.g. #1F3148')
      return
    }
    setSaving(true)
    try {
      await api.patch('/users/firm/settings', {
        portal_display_name: branding.portal_display_name.trim() || firmName,
        portal_mode: branding.portal_mode,
        portal_colors_dark: branding.colors_dark,
        portal_colors_light: branding.colors_light,
      })
      toast.success('Portal branding saved')
      setSaveConfirmed(true)
      setTimeout(() => setSaveConfirmed(false), 3000)
    } catch {
      toast.error('Failed to save portal branding')
    } finally {
      setSaving(false)
    }
  }

  function setColor(mode: 'dark' | 'light', key: keyof ColorSet, value: string) {
    setBranding((b) => ({
      ...b,
      [`colors_${mode}`]: { ...b[`colors_${mode}`], [key]: value },
    }))
  }

  function resetColors(mode: 'dark' | 'light') {
    setBranding((b) => ({
      ...b,
      [`colors_${mode}`]: mode === 'dark' ? { ...DARK_DEFAULTS } : { ...LIGHT_DEFAULTS },
    }))
  }

  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
  const inputClass = 'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'
  const hintClass = 'text-[11px] text-[#6B7280] mt-1'

  function ColorSection({ mode }: { mode: 'dark' | 'light' }) {
    const colors = mode === 'dark' ? branding.colors_dark : branding.colors_light
    const isActive = branding.portal_mode === mode
    const previewPage = VALID_HEX.test(colors.page) ? colors.page : (mode === 'dark' ? '#2D2D2D' : '#E4E6EA')
    const previewTopBar = VALID_HEX.test(colors.top_bar) ? colors.top_bar : (mode === 'dark' ? '#1A2535' : '#1F3148')
    const previewTabBar = VALID_HEX.test(colors.tab_bar) ? colors.tab_bar : (mode === 'dark' ? '#252525' : '#EDEEF0')
    const previewAccent = VALID_HEX.test(colors.accent) ? colors.accent : (mode === 'dark' ? '#4A7FA5' : '#1F3148')
    const previewAvatar = VALID_HEX.test(colors.avatar) ? colors.avatar : (mode === 'dark' ? '#3A6A94' : '#1F3148')
    const primaryText = mode === 'light' ? '#1F3148' : '#EDEEF0'
    const mutedText = '#9CA3AF'
    const tabBorderColor = mode === 'light' ? '#C8CDD6' : '#383838'

    return (
      <div className={`flex flex-col gap-4 p-4 rounded-[8px] border ${isActive ? 'border-brand dark:border-brand-light' : 'border-surface-border dark:border-dark-border'}`}>
        {/* Section header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              {mode === 'dark' ? 'Dark mode' : 'Light mode'}
            </span>
            {isActive && (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
                Active
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => resetColors(mode)}
              className="text-[11px] text-[#6B7280] hover:text-brand-light"
            >
              Reset to defaults
            </button>
            {!isActive && (
              <button
                type="button"
                onClick={() => setBranding((b) => ({ ...b, portal_mode: mode }))}
                className="text-[11px] font-medium text-brand-light hover:underline"
              >
                Set as active
              </button>
            )}
          </div>
        </div>

        {/* Color pickers */}
        <div className="flex flex-col gap-2">
          {COLOR_LABELS.map(({ key, label }) => {
          const value = colors[key]
          return (
            <div key={key} className="flex items-center gap-3">
              <input
                type="color"
                value={VALID_HEX.test(value) ? value : '#1F3148'}
                onChange={(e) => setColor(mode, key, e.target.value)}
                className="w-8 h-8 rounded cursor-pointer border border-surface-border dark:border-dark-border p-0.5 flex-shrink-0"
              />
              <input
                type="text"
                defaultValue={value}
                key={`${mode}-${key}-${value}`}
                onBlur={(e) => {
                  const v = e.target.value.trim()
                  if (VALID_HEX.test(v)) setColor(mode, key, v)
                  else e.target.value = value
                }}
                maxLength={7}
                placeholder="#000000"
                className="w-28 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-[#EDEEF0] px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand"
              />
              <span className="text-[12px] text-[#6B7280]">{label}</span>
            </div>
          )
        })}
        </div>

        {/* Mini preview */}
        <div className="rounded-[6px] overflow-hidden border border-surface-border dark:border-dark-border">
          <div className="flex items-center justify-between px-3 h-9" style={{ backgroundColor: previewTopBar }}>
            <div className="flex items-center gap-1.5">
              {logoPreviewUrl ? (
                <img src={logoPreviewUrl} alt="" className="h-5 max-w-[80px] object-contain" onError={() => {}} />
              ) : (
                <span className="text-[11px] font-medium text-white">{branding.portal_display_name || firmName}</span>
              )}
              <span className="text-[9px]" style={{ color: VALID_HEX.test(colors.subtitle) ? colors.subtitle : '#7DA3C4' }}>Client Portal</span>
            </div>
            <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ backgroundColor: previewAvatar }}>
              <span className="text-[9px] font-medium text-white">JD</span>
            </div>
          </div>
          <div className="flex items-center px-2 h-7 border-b" style={{ backgroundColor: previewTabBar, borderColor: tabBorderColor }}>
            {['To-do', 'Documents', 'Invoices'].map((t, i) => (
              <span
                key={t}
                className="px-2 py-1 text-[10px]"
                style={{
                  color: i === 0 ? primaryText : mutedText,
                  borderBottom: i === 0 ? `2px solid ${previewAccent}` : '2px solid transparent',
                  fontWeight: i === 0 ? 500 : 400,
                }}
              >
                {t}
              </span>
            ))}
          </div>
          <div className="px-3 py-2" style={{ backgroundColor: previewPage }}>
            <div className="rounded-[4px] px-3 py-2" style={{ backgroundColor: VALID_HEX.test(colors.card) ? colors.card : (mode === 'dark' ? '#383838' : '#EDEEF0') }}>
              <span className="text-[10px]" style={{ color: mode === 'light' ? '#1F3148' : '#EDEEF0' }}>Card item</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6 max-w-2xl">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-9 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[6px]" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">

      {/* Setup status */}
      <div className="flex flex-col gap-2 p-3 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border">
        <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Setup status</span>
        <div className="flex flex-col gap-1.5">
          {[
            { done: branding.portal_display_name !== firmName && branding.portal_display_name.trim() !== '', label: 'Display name customized' },
            { done: !!branding.portal_logo_s3_key, label: 'Firm logo uploaded' },
            { done: JSON.stringify(branding.colors_dark) !== JSON.stringify(DARK_DEFAULTS) || JSON.stringify(branding.colors_light) !== JSON.stringify(LIGHT_DEFAULTS), label: 'Colors customized' },
          ].map(({ done, label }) => (
            <div key={label} className="flex items-center gap-2">
              <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${done ? 'bg-[#D1FAE5]' : 'bg-[#E5E7EB] dark:bg-[#333333]'}`}>
                {done ? (
                  <svg className="w-2.5 h-2.5 text-[#065F46]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-[#D1D5DB] dark:bg-[#555]" />
                )}
              </div>
              <span className={`text-[12px] ${done ? 'text-[#065F46] dark:text-[#34D399]' : 'text-[#6B7280]'}`}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Display Name */}
      <div className="flex flex-col gap-1.5">
        <label className={labelClass}>Firm name in portal</label>
        <input
          type="text"
          value={branding.portal_display_name}
          onChange={(e) => setBranding((b) => ({ ...b, portal_display_name: e.target.value }))}
          placeholder={firmName}
          maxLength={100}
          className={inputClass}
        />
        <p className={hintClass}>The name your clients see in the portal top bar. Defaults to your firm name.</p>
      </div>

      {/* Logo Upload */}
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Firm logo</span>
        <input
          id="logo-upload-input"
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
          onChange={handleInputChange}
          disabled={uploading}
          style={{ display: 'none' }}
        />
        <input
          id="logo-replace-input"
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
          onChange={handleInputChange}
          disabled={uploading}
          style={{ display: 'none' }}
        />
        {logoPreviewUrl ? (
          <div className="flex items-center gap-3 p-3 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page">
            <img
              src={logoPreviewUrl}
              alt="Firm logo"
              className="h-10 max-w-[160px] object-contain rounded"
              onError={() => setLogoPreviewUrl(null)}
            />
            <div className="flex-1" />
            <label htmlFor="logo-replace-input" className={`text-[12px] font-medium text-brand-light hover:underline cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
              Replace
            </label>
            <button type="button" onClick={handleRemoveLogo} disabled={saving || uploading} className="text-[12px] font-medium text-[#DC2626] hover:underline disabled:opacity-50 flex items-center gap-1">
              <X className="w-3 h-3" />
              Remove
            </button>
          </div>
        ) : (
          <label htmlFor="logo-upload-input" className={`flex flex-col items-center justify-center gap-2 h-24 rounded-[6px] border border-dashed border-surface-border dark:border-dark-border hover:border-brand-light dark:hover:border-brand-light transition-colors cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
            {uploading ? (
              <>
                <Loader2 className="w-5 h-5 text-[#6B7280] animate-spin" />
                <span className="text-[12px] text-[#6B7280]">Uploading…</span>
              </>
            ) : (
              <>
                <Upload className="w-5 h-5 text-[#6B7280]" />
                <span className="text-[12px] text-[#6B7280]">Click to upload logo</span>
                <span className="text-[11px] text-[#9CA3AF]">PNG, JPG, SVG, WEBP — max 2MB</span>
              </>
            )}
          </label>
        )}
        <p className={hintClass}>Displayed in the portal top bar instead of your firm name when set.</p>
      </div>

      {/* Color sections — dark and light side by side on wide, stacked on narrow */}
      <div className="flex flex-col gap-3">
        <span className={labelClass}>Portal colors</span>
        <p className={hintClass}>
          Configure colors for both modes. Use &ldquo;Set as active&rdquo; to choose which mode your clients see.
          To find your brand colors: right-click any element on your website → Inspect → look for a # value in the CSS panel.
        </p>
        <div className="flex flex-col gap-4">
          <ColorSection mode="dark" />
          <ColorSection mode="light" />
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || uploading}
          className="h-9 px-5 rounded-[6px] bg-brand text-white text-[13px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? 'Saving…' : 'Save branding'}
        </button>
        {saveConfirmed && (
          <span className="text-[11px] text-[#065F46] dark:text-[#34D399]">Changes are live in the client portal.</span>
        )}
      </div>

    </div>
  )
}
