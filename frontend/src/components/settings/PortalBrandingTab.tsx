// path: frontend/src/components/settings/PortalBrandingTab.tsx
'use client'

import { useState, useEffect, useRef, MutableRefObject, Dispatch, SetStateAction } from 'react'
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

function wcagLinearize(c: number): number {
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}
function wcagLuminance(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  return 0.2126 * wcagLinearize(r) + 0.7152 * wcagLinearize(g) + 0.0722 * wcagLinearize(b)
}
function wcagContrast(hex1: string, hex2: string): number {
  const l1 = wcagLuminance(hex1)
  const l2 = wcagLuminance(hex2)
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
}
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp']
const MAX_BYTES = 2 * 1024 * 1024

const COLOR_LABELS = [
  { key: 'top_bar', label: 'Top bar' },
  { key: 'page', label: 'Page background' },
  { key: 'tab_bar', label: 'Tab bar' },
  { key: 'accent', label: 'Accent' },
  { key: 'avatar', label: 'Client avatar' },
  { key: 'subtitle', label: 'Subtitle' },
  { key: 'card', label: 'Card background' },
  { key: 'text_primary', label: 'Primary text' },
  { key: 'text_muted', label: 'Secondary text' },
] as const


// ColorSection: color editor only (2-column grid), no preview, no reset button.
// Preview and reset live in PortalPreviewPanel (right-hand panel).
interface ColorSectionProps {
  mode: 'dark' | 'light'
  colors: ColorSet
  invalidFields: Set<string>
  textRefs: MutableRefObject<Record<string, HTMLInputElement | null>>
  onSetColor: (mode: 'dark' | 'light', key: keyof ColorSet, value: string) => void
  onSetInvalidFields: Dispatch<SetStateAction<Set<string>>>
}

function ColorSection({
  mode,
  colors,
  invalidFields,
  textRefs,
  onSetColor,
  onSetInvalidFields,
}: ColorSectionProps) {
  return (
    <div className="flex flex-col gap-3">
      {/* Color pickers in 2-column grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        {COLOR_LABELS.map(({ key, label }) => {
        const value = colors[key]
        return (
          <div key={key} className="flex items-center gap-2 min-w-0">
            <input
              type="color"
              value={VALID_HEX.test(value) ? value : '#1F3148'}
              onChange={(e) => {
                onSetColor(mode, key, e.target.value)
                const ref = textRefs.current[`${mode}-${key}`]
                if (ref) ref.value = e.target.value
              }}
              className="w-7 h-7 rounded cursor-pointer border border-surface-border dark:border-dark-border p-0.5 flex-shrink-0"
            />
            <input
              type="text"
              defaultValue={value}
              key={`${mode}-${key}`}
              onChange={(e) => {
                const v = e.target.value.trim()
                const fid = `${mode}-${key}`
                if (v.length > 0 && !VALID_HEX.test(v)) {
                  onSetInvalidFields((s) => new Set([...s, fid]))
                } else {
                  onSetInvalidFields((s) => { const n = new Set(s); n.delete(fid); return n })
                }
              }}
              onBlur={(e) => {
                const v = e.target.value.trim()
                const fid = `${mode}-${key}`
                if (VALID_HEX.test(v)) {
                  onSetColor(mode, key, v)
                } else {
                  e.target.value = value
                }
                onSetInvalidFields((s) => { const n = new Set(s); n.delete(fid); return n })
              }}
              ref={(el) => { textRefs.current[`${mode}-${key}`] = el }}
              maxLength={7}
              placeholder="#000000"
              className={`w-24 rounded-[5px] border ${invalidFields.has(`${mode}-${key}`) ? 'border-red-400 ring-1 ring-red-400' : 'border-surface-border dark:border-dark-border'} bg-surface-page dark:bg-dark-page text-[11px] text-brand dark:text-[#EDEEF0] px-2 py-1 focus:outline-none flex-shrink-0`}
            />
            <span className="text-[11px] text-[#6B7280] truncate min-w-0">{label}</span>
          </div>
        )
      })}
      </div>

      {/* Contrast warnings for real background/foreground pairs */}
      {(() => {
        type CP = { bg: keyof ColorSet; fg: keyof ColorSet; label: string }
        const pairs: CP[] = [
          { bg: 'page', fg: 'text_primary', label: 'Page / Primary text' },
          { bg: 'page', fg: 'text_muted', label: 'Page / Secondary text' },
          { bg: 'card', fg: 'text_primary', label: 'Card / Primary text' },
          { bg: 'card', fg: 'text_muted', label: 'Card / Secondary text' },
          { bg: 'top_bar', fg: 'subtitle', label: 'Top bar / Subtitle' },
        ]
        const warnings = pairs
          .filter(({ bg, fg }) => VALID_HEX.test(colors[bg]) && VALID_HEX.test(colors[fg]))
          .map(({ bg, fg, label }) => ({ label, ratio: wcagContrast(colors[bg], colors[fg]) }))
          .filter(({ ratio }) => ratio < 4.5)
        if (!warnings.length) return null
        return (
          <div className="flex flex-col gap-1 p-3 rounded-[6px] bg-[#FEF3C7] border border-[#FDE68A]">
            <p className="text-[11px] font-semibold text-[#92400E]">Contrast warnings (below 4.5:1 recommended)</p>
            {warnings.map(({ label, ratio }) => (
              <p key={label} className="text-[11px] text-[#92400E]">
                {label}: {ratio.toFixed(2)}:1
              </p>
            ))}
            <p className="text-[10px] text-[#B45309] mt-0.5">These combinations may be hard to read. You can still save.</p>
          </div>
        )
      })()}
    </div>
  )
}


