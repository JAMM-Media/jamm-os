// frontend/src/components/settings/MigrationTab.tsx
'use client'

import { useState, useRef, DragEvent, ChangeEvent } from 'react'
import { Upload, CheckCircle, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type RowStatus = 'import' | 'skip' | 'warning'

interface ClientPreviewRow {
  row_number: number
  name: string
  email: string | null
  phone: string | null
  entity_type: string | null
  tags: string | null
  state: string | null
  status: RowStatus
  reason: string | null
}

interface ClientPreviewResult {
  total_rows: number
  will_import: number
  will_skip: number
  warnings: number
  rows: ClientPreviewRow[]
}

interface ClientImportResult {
  created: number
  skipped: number
  warnings: number
  errors: { row: number; reason: string }[]
}

interface JobPreviewRow {
  row_number: number
  job_name: string
  client_name: string
  client_found: boolean
  mapped_status: string | null
  filing_deadline: string | null
  description: string | null
  status: RowStatus
  reason: string | null
}

interface JobPreviewResult {
  total_rows: number
  will_import: number
  will_skip: number
  warnings: number
  rows: JobPreviewRow[]
}

interface JobImportResult {
  created: number
  skipped: number
  warnings: number
  errors: { row: number; reason: string }[]
}

type SectionState = 'upload' | 'preview' | 'success' | 'error'

// ---------------------------------------------------------------------------
// Small shared components
// ---------------------------------------------------------------------------

function StatPill({ label, value, variant }: { label: string; value: number; variant: 'default' | 'green' | 'amber' }) {
  const colors = {
    default: 'bg-[#E5E7EB] text-[#374151]',
    green: 'bg-[#D1FAE5] text-[#065F46]',
    amber: value > 0 ? 'bg-[#FEF3C7] text-[#92400E]' : 'bg-[#E5E7EB] text-[#6B7280]',
  }
  return (
    <div className={cn('px-3 py-1.5 rounded-[6px] flex flex-col items-center gap-0.5', colors[variant])}>
      <span className="text-[15px] font-semibold leading-none">{value}</span>
      <span className="text-[10px] uppercase tracking-[0.05em] font-medium">{label}</span>
    </div>
  )
}

function StatusBadge({ status }: { status: RowStatus }) {
  if (status === 'import') {
    return (
      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
        Import
      </span>
    )
  }
  if (status === 'skip') {
    return (
      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E]">
        Skip
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E]">
      <AlertTriangle className="w-3 h-3" />
      Warning
    </span>
  )
}

