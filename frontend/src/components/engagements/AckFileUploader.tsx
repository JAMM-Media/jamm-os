// frontend/src/components/engagements/AckFileUploader.tsx
'use client'

import { useState, useRef, DragEvent, ChangeEvent } from 'react'
import { Upload, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'
import api from '@/lib/api'

interface AckUploadResult {
  total_records: number
  matched: number
  acknowledged: number
  rejected: number
  unmatched: { confirmation_number: string; form_type: string; reason: string }[]
}

type UploadState = 'idle' | 'uploading' | 'success' | 'error'

export function AckFileUploader() {
  const [dragOver, setDragOver] = useState(false)
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [result, setResult] = useState<AckUploadResult | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function reset() {
    setUploadState('idle')
    setResult(null)
    setErrorMessage(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  function validateFile(file: File): string | null {
    if (!file.name.toLowerCase().endsWith('.ack')) {
      return 'File must have a .ack extension.'
    }
    return null
  }

  async function handleFile(file: File) {
    const validationError = validateFile(file)
    if (validationError) {
      setErrorMessage(validationError)
      setUploadState('error')
      return
    }

    setUploadState('uploading')
    setResult(null)
    setErrorMessage(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await api.post('/api/v1/ack-parser/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(response.data)
      setUploadState('success')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Upload failed. Please try again.'
      setErrorMessage(detail)
      setUploadState('error')
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const hasWarnings =
    result && (result.rejected > 0 || result.unmatched.length > 0)

  return (
    <div className="space-y-3">
      {uploadState === 'idle' || uploadState === 'uploading' ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={[
            'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors',
            dragOver
              ? 'border-[#1E40AF] bg-[#EFF6FF]'
              : 'border-[#93C5FD] bg-[#F8FAFC] hover:bg-[#EFF6FF]',
          ].join(' ')}
        >
          {uploadState === 'uploading' ? (
            <>
              <Loader2 className="h-7 w-7 text-[#1E40AF] animate-spin" />
              <p className="text-[13px] text-[#1E40AF] font-medium">Uploading...</p>
            </>
          ) : (
            <>
              <Upload className="h-7 w-7 text-[#3B82F6]" />
              <p className="text-[13px] text-[#374151] font-medium">
                Drop your .ack file here or{' '}
                <span className="text-[#1D4ED8] underline">browse</span>
              </p>
              <p className="text-[11px] text-[#9CA3AF]">.ack files only, max 512 KB</p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".ack"
            className="hidden"
            onChange={onFileChange}
          />
        </div>
      ) : null}

      {uploadState === 'success' && result && (
        <div className="rounded-lg border border-[#D1FAE5] bg-[#ECFDF5] p-4 space-y-3">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-[#059669] shrink-0" />
            <p className="text-[13px] font-semibold text-[#065F46]">
              File processed — {result.total_records} record{result.total_records !== 1 ? 's' : ''} found
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Matched" value={result.matched} color="text-[#065F46]" />
            <Stat label="Acknowledged" value={result.acknowledged} color="text-[#065F46]" />
            <Stat label="Rejected by IRS" value={result.rejected} color={result.rejected > 0 ? 'text-[#92400E]' : 'text-[#065F46]'} />
          </div>
          {hasWarnings && (
            <div className="rounded-md border border-[#FDE68A] bg-[#FFFBEB] p-3 space-y-2">
              <div className="flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4 text-[#B45309] shrink-0" />
                <p className="text-[12px] font-semibold text-[#92400E]">
                  {result.unmatched.length} unmatched
                  {result.rejected > 0 ? `, ${result.rejected} IRS rejection${result.rejected !== 1 ? 's' : ''}` : ''}
                </p>
              </div>
              {result.unmatched.length > 0 && (
                <ul className="space-y-0.5 pl-1">
                  {result.unmatched.map((u, i) => (
                    <li key={i} className="text-[11px] text-[#92400E]">
                      {u.confirmation_number} ({u.form_type}) — {formatReason(u.reason)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <button
            onClick={reset}
            className="text-[12px] text-[#1D4ED8] underline hover:text-[#1E40AF]"
          >
            Upload another file
          </button>
        </div>
      )}

      {uploadState === 'error' && (
        <div className="rounded-lg border border-[#FCA5A5] bg-[#FEF2F2] p-4 space-y-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-[#DC2626] shrink-0" />
            <p className="text-[13px] font-semibold text-[#991B1B]">Upload failed</p>
          </div>
          <p className="text-[12px] text-[#991B1B]">{errorMessage}</p>
          <button
            onClick={reset}
            className="text-[12px] text-[#1D4ED8] underline hover:text-[#1E40AF]"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">{label}</span>
      <span className={`text-[20px] font-semibold ${color}`}>{value}</span>
    </div>
  )
}

function formatReason(reason: string): string {
  if (reason === 'no_client_match') return 'no matching client'
  if (reason === 'no_efileable_engagement') return 'no efileable engagement'
  return reason.replace(/_/g, ' ')
}
