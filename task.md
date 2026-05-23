# TASK — Fix logo upload in PortalBrandingTab

The current approach uses a hidden file input triggered by a ref click. This is not firing onChange reliably. Replace the entire upload zone with a label-wrapping approach — no ref, no programmatic click, just a <label> wrapping a hidden <input type="file">. This is the most reliable cross-browser pattern.

## FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Read the full file first.

### Step 1 — Remove useRef from imports

Change:
```
import { useState, useEffect, useRef } from 'react'
```
To:
```
import { useState, useEffect } from 'react'
```

### Step 2 — Remove the fileInputRef declaration

Find and delete this line:
```
  const fileInputRef = useRef<HTMLInputElement>(null)
```

### Step 3 — Replace the entire logo upload section

Find the entire div with label "Firm logo" — from the opening `<div className="flex flex-col gap-1.5">` that contains the logo upload zone, down through the hidden input and the hint paragraph. Replace the entire section with:

```tsx
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
            <label
              className={`text-[12px] font-medium text-brand-light hover:underline cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
            >
              Replace
              <input
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </label>
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
          <label
            className={`flex flex-col items-center justify-center gap-2 h-24 rounded-[6px] border border-dashed border-surface-border dark:border-dark-border hover:border-brand-light dark:hover:border-brand-light transition-colors cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
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
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </label>
        )}

        <p className={hintClass}>
          Displayed in the portal top bar instead of your firm name when set.
        </p>
      </div>
```

### Step 4 — Remove any remaining fileInputRef references

Search the entire file for fileInputRef and delete any remaining lines. There should be none after the above steps.

### Step 5 — Do not modify handleFileSelect

The handleFileSelect function is correct as-is. Do not touch it.

## VERIFICATION
- No useRef import remains
- No fileInputRef variable remains  
- Upload zone is a <label> element with a nested hidden <input type="file">
- Replace button when logo exists is also a <label> with nested input
- handleFileSelect unchanged