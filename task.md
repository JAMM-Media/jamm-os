# JAMM PX — E-Signature Phase 2: Upload Your Own Document

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0, Pydantic v2. Never deviate from existing patterns.
- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Backend: new endpoint to upload PDF and create envelope in one step

**File to edit:** `app/api/esign.py`

Add a new endpoint after the existing `/prepare` endpoint:

```python
# -----------------------------------------------------------------------
# POST /esign/upload-and-prepare — Upload a PDF and create a draft envelope
# -----------------------------------------------------------------------
@router.post(
    "/upload-and-prepare",
    response_model=SignatureEnvelopeOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_and_prepare(
    engagement_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_staff_or_above),
):
    """
    Accepts a PDF upload, stores it in S3, creates a document record,
    then creates a draft signature envelope linked to that document.
    The envelope has the client pre-populated as the signer.
    The caller then calls POST /esign/envelopes/{id}/send to send it.
    """
    # Validate file type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Get the engagement and client
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == engagement_id,
            Engagement.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    client = db.execute(
        select(Client).where(
            Client.id == engagement.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Read file bytes and upload to S3
    import uuid as _uuid
    pdf_bytes = file.file.read()
    s3_key = (
        f"{current_firm.id}/letters/{engagement_id}"
        f"/{file.filename or 'engagement_letter'}_{date.today()}_{_uuid.uuid4().hex[:8]}.pdf"
    )
    s3_service.upload_fileobj(
        io.BytesIO(pdf_bytes),
        s3_key,
        file.content_type or "application/pdf",
    )

    # Create document record
    doc = crud_document.create_document(
        db=db,
        firm_id=current_firm.id,
        client_id=client.id,
        engagement_id=engagement_id,
        uploaded_by=current_user.id,
        filename=file.filename or "engagement_letter.pdf",
        s3_key=s3_key,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )

    # Create draft envelope with client as signer
    envelope_schema = SignatureEnvelopeCreate(
        client_id=client.id,
        engagement_id=engagement_id,
        document_id=doc.id,
        subject=file.filename or "Engagement Letter",
        signers=[{
            "name": getattr(client, "full_name", None) or client.name,
            "email": client.email or "",
            "status": "pending",
            "signed_at": None,
        }],
    )
    envelope = crud_envelope.create_signature_envelope(db, envelope_schema, firm_id=current_firm.id)

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="esign.document_uploaded",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )

    return envelope
```

Check the existing imports at the top of `esign.py` — `UploadFile`, `File`, `Query`, `io`, `select`, `Engagement`, `Client`, `crud_document` should already be imported. Add only what is missing.

---

## TASK 2 — Frontend: extend SendEngagementLetterModal with upload path

**File to edit:** `frontend/src/components/engagements/SendEngagementLetterModal.tsx`

Extend the modal to support two sending paths: template-based (existing) and upload your own PDF (new). Add a toggle at the top of the modal to switch between paths.

### Step 1 — Add mode state

Add at the top of the component alongside existing state:
```tsx
const [mode, setMode] = useState<'template' | 'upload'>('template')
const [uploadFile, setUploadFile] = useState<File | null>(null)
const [uploadSubject, setUploadSubject] = useState('')
const [dragOver, setDragOver] = useState(false)
```

Also add to `handleClose`:
```tsx
setMode('template')
setUploadFile(null)
setUploadSubject('')
setDragOver(false)
```

### Step 2 — Update handleSend to handle both paths

Replace the existing `handleSend` function with:

