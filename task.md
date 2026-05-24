# TASK — Fix logo upload: input inside label, no positioning

FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Read the file first.

Remove both off-screen hidden inputs entirely:
- The one with id="logo-upload-input"  
- The one with id="logo-replace-input"

Replace the entire logo upload section (the div with the "Firm logo" span through the hint paragraph) with this:

```tsx
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
            <label className={`text-[12px] font-medium text-brand-light hover:underline cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
              Replace
              <input
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
                onChange={handleInputChange}
                disabled={uploading}
                style={{ display: 'none' }}
              />
            </label>
            <button
              type="button"
              onClick={handleRemoveLogo}
              disabled={saving || uploading}
              className="text-[12px] font-medium text-[#DC2626] hover:underline disabled:opacity-50 flex items-center gap-1"
            >
              <X className="w-3 h-3" />
              Remove
            </button>
          </div>
        ) : (
          <label className={`flex flex-col items-center justify-center gap-2 h-24 rounded-[6px] border border-dashed border-surface-border dark:border-dark-border hover:border-brand-light dark:hover:border-brand-light transition-colors cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
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
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
              onChange={handleInputChange}
              disabled={uploading}
              style={{ display: 'none' }}
            />
          </label>
        )}

        <p className={hintClass}>Displayed in the portal top bar instead of your firm name when set.</p>
      </div>
```

The input is nested directly inside the label element. No ids, no htmlFor, no refs, no positioning. The browser connects them automatically because the input is a child of the label.

Also remove the now-unused id and htmlFor from the display name field - find:
```
        <label htmlFor="portal-display-name" className={labelClass}>Firm name in portal</label>
        <input
          id="portal-display-name"
```
Replace with:
```
        <label className={labelClass}>Firm name in portal</label>
        <input
```

No other changes.