function DropZone({
  file,
  onFile,
  disabled,
}: {
  file: File | null
  onFile: (f: File) => void
  disabled?: boolean
}) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) onFile(f)
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-[8px] border-2 border-dashed p-6 cursor-pointer transition-colors',
        dragOver ? 'border-[#1F3148] bg-[#EEF2FF]' : 'border-[#C8CDD6] hover:border-[#A0A8B4]',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <Upload className="w-6 h-6 text-[#6B7280]" />
      {file ? (
        <span className="text-[13px] text-brand dark:text-[#EDEEF0] font-medium text-center break-all">
          {file.name}
        </span>
      ) : (
        <>
          <span className="text-[13px] text-[#6B7280]">Drop CSV here or click to browse</span>
          <span className="text-[11px] text-[#9CA3AF]">Accepts .csv only</span>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Client section
// ---------------------------------------------------------------------------

function ClientSection() {
  const [state, setState] = useState<SectionState>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [preview, setPreview] = useState<ClientPreviewResult | null>(null)
  const [result, setResult] = useState<ClientImportResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  function reset() {
    setState('upload')
    setFile(null)
    setPreview(null)
    setResult(null)
    setErrorMsg(null)
  }

  async function handlePreview() {
    if (!file) return
    setPreviewing(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/v1/migration/taxdome/preview-clients', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPreview(res.data)
      setState('preview')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Preview failed. Please try again.'
      setErrorMsg(detail)
      setState('error')
    } finally {
      setPreviewing(false)
    }
  }

  async function handleImport() {
    if (!file) return
    setImporting(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/v1/migration/taxdome/import-clients', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      setState('success')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Import failed. Please try again.'
      setErrorMsg(detail)
      setState('error')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0]">Import Clients from TaxDome</p>
        <p className="text-[12px] text-[#6B7280] mt-1">
          Upload your TaxDome Accounts export. Download it from TaxDome under Clients, select all, and export as CSV. JAMM PX will preview every row before importing anything.
        </p>
      </div>

      {state === 'upload' && (
        <div className="flex flex-col gap-3">
          <DropZone file={file} onFile={setFile} disabled={previewing} />
          <div className="flex justify-end">
            <button
              onClick={handlePreview}
              disabled={!file || previewing}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2"
            >
              {previewing && (
                <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {previewing ? 'Previewing...' : 'Preview Import'}
            </button>
          </div>
        </div>
      )}

      {state === 'preview' && preview && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <StatPill label="rows found" value={preview.total_rows} variant="default" />
            <StatPill label="will import" value={preview.will_import} variant="green" />
            <StatPill label="will skip" value={preview.will_skip} variant="amber" />
            <StatPill label="warnings" value={preview.warnings} variant="amber" />
          </div>

          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-[#EDEEF0] dark:bg-[#252525]">
                  {['#', 'Name', 'Email', 'Phone', 'Entity Type', 'State', 'Status', 'Reason'].map((col) => (
                    <th key={col} className="px-3 py-2 text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, idx) => (
                  <tr
                    key={row.row_number}
                    className={cn(
                      'bg-surface-page dark:bg-dark-page',
                      idx !== preview.rows.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card' : '',
                    )}
                  >
                    <td className="px-3 py-2 text-[12px] text-[#6B7280]">{row.row_number}</td>
                    <td className="px-3 py-2 text-[12px] text-brand dark:text-[#EDEEF0] whitespace-nowrap">{row.name || <span className="text-[#9CA3AF]">blank</span>}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{row.email ?? ''}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{row.phone ?? ''}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{row.entity_type ?? ''}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{row.state ?? ''}</td>
                    <td className="px-3 py-2"><StatusBadge status={row.status} /></td>
                    <td className="px-3 py-2 text-[12px] text-[#6B7280] max-w-[200px]">{row.reason ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={reset}
              disabled={importing}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] border border-[0.5px] border-[#C8CDD6] text-[#374151] dark:text-[#EDEEF0] hover:bg-[#F3F4F6] transition-colors disabled:opacity-60"
            >
              Start Over
            </button>
            <button
              onClick={handleImport}
              disabled={importing}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2"
            >
              {importing && (
                <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {importing ? 'Importing...' : 'Confirm Import'}
            </button>
          </div>
        </div>
      )}

      {state === 'success' && result && (
        <div className="flex flex-col gap-3">
          <div className="flex items-start gap-2 rounded-[8px] p-3 bg-[#D1FAE5] border border-[#6EE7B7]">
            <CheckCircle className="w-4 h-4 text-[#065F46] mt-0.5 flex-shrink-0" />
            <p className="text-[13px] text-[#065F46] font-medium">
              Import complete -- {result.created} client{result.created !== 1 ? 's' : ''} imported, {result.skipped} skipped.
            </p>
          </div>
          <div className="flex justify-end">
            <button
              onClick={reset}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] border border-[0.5px] border-[#C8CDD6] text-[#374151] dark:text-[#EDEEF0] hover:bg-[#F3F4F6] transition-colors"
            >
              Import Another File
            </button>
          </div>
        </div>
      )}

      {state === 'error' && (
        <div className="flex flex-col gap-3">
          {preview && (
            <div className="rounded-modal border border-[0.5px] border-surface-border overflow-hidden overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="bg-[#EDEEF0]">
                    {['#', 'Name', 'Email', 'Phone', 'Entity Type', 'State', 'Status', 'Reason'].map((col) => (
                      <th key={col} className="px-3 py-2 text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, idx) => (
                    <tr key={row.row_number} className={cn('bg-surface-page', idx !== preview.rows.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE]' : '')}>
                      <td className="px-3 py-2 text-[12px] text-[#6B7280]">{row.row_number}</td>
                      <td className="px-3 py-2 text-[12px] text-brand whitespace-nowrap">{row.name || <span className="text-[#9CA3AF]">blank</span>}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151]">{row.email ?? ''}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151]">{row.phone ?? ''}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151]">{row.entity_type ?? ''}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151]">{row.state ?? ''}</td>
                      <td className="px-3 py-2"><StatusBadge status={row.status} /></td>
                      <td className="px-3 py-2 text-[12px] text-[#6B7280] max-w-[200px]">{row.reason ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-[8px] p-3 bg-[#FEE2E2] border border-[#FCA5A5]">
            <p className="text-[13px] text-[#991B1B]">{errorMsg}</p>
          </div>
          <div className="flex justify-end">
            <button
              onClick={() => setState(preview ? 'preview' : 'upload')}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Job section
// ---------------------------------------------------------------------------

function JobSection() {
  const [state, setState] = useState<SectionState>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [preview, setPreview] = useState<JobPreviewResult | null>(null)
  const [result, setResult] = useState<JobImportResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  function reset() {
    setState('upload')
    setFile(null)
    setPreview(null)
    setResult(null)
    setErrorMsg(null)
  }

  async function handlePreview() {
    if (!file) return
    setPreviewing(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/v1/migration/taxdome/preview-jobs', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPreview(res.data)
      setState('preview')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Preview failed. Please try again.'
      setErrorMsg(detail)
      setState('error')
    } finally {
      setPreviewing(false)
    }
  }

  async function handleImport() {
    if (!file) return
    setImporting(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/v1/migration/taxdome/import-jobs', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      setState('success')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Import failed. Please try again.'
      setErrorMsg(detail)
      setState('error')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0]">Import Jobs from TaxDome</p>
        <p className="text-[12px] text-[#6B7280] mt-1">
          Upload your TaxDome Jobs export. Download it from TaxDome under Work, select all jobs, and export as CSV. Import clients first -- job matching uses client names.
        </p>
      </div>

      {state === 'upload' && (
        <div className="flex flex-col gap-3">
          <DropZone file={file} onFile={setFile} disabled={previewing} />
          <div className="flex justify-end">
            <button
              onClick={handlePreview}
              disabled={!file || previewing}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2"
            >
              {previewing && (
                <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {previewing ? 'Previewing...' : 'Preview Import'}
            </button>
          </div>
        </div>
      )}

      {state === 'preview' && preview && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <StatPill label="rows found" value={preview.total_rows} variant="default" />
            <StatPill label="will import" value={preview.will_import} variant="green" />
            <StatPill label="will skip" value={preview.will_skip} variant="amber" />
            <StatPill label="warnings" value={preview.warnings} variant="amber" />
          </div>

          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-[#EDEEF0] dark:bg-[#252525]">
                  {['#', 'Job Name', 'Client', 'Status', 'Filing Deadline', 'Description', 'Import Status', 'Reason'].map((col) => (
                    <th key={col} className="px-3 py-2 text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, idx) => (
                  <tr
                    key={row.row_number}
                    className={cn(
                      'bg-surface-page dark:bg-dark-page',
                      idx !== preview.rows.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card' : '',
                    )}
                  >
                    <td className="px-3 py-2 text-[12px] text-[#6B7280]">{row.row_number}</td>
                    <td className="px-3 py-2 text-[12px] text-brand dark:text-[#EDEEF0] whitespace-nowrap">{row.job_name || <span className="text-[#9CA3AF]">blank</span>}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF] whitespace-nowrap">
                      <span className={cn(!row.client_found && 'text-[#EF4444]')}>{row.client_name}</span>
                    </td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{row.mapped_status ?? ''}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{row.filing_deadline ?? ''}</td>
                    <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF] max-w-[150px] truncate">{row.description ?? ''}</td>
                    <td className="px-3 py-2"><StatusBadge status={row.status} /></td>
                    <td className="px-3 py-2 text-[12px] text-[#6B7280] max-w-[200px]">{row.reason ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={reset}
              disabled={importing}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] border border-[0.5px] border-[#C8CDD6] text-[#374151] dark:text-[#EDEEF0] hover:bg-[#F3F4F6] transition-colors disabled:opacity-60"
            >
              Start Over
            </button>
            <button
              onClick={handleImport}
              disabled={importing}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2"
            >
              {importing && (
                <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {importing ? 'Importing...' : 'Confirm Import'}
            </button>
          </div>
        </div>
      )}

      {state === 'success' && result && (
        <div className="flex flex-col gap-3">
          <div className="flex items-start gap-2 rounded-[8px] p-3 bg-[#D1FAE5] border border-[#6EE7B7]">
            <CheckCircle className="w-4 h-4 text-[#065F46] mt-0.5 flex-shrink-0" />
            <p className="text-[13px] text-[#065F46] font-medium">
              Import complete -- {result.created} job{result.created !== 1 ? 's' : ''} imported, {result.skipped} skipped.
            </p>
          </div>
          <div className="flex justify-end">
            <button
              onClick={reset}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] border border-[0.5px] border-[#C8CDD6] text-[#374151] dark:text-[#EDEEF0] hover:bg-[#F3F4F6] transition-colors"
            >
              Import Another File
            </button>
          </div>
        </div>
      )}

      {state === 'error' && (
        <div className="flex flex-col gap-3">
          {preview && (
            <div className="rounded-modal border border-[0.5px] border-surface-border overflow-hidden overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="bg-[#EDEEF0]">
                    {['#', 'Job Name', 'Client', 'Status', 'Filing Deadline', 'Description', 'Import Status', 'Reason'].map((col) => (
                      <th key={col} className="px-3 py-2 text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, idx) => (
                    <tr key={row.row_number} className={cn('bg-surface-page', idx !== preview.rows.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE]' : '')}>
                      <td className="px-3 py-2 text-[12px] text-[#6B7280]">{row.row_number}</td>
                      <td className="px-3 py-2 text-[12px] text-brand whitespace-nowrap">{row.job_name || <span className="text-[#9CA3AF]">blank</span>}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151] whitespace-nowrap"><span className={cn(!row.client_found && 'text-[#EF4444]')}>{row.client_name}</span></td>
                      <td className="px-3 py-2 text-[12px] text-[#374151]">{row.mapped_status ?? ''}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151]">{row.filing_deadline ?? ''}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151] max-w-[150px] truncate">{row.description ?? ''}</td>
                      <td className="px-3 py-2"><StatusBadge status={row.status} /></td>
                      <td className="px-3 py-2 text-[12px] text-[#6B7280] max-w-[200px]">{row.reason ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-[8px] p-3 bg-[#FEE2E2] border border-[#FCA5A5]">
            <p className="text-[13px] text-[#991B1B]">{errorMsg}</p>
          </div>
          <div className="flex justify-end">
            <button
              onClick={() => setState(preview ? 'preview' : 'upload')}
              className="h-8 px-4 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main tab
// ---------------------------------------------------------------------------

export default function MigrationTab() {
  return (
    <div className="flex flex-col gap-0 max-w-4xl">
      <div className="bg-[#EDEEF0] dark:bg-[#383838] rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] p-4">
        <ClientSection />
      </div>

      <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] my-6" />

      <div className="bg-[#EDEEF0] dark:bg-[#383838] rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] p-4">
        <JobSection />
      </div>
    </div>
  )
}