// PortalPreviewPanel: live portal color preview (mini swatch) with reset and open-preview button.
interface PortalPreviewPanelProps {
  colors: ColorSet
  mode: 'dark' | 'light'
  logoPreviewUrl: string | null
  portalDisplayName: string
  firmName: string
  onReset: () => void
}

function PortalPreviewPanel({
  colors,
  mode,
  logoPreviewUrl,
  portalDisplayName,
  firmName,
  onReset,
}: PortalPreviewPanelProps) {
  const [previewLoading, setPreviewLoading] = useState(false)
  const previewPage = VALID_HEX.test(colors.page) ? colors.page : (mode === 'dark' ? '#2D2D2D' : '#E4E6EA')
  const previewTopBar = VALID_HEX.test(colors.top_bar) ? colors.top_bar : (mode === 'dark' ? '#1A2535' : '#1F3148')
  const previewAccent = VALID_HEX.test(colors.accent) ? colors.accent : (mode === 'dark' ? '#4A7FA5' : '#1F3148')

  return (
    <div className="flex flex-col gap-3">
      {/* Panel header */}
      <div className="flex flex-col gap-1">
        <span className="text-[12px] font-semibold text-brand dark:text-[#EDEEF0]">Live portal preview</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReset}
            className="text-[11px] text-[#6B7280] hover:text-brand-light transition-colors"
          >
            Reset to defaults
          </button>
          <button
            type="button"
            disabled={previewLoading}
            onClick={async () => {
              setPreviewLoading(true)
              try {
                const { data } = await api.post('/portal-preview/token')
                const { preview_token } = data as { preview_token: string }
                window.open(`/portal-preview?token=${encodeURIComponent(preview_token)}`, '_blank', 'noreferrer')
              } catch (err: unknown) {
                const status = (err as { response?: { status?: number } })?.response?.status
                if (status === 404) {
                  toast.error('No portal-enabled clients found. Enable portal access for at least one client first.')
                } else {
                  toast.error('Could not generate preview. Please try again.')
                }
              } finally {
                setPreviewLoading(false)
              }
            }}
            className="h-6 px-2 text-[11px] font-medium rounded-[4px] border border-surface-border dark:border-dark-border text-brand dark:text-[#EDEEF0] hover:bg-surface-card dark:hover:bg-dark-card transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {previewLoading ? 'Opening…' : 'Open preview'}
          </button>
        </div>
      </div>

      {/* Mini portal preview -- simple color swatch: top bar + accent against page background */}
      <div className="rounded-[6px] overflow-hidden border border-surface-border dark:border-dark-border">
        {/* Top bar strip */}
        <div className="flex items-center gap-2 px-3 h-10" style={{ backgroundColor: previewTopBar }}>
          {logoPreviewUrl ? (
            <img src={logoPreviewUrl} alt="" className="h-5 max-w-[100px] object-contain" onError={() => {}} />
          ) : (
            <span className="text-[12px] font-semibold text-white">{portalDisplayName || firmName}</span>
          )}
          <span className="text-[10px]" style={{ color: VALID_HEX.test(colors.subtitle) ? colors.subtitle : '#7DA3C4' }}>Client Portal</span>
        </div>
        {/* Content area with accent sample */}
        <div className="px-4 py-4" style={{ backgroundColor: previewPage }}>
          <span
            className="inline-block text-[12px] font-medium px-3 py-1.5 rounded-md text-white"
            style={{ backgroundColor: previewAccent }}
          >
            View documents
          </span>
        </div>
      </div>
    </div>
  )
}


