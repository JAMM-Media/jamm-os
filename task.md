# STANDING RULES
- No schema changes — all branding data lives in firm.settings JSON blob
- No migrations
- The logo is stored in S3 at key `logos/{firm_id}/{uuid}.{ext}` using the existing private bucket
- Logo is served via a backend redirect endpoint (GET /firms/logo/{firm_id}) that generates a fresh presigned URL and returns a 302 redirect — this solves the presigned URL expiry problem without a public bucket
- All logo display uses this backend endpoint URL as the img src, not a direct S3 URL
- Image upload uses the existing presigned PUT pattern (request upload URL, browser PUTs directly to S3, frontend confirms key)
- All logo display must have graceful fallback to firm name text if no logo or load error
- Only accept PNG, JPG, JPEG, SVG, WEBP for logo uploads — reject others with a clear error
- Max logo file size: 2MB
- Color validation: reject non-#RRGGBB format with a toast error, never save invalid colors
- firm_owner only for all branding operations

# WHAT GETS BUILT
Six parts:
1. Backend: Logo upload URL endpoint + logo serve/redirect endpoint + portal/me branding fields
2. Frontend Settings: New PortalBrandingTab component with real file upload
3. Frontend Settings: Wire Portal tab into settings page
4. Frontend Portal: Extend PortalMe interface and pass branding to PortalShell
5. Frontend Portal: Update PortalShell to render logo and brand color
6. Frontend Portal Login: Clean up hardcoded "Your Firm" placeholder

---

# PART 1 — Backend

## 1A — Logo upload URL endpoint
FILE: app/api/firms.py

Add two new endpoints to the firms router. Add imports at the top of the file:
```python
import uuid as _uuid
from fastapi import File, UploadFile, Query
from fastapi.responses import RedirectResponse
from app.services import s3 as s3_service
```

**Endpoint 1: POST /firms/logo/upload-url**
Firm owner requests a presigned PUT URL to upload their logo directly from the browser to S3.

```python
LOGO_ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp"
}
LOGO_MAX_SIZE = 2 * 1024 * 1024  # 2MB

class LogoUploadUrlRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int

class LogoUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str


@router.post("/logo/upload-url", response_model=LogoUploadUrlResponse)
def get_logo_upload_url(
    body: LogoUploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    """
    Returns a presigned PUT URL so the browser can upload the logo directly to S3.
    The frontend PUTs the file to upload_url, then calls PATCH /users/firm/settings
    with portal_logo_s3_key set to s3_key.
    """
    if body.file_type not in LOGO_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Logo must be PNG, JPG, SVG, or WEBP"
        )
    if body.file_size > LOGO_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Logo must be 2MB or smaller"
        )

    ext = body.file_name.rsplit(".", 1)[-1].lower() if "." in body.file_name else "png"
    s3_key = f"logos/{current_user.firm_id}/{_uuid.uuid4()}.{ext}"
    upload_url = s3_service.generate_presigned_put_url(s3_key, body.file_type)

    return LogoUploadUrlResponse(upload_url=upload_url, s3_key=s3_key)
```

**Endpoint 2: GET /firms/logo/{firm_id}**
Anyone (including unauthenticated portal visitors) can hit this endpoint to load the firm's logo. It generates a fresh presigned GET URL and returns a 302 redirect. Because logos are loaded as img src, the browser follows the redirect transparently.

```python
@router.get("/logo/{firm_id}")
def get_firm_logo(
    firm_id: _uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — no auth required.
    Returns a 302 redirect to a fresh presigned S3 URL for the firm's logo.
    Returns 404 if the firm has no logo configured.
    Used as the img src for portal top bar and login page.
    """
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    settings = firm.settings or {}
    s3_key = settings.get("portal_logo_s3_key")
    if not s3_key:
        raise HTTPException(status_code=404, detail="No logo configured")

    presigned_url = s3_service.generate_presigned_url(s3_key)
    return RedirectResponse(url=presigned_url, status_code=302)
```

## 1B — Extend portal/me to return branding
FILE: app/api/portal.py

Find the `portal_me` function. Replace the return dict with:

```python
@router.get("/me")
def portal_me(
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Return identity info for the authenticated portal client."""
    firm = db.execute(select(Firm).where(Firm.id == current_client.firm_id)).scalar_one_or_none()
    settings = firm.settings or {} if firm else {}
    firm_id_str = str(current_client.firm_id)
    has_logo = bool(settings.get("portal_logo_s3_key"))
    return {
        "client_id": str(current_client.id),
        "client_name": current_client.name,
        "firm_name": firm.name if firm else "",
        "portal_display_name": settings.get("portal_display_name") or (firm.name if firm else ""),
        "portal_logo_url": f"/api/v1/firms/logo/{firm_id_str}" if has_logo else None,
        "portal_brand_color": settings.get("portal_brand_color") or "#1F3148",
    }
```

Note: portal_logo_url is the backend redirect endpoint path, not a direct S3 URL. The frontend prepends the API base URL when using it as an img src.

## 1C — Delete old logo when a new one is uploaded
FILE: app/api/users.py

Find the `update_my_firm_settings` function (PATCH /users/firm/settings).