```tsx
async function handleSend() {
  if (mode === 'template') {
    const errs: typeof errors = {}
    if (!selectedTemplateId) errs.template = 'Please select a template.'
    if (!feeAmount.trim()) errs.fee = 'Please enter the fee amount.'
    if (Object.keys(errs).length > 0) { setErrors(errs); return }

    setLoading(true)
    try {
      const prepareRes = await api.post('/esign/prepare', {
        template_id: selectedTemplateId,
        engagement_id: engagementId,
        fee_amount: feeAmount.trim(),
      })
      const envelopeId = prepareRes.data?.id
      if (!envelopeId) throw new Error('No envelope ID returned')
      await api.post(`/esign/envelopes/${envelopeId}/send`)
      toast.success('Engagement letter sent for signature')
      onSent()
      handleClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send engagement letter'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  } else {
    // Upload path
    const errs: typeof errors = {}
    if (!uploadFile) errs.template = 'Please select a PDF file.'
    if (Object.keys(errs).length > 0) { setErrors(errs); return }

    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile!)

      const uploadRes = await api.post(
        `/esign/upload-and-prepare?engagement_id=${engagementId}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      const envelopeId = uploadRes.data?.id
      if (!envelopeId) throw new Error('No envelope ID returned')
      await api.post(`/esign/envelopes/${envelopeId}/send`)
      toast.success('Engagement letter sent for signature')
      onSent()
      handleClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send engagement letter'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }
}
```

### Step 3 — Update the JSX

Add a mode toggle at the top of the modal body, before the auto-populated preview section:

```tsx
{/* Mode toggle */}
<div className="flex rounded-[6px] border border-surface-border dark:border-dark-border overflow-hidden">
  <button
    onClick={() => { setMode('template'); setErrors({}) }}
    className={`flex-1 py-2 text-[12px] font-medium transition-colors ${
      mode === 'template'
        ? 'bg-brand dark:bg-brand-btn text-white'
        : 'bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand'
    }`}
  >
    Use a Template
  </button>
  <button
    onClick={() => { setMode('upload'); setErrors({}) }}
    className={`flex-1 py-2 text-[12px] font-medium transition-colors ${
      mode === 'upload'
        ? 'bg-brand dark:bg-brand-btn text-white'
        : 'bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand'
    }`}
  >
    Upload Your Own PDF
  </button>
</div>
```

Then wrap the existing template content (auto-populated preview + template select + fee amount) in `{mode === 'template' && (...)}`.

After that block, add the upload path content:

```tsx
{mode === 'upload' && (
  <div className="flex flex-col gap-4">
    {/* Auto-populated preview — same as template path */}
    <div className="bg-surface-page dark:bg-[#252525] rounded-[6px] p-3 flex flex-col gap-2">
      <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Auto-populated from engagement</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        <div>
          <p className="text-[11px] text-[#6B7280]">Client</p>
          <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{clientName || '—'}</p>
        </div>
        <div>
          <p className="text-[11px] text-[#6B7280]">Engagement</p>
          <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{engagementName || '—'}</p>
        </div>
      </div>
    </div>

    {/* File upload area */}
    <FormField label="Engagement Letter PDF" required error={errors.template}>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          const file = e.dataTransfer.files[0]
          if (file?.type === 'application/pdf') {
            setUploadFile(file)
            if (errors.template) setErrors((prev) => ({ ...prev, template: undefined }))
          } else {
            toast.error('Please upload a PDF file')
          }
        }}
        className={`relative flex flex-col items-center justify-center gap-2 p-6 rounded-[6px] border border-dashed transition-colors cursor-pointer ${
          dragOver
            ? 'border-brand bg-surface-card dark:bg-dark-card'
            : errors.template
            ? 'border-red-400 bg-surface-page dark:bg-[#252525]'
            : 'border-surface-border dark:border-dark-border bg-surface-page dark:bg-[#252525] hover:border-brand'
        }`}
        onClick={() => document.getElementById('esign-pdf-upload')?.click()}
      >
        <input
          id="esign-pdf-upload"
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              setUploadFile(file)
              if (errors.template) setErrors((prev) => ({ ...prev, template: undefined }))
            }
          }}
        />
        {uploadFile ? (
          <>
            <div className="w-8 h-8 rounded-[6px] bg-status-green flex items-center justify-center">
              <svg width="16" height="16" fill="none" stroke="#065F46" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{uploadFile.name}</p>
            <p className="text-[11px] text-[#6B7280]">{(uploadFile.size / 1024).toFixed(0)} KB · Click to replace</p>
          </>
        ) : (
          <>
            <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" className="text-[#6B7280]">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">Drop your PDF here or click to browse</p>
            <p className="text-[11px] text-[#6B7280]">PDF files only</p>
          </>
        )}
      </div>
    </FormField>

    <p className="text-[11px] text-[#6B7280]">
      The client will receive an email from Dropbox Sign with a link to review and sign the document. You will be notified when they sign.
    </p>
  </div>
)}
```

Also update the bottom disclaimer text that currently shows for both modes — move it inside the `mode === 'template'` block so it doesn't duplicate.

---

## EXECUTION ORDER

1. Task 1 — backend: app/api/esign.py (new upload-and-prepare endpoint)
2. Task 2 — frontend: SendEngagementLetterModal.tsx (add upload mode)

After all tasks: report every file modified and confirm no TypeScript errors.