export default function PortalBrandingTab() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [firmId, setFirmId] = useState<string | null>(null)
  const [firmName, setFirmName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null)
  const [saveConfirmed, setSaveConfirmed] = useState(false)
  const [invalidFields, setInvalidFields] = useState<Set<string>>(new Set())
  const textRefs = useRef<Record<string, HTMLInputElement | null>>({})
  const [activeModeTab, setActiveModeTab] = useState<'dark' | 'light'>('dark')
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
      const mode = (settings.portal_mode as 'light' | 'dark') || 'dark'
      setBranding({
        portal_display_name: (settings.portal_display_name as string) || data.name,
        portal_logo_s3_key: (settings.portal_logo_s3_key as string | null) || null,
        portal_mode: mode,
        colors_dark: { ...DARK_DEFAULTS, ...savedDark },
        colors_light: { ...LIGHT_DEFAULTS, ...savedLight },
      })
      setActiveModeTab(mode)
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
    const defaults = mode === 'dark' ? DARK_DEFAULTS : LIGHT_DEFAULTS
    setBranding((b) => ({
      ...b,
      [`colors_${mode}`]: { ...defaults },
    }))
    for (const { key } of COLOR_LABELS) {
      const ref = textRefs.current[`${mode}-${key}`]
      if (ref) ref.value = defaults[key as keyof ColorSet]
    }
  }

  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
  const inputClass = 'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'
  const hintClass = 'text-[11px] text-[#6B7280] mt-1'

  const activeColors = activeModeTab === 'dark' ? branding.colors_dark : branding.colors_light
  const isTabActive = activeModeTab === branding.portal_mode

  if (loading) {
    return (
      <div className="flex gap-6 items-start">
        <div className="flex flex-col gap-5 flex-1 min-w-0">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              <div className="h-9 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[6px]" />
            </div>
          ))}
        </div>
        <div className="w-80 flex-shrink-0 h-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
      </div>
    )
  }

  return (
    <div className="flex gap-6 items-start">

      {/* Left: main editor */}
      <div className="flex flex-col gap-5 flex-1 min-w-0">

        {/* Setup status -- horizontal row of badges */}
        <div className="flex items-center gap-4 p-3 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border flex-wrap">
          <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] flex-shrink-0">Setup status</span>
          {[
            { done: branding.portal_display_name !== firmName && branding.portal_display_name.trim() !== '', label: 'Display name customized' },
            { done: !!branding.portal_logo_s3_key, label: 'Firm logo uploaded' },
            { done: JSON.stringify(branding.colors_dark) !== JSON.stringify(DARK_DEFAULTS) || JSON.stringify(branding.colors_light) !== JSON.stringify(LIGHT_DEFAULTS), label: 'Colors customized' },
          ].map(({ done, label }) => (
            <div key={label} className="flex items-center gap-1.5">
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

        {/* Firm name + Logo -- side by side */}
        <div className="grid grid-cols-2 gap-4">
          {/* Firm name card */}
          <div className="flex flex-col gap-1.5 p-4 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border">
            <label className={labelClass}>Firm name in portal</label>
            <input
              type="text"
              value={branding.portal_display_name}
              onChange={(e) => setBranding((b) => ({ ...b, portal_display_name: e.target.value }))}
              placeholder={firmName}
              maxLength={100}
              className={inputClass}
            />
            <p className={hintClass}>Shown in the portal top bar. Defaults to your firm name.</p>
          </div>

          {/* Firm logo card */}
          <div className="flex flex-col gap-1.5 p-4 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border">
            <span className={labelClass}>Firm logo</span>
            <input id="logo-upload-input" type="file" accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp" onChange={handleInputChange} disabled={uploading} style={{ display: 'none' }} />
            <input id="logo-replace-input" type="file" accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp" onChange={handleInputChange} disabled={uploading} style={{ display: 'none' }} />
            {logoPreviewUrl ? (
              <div className="flex items-center gap-3 p-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page">
                <img src={logoPreviewUrl} alt="Firm logo" className="h-8 max-w-[120px] object-contain rounded" onError={() => setLogoPreviewUrl(null)} />
                <div className="flex-1" />
                <label htmlFor="logo-replace-input" className={`text-[12px] font-medium text-brand-light hover:underline cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>Replace</label>
                <button type="button" onClick={handleRemoveLogo} disabled={saving || uploading} className="text-[12px] font-medium text-[#DC2626] hover:underline disabled:opacity-50 flex items-center gap-1">
                  <X className="w-3 h-3" />Remove
                </button>
              </div>
            ) : (
              <label htmlFor="logo-upload-input" className={`flex flex-col items-center justify-center gap-1.5 h-20 rounded-[6px] border border-dashed border-surface-border dark:border-dark-border hover:border-brand-light transition-colors cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
                {uploading ? (
                  <><Loader2 className="w-4 h-4 text-[#6B7280] animate-spin" /><span className="text-[12px] text-[#6B7280]">Uploading...</span></>
                ) : (
                  <><Upload className="w-4 h-4 text-[#6B7280]" /><span className="text-[12px] text-[#6B7280]">Click to upload logo</span><span className="text-[11px] text-[#9CA3AF]">PNG, JPG, SVG, WEBP</span></>
                )}
              </label>
            )}
            <p className={hintClass}>Shown instead of firm name when set.</p>
          </div>
        </div>

        {/* Portal branding card */}
        <div className="flex flex-col gap-4 p-4 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border">
          <div>
            <span className={labelClass}>Portal branding</span>
            <p className={hintClass}>Configure colors for dark and light modes. Use the mode tabs to switch between them.</p>
          </div>

          {/* Tab switcher + active mode indicator */}
          <div className="flex items-center gap-3">
            <div className="flex rounded-[6px] border border-surface-border dark:border-dark-border overflow-hidden">
              {(['dark', 'light'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setActiveModeTab(m)}
                  className={`h-8 px-4 text-[12px] font-medium transition-colors ${
                    activeModeTab === m
                      ? 'bg-brand text-white'
                      : 'bg-surface-page dark:bg-dark-page text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0]'
                  }`}
                >
                  {m === 'dark' ? 'Dark mode' : 'Light mode'}
                </button>
              ))}
            </div>
            {isTabActive ? (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
                Active mode
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setBranding((b) => ({ ...b, portal_mode: activeModeTab }))}
                className="text-[11px] font-medium text-brand-light hover:underline"
              >
                Set as active
              </button>
            )}
          </div>

          {/* Color editor for the currently selected mode tab */}
          <ColorSection
            mode={activeModeTab}
            colors={activeColors}
            invalidFields={invalidFields}
            textRefs={textRefs}
            onSetColor={setColor}
            onSetInvalidFields={setInvalidFields}
          />
        </div>

        {/* Save */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || uploading}
            className="h-9 px-5 rounded-[6px] bg-brand text-white text-[13px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {saving ? 'Saving...' : 'Save changes'}
          </button>
          {saveConfirmed && (
            <span className="text-[11px] text-[#065F46] dark:text-[#34D399]">Changes are live in the client portal.</span>
          )}
        </div>

      </div>

      {/* Right: live portal preview panel */}
      <div className="w-80 flex-shrink-0 sticky top-6 flex flex-col gap-3 p-4 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border">
        <PortalPreviewPanel
          colors={activeColors}
          mode={activeModeTab}
          logoPreviewUrl={logoPreviewUrl}
          portalDisplayName={branding.portal_display_name}
          firmName={firmName}
          onReset={() => resetColors(activeModeTab)}
        />
      </div>

    </div>
  )
}