After the merge of settings, before the `crud_firm.update_firm` call, add logic to delete the old S3 logo object when portal_logo_s3_key changes:

```python
    # If portal_logo_s3_key is being replaced, delete the old logo from S3
    old_logo_key = current_settings.get("portal_logo_s3_key")
    new_logo_key = payload.get("portal_logo_s3_key")
    if new_logo_key is not None and old_logo_key and old_logo_key != new_logo_key:
        try:
            s3_service.delete_object(old_logo_key)
        except Exception:
            pass  # Never fail a settings save because of S3 cleanup

    if new_logo_key == "":
        # Explicit empty string means remove logo — also delete from S3
        if old_logo_key:
            try:
                s3_service.delete_object(old_logo_key)
            except Exception:
                pass
```

Add `from app.services import s3 as s3_service` to the imports in users.py if not already present. Also add `from app.schemas.firm import FirmUpdate` if not already imported.

---

# PART 2 — Frontend: PortalBrandingTab component
FILE: frontend/src/components/settings/PortalBrandingTab.tsx (CREATE NEW FILE)

```tsx
// path: frontend/src/components/settings/PortalBrandingTab.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
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
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

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
      // Step 1: Get presigned PUT URL
      const { data } = await api.post('/firms/logo/upload-url', {
        file_name: file.name,
        file_type: file.type,
        file_size: file.size,
      })
      const { upload_url, s3_key } = data as { upload_url: string; s3_key: string }

      // Step 2: PUT file directly to S3
      const putRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type },
      })
      if (!putRes.ok) throw new Error('S3 upload failed')

      // Step 3: Save s3_key to firm settings immediately
      await api.patch('/users/firm/settings', { portal_logo_s3_key: s3_key })

      // Step 4: Update local state
      setBranding((b) => ({ ...b, portal_logo_s3_key: s3_key }))
      // Bust the preview cache with a timestamp
      setLogoPreviewUrl(`${API_BASE}/api/v1/firms/logo/${firmId}?t=${Date.now()}`)
      toast.success('Logo uploaded')
    } catch {
      toast.error('Logo upload failed. Please try again.')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
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
        <label className={labelClass}>Firm logo</label>

        {logoPreviewUrl ? (
          <div className="flex items-center gap-3 p-3 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page">
            <img
              src={logoPreviewUrl}
              alt="Firm logo"
              className="h-10 max-w-[160px] object-contain rounded"
              onError={() => setLogoPreviewUrl(null)}
            />
            <div className="flex-1" />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="text-[12px] font-medium text-brand-light hover:underline disabled:opacity-50"
            >
              Replace
            </button>
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
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex flex-col items-center justify-center gap-2 h-24 rounded-[6px] border border-dashed border-surface-border dark:border-dark-border hover:border-brand-light dark:hover:border-brand-light transition-colors disabled:opacity-50 cursor-pointer"
          >
            {uploading ? (
              <>
                <Loader2 className="w-5 h-5 text-[#6B7280] animate-spin" />
                <span className="text-[12px] text-[#6B7280]">Uploading…</span>
              </>
            ) : (
              <>
                <Upload className="w-5 h-5 text-[#6B7280]" />
                <span className="text-[12px] text-[#6B7280]">
                  Click to upload logo
                </span>
                <span className="text-[11px] text-[#9CA3AF]">
                  PNG, JPG, SVG, WEBP — max 2MB
                </span>
              </>
            )}
          </button>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
          onChange={handleFileSelect}
          className="hidden"
        />
        <p className={hintClass}>
          Displayed in the portal top bar instead of your firm name when set.
        </p>
      </div>

      {/* Brand Color */}
      <div className="flex flex-col gap-1.5">
        <label className={labelClass}>Portal top bar color</label>
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
          Color of the portal top bar your clients see. JAMM default is #1F3148.
        </p>
      </div>

      {/* Live preview */}
      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Preview</span>
        <div className="rounded-[8px] overflow-hidden border border-surface-border dark:border-dark-border">
          {/* Top bar */}
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
          {/* Simulated tab row */}
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
```

---

# PART 3 — Wire Portal tab into Settings page
FILE: frontend/src/app/settings/page.tsx

3A — Add import (with the other component imports):
```tsx
import PortalBrandingTab from '@/components/settings/PortalBrandingTab'
```

3B — Add tab to TABS array after fee_schedule:
```tsx
  { key: 'portal_branding', label: 'Portal' },
```

3C — Add visibility rule in the .filter() call:
```tsx
if (tab.key === 'portal_branding') return isFirmOwner
```

3D — Add content render alongside the other tab renders:
```tsx
{activeTab === 'portal_branding' && isFirmOwner && <PortalBrandingTab />}
```

---

# PART 4 — Extend PortalMe and pass branding to PortalShell
FILE: frontend/src/app/portal/page.tsx

4A — Update the PortalMe interface:
```tsx
interface PortalMe {
  client_id: string
  client_name: string
  firm_name: string
  portal_display_name: string
  portal_logo_url: string | null
  portal_brand_color: string
}
```

