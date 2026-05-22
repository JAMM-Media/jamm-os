# JAMM PX — Document Detail Page + Filename + File Size Fixes

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## TASK 1 — Backend: fix signed document filename and file size

**File to edit:** `app/api/esign.py`

In `store_signed_document`, find where the document is created:

```python
doc = crud_document.create_document(
    db=db,
    firm_id=uuid.UUID(firm_id),
    client_id=uuid.UUID(client_id),
    engagement_id=uuid.UUID(str(engagement_id)) if engagement_id else None,
    uploaded_by=None,
    filename=f"{provider_envelope_id}.pdf",
    s3_key=s3_key,
    content_type="application/pdf",
    size_bytes=len(pdf_bytes),
)
```

The filename is the raw Dropbox Sign ID. Replace the filename with something readable. To do this, fetch the engagement name from the database first:

```python
def store_signed_document(
    envelope_id: str,
    firm_id: str,
    client_id: str,
    engagement_id,
    provider_envelope_id: str,
    pdf_bytes: bytes,
) -> None:
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        from app.models.signature_envelope import SignatureEnvelope as _SE
        envelope = db.query(_SE).filter(_SE.id == envelope_id).first()
        if not envelope:
            return

        # Build a readable filename from the engagement name if available
        readable_name = "Engagement Letter"
        if engagement_id:
            from app.models.engagement import Engagement as _Eng
            eng = db.query(_Eng).filter(_Eng.id == engagement_id).first()
            if eng:
                # Sanitize: remove characters that are invalid in filenames
                import re
                safe_name = re.sub(r'[^\w\s\-]', '', eng.name).strip()
                readable_name = safe_name if safe_name else "Engagement Letter"

        filename = f"{readable_name} — Signed.pdf"
```

Replace the `filename=f"{provider_envelope_id}.pdf"` line in `crud_document.create_document` with `filename=filename`.

Keep the rest of the function exactly as it is.

---

## TASK 2 — Backend: fix file size in document response

**File to edit:** `app/schemas/document.py`

Check the `DocumentOut` schema — find the `size_bytes` or `file_size` field. The frontend reads `raw.file_size_kb` but the backend likely returns `size_bytes`. 

In `mapDocument` in `frontend/src/lib/api/documents.ts`:
```typescript
fileSizeKb: Number(raw.file_size_kb ?? raw.fileSizeKb ?? 0),
```

The backend returns `size_bytes` not `file_size_kb`. Update `mapDocument`:

**File to edit:** `frontend/src/lib/api/documents.ts`

Find:
```typescript
fileSizeKb: Number(raw.file_size_kb ?? raw.fileSizeKb ?? 0),
```

Replace with:
```typescript
fileSizeKb: raw.size_bytes
  ? Number(raw.size_bytes) / 1024
  : Number(raw.file_size_kb ?? raw.fileSizeKb ?? 0),
```

This converts `size_bytes` to KB for display.

---

## TASK 3 — Frontend: replace document detail page placeholder with proper metadata card

**File to edit:** `frontend/src/app/documents/[id]/page.tsx`

Find the placeholder section:
```tsx
<div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
  <p className="text-[12px] text-[#6B7280]">
    Document preview and version history coming in a future phase.
  </p>
</div>
```

Replace with a proper document metadata card:
```tsx
<div className="flex flex-col gap-3">
  {/* Document info card */}
  <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
    <div className="px-4 py-2.5 border-b border-[0.5px] border-surface-border dark:border-dark-border bg-[#EDEEF0] dark:bg-[#252525]">
      <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Document Details</p>
    </div>
    <div className="grid grid-cols-2 gap-0">
      {[
        { label: 'Client', value: doc.clientName || '—' },
        { label: 'Engagement', value: doc.engagementTitle || '—' },
        { label: 'File Type', value: doc.fileType || '—' },
        { label: 'File Size', value: doc.fileSizeKb > 0 ? `${doc.fileSizeKb.toFixed(0)} KB` : '—' },
        { label: 'Uploaded', value: doc.uploadedAt || '—' },
        { label: 'Uploaded By', value: doc.uploadedBy || 'System' },
      ].map((row, i) => (
        <div
          key={row.label}
          className={`px-4 py-3 flex flex-col gap-0.5 ${
            i < 4 ? 'border-b border-[0.5px] border-surface-border dark:border-dark-border' : ''
          }`}
        >
          <p className="text-[11px] text-[#6B7280]">{row.label}</p>
          <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{row.value}</p>
        </div>
      ))}
    </div>
  </div>

  {/* Download CTA */}
  <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4 flex items-center justify-between">
    <div>
      <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Download Document</p>
      <p className="text-[11px] text-[#6B7280] mt-0.5">Opens a secure link valid for 1 hour</p>
    </div>
    <button
      onClick={handleDownload}
      className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
    >
      Download
    </button>
  </div>
</div>
```

Also remove the duplicate Download button from the header — the one at the top right next to the filename. The download action is now in the card below.

Find and remove:
```tsx
<button
  onClick={handleDownload}
  className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex-shrink-0"
>
  Download
</button>
```

Run TypeScript check after all frontend changes.

---

## EXECUTION ORDER

1. Task 1 — app/api/esign.py (readable filename)
2. Task 2 — frontend/src/lib/api/documents.ts (file size)
3. Task 3 — frontend/src/app/documents/[id]/page.tsx (metadata card)

No migrations needed. Report every file modified.