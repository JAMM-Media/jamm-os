// path: frontend/src/components/settings/PortalBrandingTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Upload, X, Loader2 } from 'lucide-react'
import api from '@/lib/api'

interface BrandingState {
  portal_display_name: string
  portal_logo_s3_key: string | null
  portal_brand_color: string
}

const VALID_HEX = /^#[0-9A-Fa-f]{6}$/
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp']
const MAX_BYTES = 2 * 1024 * 1024
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export default function PortalBrandingTab() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [firmId, setFirmId] = useState<string | null>(null)
  const [branding, setBranding] = useState<BrandingState>({
    portal_display_name: '',
    portal_logo_s3_key: null,
    portal_brand_color: '#1F3148',
  })
  const [firmName, setFirmName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null)
  const [saveConfirmed, setSaveConfirmed] = useState(false)

  useEffect(() => {
    api.get('/users/firm').then((res) => {
      const data = res.data as {
        id: string
        name: string
        settings?: Record<string, string | null> | null
      }
      const settings = data.settings ?? {}
      setFirmId(data.id)
      setFirmName(data.name)
      setBranding({
        portal_display_name: (settings.portal_display_name as string) || data.name,
        portal_logo_s3_key: (settings.portal_logo_s3_key as string | null) || null,
        portal_brand_color: (settings.portal_brand_color as string) || '#1F3148',
      })
      if (settings.portal_logo_s3_key) {
        setLogoPreviewUrl(`${API_BASE}/api/v1/firms/logo/${data.id}`)
      }
    }).finally(() => setLoading(false))
  }, [])

  async function handleFileChange(e: React.FormEvent<HTMLInputElement>) {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error('Logo must be PNG, JPG, SVG, or WEBP')
      (e.target as HTMLInputElement).value = ''
      return
    }
    if (file.size > MAX_BYTES) {
      toast.error('Logo must be 2MB or smaller')
      (e.target as HTMLInputElement).value = ''
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
      setLogoPreviewUrl(`${API_BASE}/api/v1/firms/logo/${firmId}?t=${Date.now()}`)
      toast.success('Logo uploaded')
    } catch {
      toast.error('Logo upload failed. Please try again.')
    } finally {
      setUploading(false)
      (e.target as HTMLInputElement).value = ''
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
    if (branding.portal_brand_color && !VALID_HEX.test(branding.portal_brand_color)) {
      toast.error('Brand color must be a valid hex color — e.g. #1F3148')
      return
    }
    setSaving(true)
    try {
      await api.patch('/users/firm/settings', {
        portal_display_name: branding.portal_display_name.trim() || firmName,
        portal_brand_color: branding.portal_brand_color.trim() || '#1F3148',
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

  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
  const inputClass =
    'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'
  const hintClass = 'text-[11px] text-[#6B7280] mt-1'
  const previewColor = VALID_HEX.test(branding.portal_brand_color)
    ? branding.portal_brand_color
    : '#1F3148'

  if (loading) {
    return (
      <div className="flex flex-col gap-6 max-w-lg">
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
    <div className="flex flex-col gap-6 max-w-lg">

      {/* Setup status */}
      <div className="flex flex-col gap-2 p-3 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border">
        <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Setup status</span>
        <div className="flex flex-col gap-1.5">
          {[
            {
              done: branding.portal_display_name !== firmName && branding.portal_display_name.trim() !== '',
              label: 'Display name customized',
            },
            {
              done: !!branding.portal_logo_s3_key,
              label: 'Firm logo uploaded',
            },
            {
              done: branding.portal_brand_color !== '#1F3148',
              label: 'Brand color set',
            },
          ].map(({ done, label }) => (
            <div key={label} className="flex items-center gap-2">
              <div
                className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${
                  done ? 'bg-[#D1FAE5]' : 'bg-[#E5E7EB] dark:bg-[#333333]'
                }`}
              >
                {done ? (
                  <svg className="w-2.5 h-2.5 text-[#065F46]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-[#D1D5DB] dark:bg-[#555]" />
                )}
              </div>
              <span className={`text-[12px] ${done ? 'text-[#065F46] dark:text-[#34D399]' : 'text-[#6B7280]'}`}>
                {label}
              </span>
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
        <p className={hintClass}>
          The name your clients see in the portal top bar. Defaults to your firm name.
        </p>
      </div>

      {/* Logo Upload */}
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Firm logo</span>

        {logoPreviewUrl ? (
          <div className="flex items-center gap-3 p-3 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page">
            <img
              src={logoPreviewUrl}
              alt="Firm logo"
              className="h-10 max-w-[160px] object-contain rounded"
              onError={() => setLogoPreviewUrl(null)}
            />
            <div className="flex-1" />
            <div className="relative">
              <span className={`text-[12px] font-medium text-brand-light hover:underline cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
                Replace
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
                onInput={handleFileChange}
                disabled={uploading}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
            </div>
            <button
              onClick={handleRemoveLogo}
              disabled={saving || uploading}
              className="text-[12px] font-medium text-[#DC2626] hover:underline disabled:opacity-50 flex items-center gap-1"
            >
              <X className="w-3 h-3" />
              Remove
            </button>
          </div>
        ) : (
          <div className="relative h-24 rounded-[6px] border border-dashed border-surface-border dark:border-dark-border hover:border-brand-light dark:hover:border-brand-light transition-colors">
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 pointer-events-none">
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
            </div>
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
              onInput={handleFileChange}
              disabled={uploading}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
          </div>
        )}

        <p className={hintClass}>
          Displayed in the portal top bar instead of your firm name when set.
        </p>
      </div>

      {/* Brand Color */}
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Portal top bar color</span>
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={VALID_HEX.test(branding.portal_brand_color) ? branding.portal_brand_color : '#1F3148'}
            onChange={(e) => setBranding((b) => ({ ...b, portal_brand_color: e.target.value }))}
            className="w-9 h-9 rounded cursor-pointer border border-surface-border dark:border-dark-border p-0.5"
          />
          <input
            type="text"
            value={branding.portal_brand_color}
            onChange={(e) => setBranding((b) => ({ ...b, portal_brand_color: e.target.value }))}
            placeholder="#1F3148"
            maxLength={7}
            className={`${inputClass} w-32`}
          />
          <span className="text-[11px] text-[#6B7280]">hex</span>
          <button
            onClick={() => setBranding((b) => ({ ...b, portal_brand_color: '#1F3148' }))}
            className="text-[11px] text-[#6B7280] hover:text-brand-light ml-1"
          >
            Reset to default
          </button>
        </div>
        <p className={hintClass}>
          Match your firm&apos;s website color exactly. To find it: open your website, right-click any colored element, and select Inspect. Look for a value starting with # in the CSS panel.
        </p>
      </div>

      {/* Live preview */}
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Preview</span>
        <div className="rounded-[8px] overflow-hidden border border-surface-border dark:border-dark-border">
          <div
            className="flex items-center justify-between px-4 h-11"
            style={{ backgroundColor: previewColor }}
          >
            <div className="flex items-center gap-2">
              {logoPreviewUrl ? (
                <img
                  src={logoPreviewUrl}
                  alt=""
                  className="h-6 max-w-[120px] object-contain"
                  onError={() => {}}
                />
              ) : (
                <span className="text-[12px] font-medium text-white">
                  {branding.portal_display_name || firmName}
                </span>
              )}
              <span className="text-[10px]" style={{ color: '#7DA3C4' }}>
                Client Portal
              </span>
            </div>
            <div className="w-6 h-6 rounded-full bg-[#3A6A94] flex items-center justify-center">
              <span className="text-[10px] font-medium text-white">JD</span>
            </div>
          </div>
          <div className="flex items-center gap-0 px-4 h-9 bg-[#252525] border-b border-[#383838]">
            {['To-do', 'Documents', 'Invoices'].map((t, i) => (
              <span
                key={t}
                className={`px-3 py-2 text-[12px] ${i === 0 ? 'text-[#EDEEF0] font-medium border-b-2 border-[#4A7FA5]' : 'text-[#9CA3AF]'}`}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
        {saveConfirmed && (
          <p className="text-[11px] text-[#065F46] dark:text-[#34D399] mt-1">
            Changes are live in the client portal.
          </p>
        )}
      </div>

      {/* Save */}
      <div>
        <button
          onClick={handleSave}
          disabled={saving || uploading}
          className="h-9 px-5 rounded-[6px] bg-brand text-white text-[13px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? 'Saving…' : 'Save branding'}
        </button>
      </div>

    </div>
  )
}