4B — Determine the logo img src. The portal_logo_url from the backend is a relative path like `/api/v1/firms/logo/{id}`. Construct the full URL:
```tsx
  const logoImgSrc = me.portal_logo_url
    ? `${process.env.NEXT_PUBLIC_API_URL ?? ''}${me.portal_logo_url}`
    : undefined
```

Add this line just before the return statement (after `const firstName = ...`).

4C — Update the PortalShell usage:
```tsx
    <PortalShell
      firmName={me.portal_display_name || me.firm_name}
      logoUrl={logoImgSrc}
      brandColor={me.portal_brand_color || '#1F3148'}
      clientName={me.client_name}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    >
```

---

# PART 5 — Update PortalShell
FILE: frontend/src/components/portal/PortalShell.tsx

5A — Add useState to the import:
```tsx
import { useState } from 'react'
```
Check if useState is already imported — only add if missing.

5B — Update the interface:
```tsx
interface PortalShellProps {
  firmName: string
  logoUrl?: string
  brandColor?: string
  clientName: string
  activeTab: string
  onTabChange: (tab: string) => void
  children: React.ReactNode
}
```

5C — Destructure new props and add logoError state:
```tsx
export function PortalShell({
  firmName,
  logoUrl,
  brandColor = '#1F3148',
  clientName,
  activeTab,
  onTabChange,
  children,
}: PortalShellProps) {
  const { unreadCount, markAsRead } = usePortalUnreadMessages()
  const [logoError, setLogoError] = useState(false)
```

5D — Update the top bar. Find the entire top bar div and replace it:

Find:
```tsx
      <div className="flex items-center justify-between px-5 h-12 bg-[#1F3148] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-white">
            {firmName}
          </span>
          <span className="text-[10px] text-[#7DA3C4]">
            Client Portal
          </span>
        </div>
```

Replace with:
```tsx
      <div
        className="flex items-center justify-between px-5 h-12 flex-shrink-0"
        style={{ backgroundColor: brandColor }}
      >
        <div className="flex items-center gap-2">
          {logoUrl && !logoError ? (
            <img
              src={logoUrl}
              alt={firmName}
              className="h-6 max-w-[120px] object-contain"
              onError={() => setLogoError(true)}
            />
          ) : (
            <span className="text-[12px] font-medium text-white">
              {firmName}
            </span>
          )}
          <span className="text-[10px] text-[#7DA3C4]">
            Client Portal
          </span>
        </div>
```

---

# PART 6 — Portal login page cleanup
FILE: frontend/src/app/portal/login/page.tsx

Find:
```tsx
          <span className="text-[12px] font-[500] text-white">Your Firm</span>
```

Replace with:
```tsx
          <span className="text-[12px] font-[500] text-white">Client Portal</span>
```

The login page intentionally shows no firm branding — the client is not authenticated yet so we cannot safely identify their firm from the URL.

---

# VERIFICATION CHECKLIST
After all changes confirm:
1. firms.py has no import errors — RedirectResponse, BaseModel, uuid imported correctly
2. The GET /firms/logo/{firm_id} endpoint requires no auth (no JWT dependency)
3. PortalBrandingTab handles uploading=true state correctly during S3 PUT
4. Logo upload saves s3_key immediately after PUT succeeds (not bundled with the Save button)
5. Remove logo sends portal_logo_s3_key: '' and clears the preview immediately
6. PortalShell has useState imported and logoError state properly scoped
7. The preview strip in PortalBrandingTab updates live as color changes
8. No presigned S3 URLs are stored in firm.settings — only the s3_key is stored
9. The backend logo redirect endpoint is the only thing that generates presigned GET URLs for logos

---

# PART 7 — Make setup as easy as possible

## 7A — Color extraction hint text
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

In the brand color section, update the hint text below the inputs to read:

```tsx
        <p className={hintClass}>
          Match your firm's website color exactly. To find it: open your website, right-click any colored element, and select Inspect. Look for a value starting with # in the CSS panel.
        </p>
```

## 7B — Add a "How to find your logo URL" helper that points to the upload button
The current design already uses file upload (not a URL field), so no change needed — the upload button is self-explanatory.

## 7C — Add a setup completion indicator
At the top of the PortalBrandingTab, above the Display Name field, add a setup checklist that shows the firm owner what's configured and what's missing:

```tsx
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
```

Place this block immediately after the `if (loading)` early return and before the Display Name field.

## 7D — Pre-populate display name from firm name on first load
This is already handled in the useEffect — portal_display_name defaults to firm.name if not set. No change needed.

## 7E — Inline save confirmation in the preview
After a successful save, briefly flash "Changes live in portal" text below the preview for 3 seconds. Add state for this:

```tsx
  const [saveConfirmed, setSaveConfirmed] = useState(false)
```

In the handleSave success path, after `toast.success(...)`:
```tsx
      setSaveConfirmed(true)
      setTimeout(() => setSaveConfirmed(false), 3000)
```

Below the preview div, add:
```tsx
        {saveConfirmed && (
          <p className="text-[11px] text-[#065F46] dark:text-[#34D399] mt-1">
            Changes are live in the client portal.
          </p>
        )}
```