// frontend/src/app/(app)/firm-library/page.tsx
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
  MoreHorizontal,
  Search,
  Upload,
  FolderPlus,
  Copy,
  Download,
  X,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'
import { Breadcrumb } from '@/components/layout/Breadcrumb'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FirmFolder {
  id: string
  name: string
  scope: string
  parent_folder_id: string | null
  children?: FirmFolder[]
  expanded?: boolean
}

interface FirmDoc {
  id: string
  filename: string
  description: string | null
  content_type: string
  size_bytes: number
  uploaded_by_name: string | null
  created_at: string
  folder_id: string | null
  scope: string
}

interface EngagementOption {
  id: string
  name: string
  client_id: string
}

interface ClientOption {
  id: string
  name: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}

function fileTypeLabel(contentType: string): string {
  if (contentType.includes('pdf')) return 'PDF'
  if (contentType.includes('word') || contentType.includes('docx') || contentType.includes('document')) return 'Word'
  if (contentType.includes('excel') || contentType.includes('xlsx') || contentType.includes('spreadsheet')) return 'Excel'
  if (contentType.includes('powerpoint') || contentType.includes('pptx') || contentType.includes('presentation')) return 'PPT'
  if (contentType.includes('image')) return 'Image'
  if (contentType.includes('text')) return 'Text'
  if (contentType.includes('csv')) return 'CSV'
  return 'File'
}

function FileTypeIcon({ contentType }: { contentType: string }) {
  let bgColor = '#6B7280'
  const label = fileTypeLabel(contentType)
  if (label === 'PDF') bgColor = '#DC2626'
  else if (label === 'Word') bgColor = '#2563EB'
  else if (label === 'Excel') bgColor = '#16A34A'
  else if (label === 'PPT') bgColor = '#D97706'
  else if (label === 'Image') bgColor = '#7C3AED'
  return (
    <div
      className="flex items-center justify-center w-8 h-8 rounded flex-shrink-0"
      style={{ backgroundColor: bgColor }}
    >
      <FileText className="h-4 w-4 text-white" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// FolderTree node
// ---------------------------------------------------------------------------

function FolderNode({
  folder,
  depth,
  selectedId,
  onSelect,
  firmId,
}: {
  folder: FirmFolder
  depth: number
  selectedId: string | null
  onSelect: (f: FirmFolder) => void
  firmId: string
}) {
  const [expanded, setExpanded] = useState(depth === 0)
  const [children, setChildren] = useState<FirmFolder[] | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleToggle(e: React.MouseEvent) {
    e.stopPropagation()
    if (!expanded && children === null) {
      setLoading(true)
      try {
        const { data } = await api.get('/document-folders/', {
          params: { scope: 'firm_library', parent_folder_id: folder.id },
        })
        setChildren(Array.isArray(data) ? data : [])
      } catch {
        setChildren([])
      } finally {
        setLoading(false)
      }
    }
    setExpanded((v) => !v)
  }

  const isSelected = selectedId === folder.id
  const hasChildren = folder.children !== undefined ? folder.children.length > 0 : true

  return (
    <div>
      <div
        className={[
          'flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-[13px] transition-colors select-none',
          isSelected
            ? 'bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] font-medium'
            : 'text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0]',
        ].join(' ')}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
        onClick={() => onSelect(folder)}
      >
        {hasChildren ? (
          <button
            className="p-0 m-0 border-0 bg-transparent flex-shrink-0"
            onClick={handleToggle}
          >
            {loading ? (
              <Loader2 className="h-3 w-3 animate-spin text-[#6B7280]" />
            ) : expanded ? (
              <ChevronDown className="h-3 w-3 text-[#6B7280]" />
            ) : (
              <ChevronRight className="h-3 w-3 text-[#6B7280]" />
            )}
          </button>
        ) : (
          <span className="w-3 flex-shrink-0" />
        )}
        {expanded ? (
          <FolderOpen className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
        ) : (
          <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
        )}
        <span className="truncate">{folder.name}</span>
      </div>
      {expanded && children && children.map((child) => (
        <FolderNode
          key={child.id}
          folder={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
          firmId={firmId}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Copy To modal
// ---------------------------------------------------------------------------

function CopyToModal({
  doc,
  firmLibraryFolders,
  onClose,
  onCopied,
}: {
  doc: FirmDoc
  firmLibraryFolders: FirmFolder[]
  onClose: () => void
  onCopied: () => void
}) {
  const [destType, setDestType] = useState<'firm_library' | 'engagement'>('firm_library')
  const [selectedFolderId, setSelectedFolderId] = useState<string>('')
  const [clients, setClients] = useState<ClientOption[]>([])
  const [selectedClientId, setSelectedClientId] = useState('')
  const [engagements, setEngagements] = useState<EngagementOption[]>([])
  const [selectedEngagementId, setSelectedEngagementId] = useState('')
  const [engagementFolders, setEngagementFolders] = useState<{ id: string; name: string }[]>([])
  const [engagementFoldersLoading, setEngagementFoldersLoading] = useState(false)
  // undefined = no folder decision made yet; '' = engagement root; UUID string = specific folder
  const [selectedEngFolderDecision, setSelectedEngFolderDecision] = useState<string | undefined>(undefined)
  const [copying, setCopying] = useState(false)
  const [conflict, setConflict] = useState<{ existing_id: string; filename: string } | null>(null)

  useEffect(() => {
    if (destType === 'engagement') {
      api.get('/clients/', { params: { limit: 200 } })
        .then((r) => setClients(r.data.items ?? r.data ?? []))
        .catch(() => {})
    }
  }, [destType])

  useEffect(() => {
    if (selectedClientId) {
      api.get('/engagements/', { params: { client_id: selectedClientId, limit: 100 } })
        .then((r) => setEngagements(r.data.items ?? r.data ?? []))
        .catch(() => {})
    } else {
      setEngagements([])
      setSelectedEngagementId('')
    }
  }, [selectedClientId])

  // Fetch the chosen engagement's folders so the user can pick a real destination.
  useEffect(() => {
    if (!selectedEngagementId) {
      setEngagementFolders([])
      setSelectedEngFolderDecision(undefined)
      return
    }
    setEngagementFoldersLoading(true)
    setSelectedEngFolderDecision(undefined)
    api.get('/document-folders/', { params: { scope: 'engagement', engagement_id: selectedEngagementId } })
      .then((r) => setEngagementFolders(Array.isArray(r.data) ? r.data : []))
      .catch(() => setEngagementFolders([]))
      .finally(() => setEngagementFoldersLoading(false))
  }, [selectedEngagementId])

  async function handleCopy(duplicateAction?: 'replace' | 'keep_both') {
    // Resolve the destination folder_id.
    // Firm Library: selectedFolderId '' = root (no folder_id sent = copy-in-place at source).
    // Engagement: selectedEngFolderDecision '' = engagement root (no folder_id sent).
    // NOTE: sending no folder_id for the engagement path falls back to copy-in-place at the
    // SOURCE scope (firm_library) per copy_document's backend logic. "Engagement root" without
    // a real folder_id is not expressible by this API. Users should select a real subfolder
    // for engagement copies to land in the correct engagement.
    const folderId = destType === 'firm_library'
      ? (selectedFolderId || null)
      : (selectedEngFolderDecision || null)

    setCopying(true)
    try {
      const body: Record<string, unknown> = {}
      if (folderId) body.folder_id = folderId
      // duplicate_action is omitted on the first attempt so the backend can return
      // a real conflict object if a filename collision exists, instead of silently
      // overriding the user's intent.
      if (duplicateAction) body.duplicate_action = duplicateAction

      const { data } = await api.post(`/documents/${doc.id}/copy`, body)

      if (data.conflict) {
        // Backend returned a real conflict -- show the inline resolution prompt.
        setConflict(data.conflict)
        return
      }

      toast.success(`"${doc.filename}" copied successfully`)
      onCopied()
      onClose()
    } catch {
      toast.error('Copy failed -- please try again')
    } finally {
      setCopying(false)
    }
  }

  const canSubmit =
    !copying && (
      destType === 'firm_library' ||
      (destType === 'engagement' && !!selectedEngagementId && selectedEngFolderDecision !== undefined)
    )

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[480px] max-w-[92vw] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Copy to...</h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        {conflict ? (
          <div className="p-5 flex flex-col gap-4">
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">
              A file named <strong>&ldquo;{conflict.filename}&rdquo;</strong> already exists at this destination.
            </p>
            <p className="text-[12px] text-[#6B7280]">How would you like to handle this?</p>
            <div className="flex gap-2">
              <button
                onClick={() => handleCopy('replace')}
                disabled={copying}
                className="flex-1 h-9 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] hover:border-brand hover:text-brand transition-colors disabled:opacity-50"
              >
                {copying ? 'Working...' : 'Replace existing'}
              </button>
              <button
                onClick={() => handleCopy('keep_both')}
                disabled={copying}
                className="flex-1 h-9 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {copying ? 'Working...' : 'Keep both'}
              </button>
            </div>
            <button
              onClick={() => setConflict(null)}
              className="text-[11px] text-[#6B7280] hover:text-brand underline self-start"
            >
              Go back
            </button>
          </div>
        ) : (
          <>
            <div className="p-5 flex flex-col gap-4">
              <div className="flex gap-2">
                <button
                  onClick={() => setDestType('firm_library')}
                  className={[
                    'flex-1 py-2 rounded-[6px] text-[12px] font-medium border border-[0.5px] transition-colors',
                    destType === 'firm_library'
                      ? 'bg-brand text-white border-brand'
                      : 'border-surface-border dark:border-dark-border text-[#6B7280] hover:text-brand',
                  ].join(' ')}
                >
                  Firm Library
                </button>
                <button
                  onClick={() => setDestType('engagement')}
                  className={[
                    'flex-1 py-2 rounded-[6px] text-[12px] font-medium border border-[0.5px] transition-colors',
                    destType === 'engagement'
                      ? 'bg-brand text-white border-brand'
                      : 'border-surface-border dark:border-dark-border text-[#6B7280] hover:text-brand',
                  ].join(' ')}
                >
                  Engagement
                </button>
              </div>

              {destType === 'firm_library' && (
                <div>
                  <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
                    Destination folder
                  </label>
                  <select
                    value={selectedFolderId}
                    onChange={(e) => setSelectedFolderId(e.target.value)}
                    className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]"
                  >
                    <option value="">Firm Library root</option>
                    {firmLibraryFolders.map((f) => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {destType === 'engagement' && (
                <>
                  <div>
                    <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
                      Client
                    </label>
                    <select
                      value={selectedClientId}
                      onChange={(e) => {
                        setSelectedClientId(e.target.value)
                        setSelectedEngagementId('')
                        setSelectedEngFolderDecision(undefined)
                      }}
                      className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]"
                    >
                      <option value="">Select client...</option>
                      {clients.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>
                  {selectedClientId && (
                    <div>
                      <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
                        Engagement
                      </label>
                      <select
                        value={selectedEngagementId}
                        onChange={(e) => setSelectedEngagementId(e.target.value)}
                        className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]"
                      >
                        <option value="">Select engagement...</option>
                        {engagements.map((e) => (
                          <option key={e.id} value={e.id}>{e.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  {selectedEngagementId && (
                    <div>
                      <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
                        Destination folder
                      </label>
                      {engagementFoldersLoading ? (
                        <div className="h-9 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card flex items-center px-2.5">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#6B7280]" />
                        </div>
                      ) : (
                        <select
                          value={selectedEngFolderDecision === undefined ? '__unset__' : selectedEngFolderDecision}
                          onChange={(e) => {
                            const v = e.target.value
                            setSelectedEngFolderDecision(v === '__unset__' ? undefined : v)
                          }}
                          className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]"
                        >
                          <option value="__unset__" disabled>Choose a destination...</option>
                          <option value="">Engagement root</option>
                          {engagementFolders.map((f) => (
                            <option key={f.id} value={f.id}>{f.name}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[0.5px] border-surface-border dark:border-dark-border">
              <button
                onClick={onClose}
                className="h-8 px-3.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleCopy()}
                disabled={!canSubmit}
                className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {copying ? 'Copying...' : 'Copy here'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function UploadModal({
  currentFolderId,
  firmId,
  onClose,
  onUploaded,
}: {
  currentFolderId: string | null
  firmId: string
  onClose: () => void
  onUploaded: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setProgress('Requesting upload URL...')
    try {
      const urlPayload: Record<string, unknown> = {
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      }
      if (currentFolderId) urlPayload.folder_id = currentFolderId

      const { data: urlData } = await api.post('/documents/upload-url', urlPayload)
      const { document_id, upload_url } = urlData

      setProgress('Uploading to S3...')
      await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      })

      setProgress('Finalizing...')
      const completePayload: Record<string, unknown> = {
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      }
      if (currentFolderId) completePayload.folder_id = currentFolderId
      if (description.trim()) completePayload.description = description.trim()

      await api.post(`/documents/${document_id}/upload-complete`, completePayload)
      toast.success(`"${file.name}" uploaded to Firm Library`)
      onUploaded()
      onClose()
    } catch {
      toast.error('Upload failed -- please try again')
    } finally {
      setUploading(false)
      setProgress('')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[480px] max-w-[92vw] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Upload to Firm Library</h2>
          <button onClick={onClose} disabled={uploading} className="text-[#6B7280] hover:text-brand transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5 flex flex-col gap-4">
          <div>
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
              File
            </label>
            <div
              className="border border-dashed border-surface-border dark:border-dark-border rounded-[6px] p-6 text-center cursor-pointer hover:bg-surface-input dark:hover:bg-dark-card transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              {file ? (
                <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{file.name}</p>
              ) : (
                <>
                  <Upload className="h-6 w-6 text-[#6B7280] mx-auto mb-2" />
                  <p className="text-[13px] text-[#6B7280]">Click to select a file</p>
                </>
              )}
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          </div>
          <div>
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
              Description (optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Standard engagement letter for individual returns"
              className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none"
            />
          </div>
          {progress && (
            <p className="text-[12px] text-[#6B7280] flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              {progress}
            </p>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[0.5px] border-surface-border dark:border-dark-border">
          <button
            onClick={onClose}
            disabled={uploading}
            className="h-8 px-3.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// New Folder modal
// ---------------------------------------------------------------------------

function NewFolderModal({
  parentFolderId,
  onClose,
  onCreated,
}: {
  parentFolderId: string | null
  onClose: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  async function handleCreate() {
    if (!name.trim()) return
    setCreating(true)
    try {
      const body: Record<string, unknown> = { scope: 'firm_library', name: name.trim() }
      if (parentFolderId) body.parent_folder_id = parentFolderId
      await api.post('/document-folders/', body)
      toast.success(`Folder "${name.trim()}" created`)
      onCreated()
      onClose()
    } catch {
      toast.error('Could not create folder -- please try again')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[400px] max-w-[92vw] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">New Folder</h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">
          <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
            Folder name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCreate() }}
            placeholder="e.g. Tax Templates"
            autoFocus
            className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none"
          />
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[0.5px] border-surface-border dark:border-dark-border">
          <button
            onClick={onClose}
            className="h-8 px-3.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!name.trim() || creating}
            className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Row overflow menu
// ---------------------------------------------------------------------------

function OverflowMenu({
  doc,
  isElevated,
  onCopyTo,
  onDownload,
}: {
  doc: FirmDoc
  isElevated: boolean
  onCopyTo: () => void
  onDownload: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
        className="flex items-center justify-center w-7 h-7 rounded hover:bg-surface-input dark:hover:bg-dark-card text-[#6B7280] hover:text-brand transition-colors"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-44 bg-surface-page dark:bg-dark-page border border-[0.5px] border-surface-border dark:border-dark-border rounded-[6px] shadow-lg z-20 py-1">
          <button
            onClick={(e) => { e.stopPropagation(); setOpen(false); onCopyTo() }}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand transition-colors"
          >
            <Copy className="h-3.5 w-3.5" />
            Copy to...
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); setOpen(false); onDownload() }}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function FileSkeleton() {
  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0">
          <div className="w-8 h-8 rounded bg-[#D5D8DE] dark:bg-[#444444] animate-pulse flex-shrink-0" />
          <div className="flex-1 flex flex-col gap-1.5">
            <div className="h-3.5 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-2.5 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          </div>
          <div className="h-3 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          <div className="h-3 w-12 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          <div className="h-3 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function FirmLibraryPage() {
  const { user } = useAuth()
  const isElevated = user?.role === 'firm_owner' || user?.role === 'manager' || user?.role === 'system_admin'

  const [rootFolders, setRootFolders] = useState<FirmFolder[]>([])
  const [foldersLoading, setFoldersLoading] = useState(true)

  // Current folder navigation: null = root
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null)
  const [folderPath, setFolderPath] = useState<{ id: string; name: string }[]>([])

  const [docs, setDocs] = useState<FirmDoc[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [search, setSearch] = useState('')

  const [allFirmFolders, setAllFirmFolders] = useState<FirmFolder[]>([])

  // Modals
  const [copyTarget, setCopyTarget] = useState<FirmDoc | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const [showNewFolder, setShowNewFolder] = useState(false)

  // Load root-level folders
  const loadRootFolders = useCallback(async () => {
    setFoldersLoading(true)
    try {
      const { data } = await api.get('/document-folders/', {
        params: { scope: 'firm_library', parent_folder_id: null },
      })
      const folders = Array.isArray(data) ? data : []
      setRootFolders(folders)
      setAllFirmFolders(folders)
    } catch {
      setRootFolders([])
    } finally {
      setFoldersLoading(false)
    }
  }, [])

  useEffect(() => { loadRootFolders() }, [loadRootFolders])

  // Load documents for current folder
  const loadDocs = useCallback(async () => {
    setDocsLoading(true)
    try {
      const params: Record<string, unknown> = { scope: 'firm_library', limit: 200 }
      if (currentFolderId) params.folder_id = currentFolderId
      const { data } = await api.get('/documents/', { params })
      setDocs(data.items ?? data ?? [])
    } catch {
      setDocs([])
    } finally {
      setDocsLoading(false)
    }
  }, [currentFolderId])

  useEffect(() => { loadDocs() }, [loadDocs])

  function handleFolderSelect(folder: FirmFolder) {
    setCurrentFolderId(folder.id)
    // Build breadcrumb path: if folder is a root folder, path is just it;
    // deeper nesting would require walking up. For this implementation,
    // clicking a folder in the tree sets it as current with a single-level path.
    setFolderPath([{ id: folder.id, name: folder.name }])
    setSearch('')
  }

  function handleRootSelect() {
    setCurrentFolderId(null)
    setFolderPath([])
    setSearch('')
  }

  async function handleDownload(doc: FirmDoc) {
    try {
      const { data } = await api.get(`/documents/${doc.id}/download`)
      const url = data.url ?? data.signed_url
      if (url) window.open(url, '_blank')
    } catch {
      toast.error('Could not generate download link')
    }
  }

  // Filtered docs
  const filteredDocs = docs.filter((d) => {
    if (!search) return true
    return d.filename.toLowerCase().includes(search.toLowerCase()) ||
      (d.description ?? '').toLowerCase().includes(search.toLowerCase())
  })

  // Breadcrumb items
  const breadcrumbItems = [
    { label: 'Firm Library', href: undefined, onClick: handleRootSelect },
    ...folderPath.map((f) => ({ label: f.name, href: undefined })),
  ]

  return (
    <div className="flex h-full">
      {/* Left panel: folder tree */}
      <div className="w-56 flex-shrink-0 border-r border-[0.5px] border-surface-border dark:border-dark-border flex flex-col bg-surface-page dark:bg-dark-page">
        <div className="px-3 py-3 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Folders</p>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {/* All Files root entry */}
          <div
            className={[
              'flex items-center gap-2 px-3 py-1.5 rounded cursor-pointer text-[13px] transition-colors mx-1',
              currentFolderId === null
                ? 'bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] font-medium'
                : 'text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0]',
            ].join(' ')}
            onClick={handleRootSelect}
          >
            <FolderOpen className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
            <span>All Files</span>
          </div>

          {foldersLoading ? (
            <div className="px-3 py-2 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-4 rounded bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" style={{ width: `${60 + i * 8}%` }} />
              ))}
            </div>
          ) : rootFolders.length === 0 ? (
            <p className="px-3 py-2 text-[12px] text-[#9CA3AF]">No folders yet</p>
          ) : (
            rootFolders.map((folder) => (
              <FolderNode
                key={folder.id}
                folder={folder}
                depth={0}
                selectedId={currentFolderId}
                onSelect={handleFolderSelect}
                firmId=""
              />
            ))
          )}
        </div>
      </div>

      {/* Right panel: main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-6 flex flex-col gap-4 flex-1 overflow-y-auto">
          {/* Page title + breadcrumb */}
          <div>
            <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">Firm Library</h1>
            <p className="text-[12px] text-[#6B7280] mb-3">
              Templates and resources for your team. Copy files into client folders to get started.
            </p>
            {folderPath.length > 0 && (
              <nav className="flex items-center gap-1.5 text-[13px]">
                <button
                  onClick={handleRootSelect}
                  className="text-[#6B7280] hover:text-brand transition-colors"
                >
                  Firm Library
                </button>
                {folderPath.map((f, i) => (
                  <span key={f.id} className="flex items-center gap-1.5">
                    <span className="text-[#9CA3AF]">/</span>
                    <span className={i === folderPath.length - 1 ? 'text-brand dark:text-[#EDEEF0] font-medium' : 'text-[#6B7280]'}>
                      {f.name}
                    </span>
                  </span>
                ))}
              </nav>
            )}
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
              <input
                type="text"
                placeholder="Search files..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full h-9 pl-8 pr-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none transition-colors"
              />
            </div>
            {isElevated && (
              <>
                <button
                  onClick={() => setShowNewFolder(true)}
                  className="h-9 px-3 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:text-brand hover:border-brand transition-colors flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
                >
                  <FolderPlus className="h-4 w-4" />
                  New Folder
                </button>
                <button
                  onClick={() => setShowUpload(true)}
                  className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
                >
                  <Upload className="h-4 w-4" />
                  Upload
                </button>
              </>
            )}
          </div>

          {/* File list */}
          {docsLoading ? (
            <FileSkeleton />
          ) : filteredDocs.length === 0 && search ? (
            <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                <Search className="h-5 w-5 text-[#6B7280]" />
              </div>
              <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                No results for &ldquo;{search}&rdquo;
              </p>
              <p className="text-[12px] text-[#6B7280]">Try a different filename or description.</p>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                <FileText className="h-5 w-5 text-[#6B7280]" />
              </div>
              <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                No files in this folder yet
              </p>
              <p className="text-[12px] text-[#6B7280]">
                {isElevated ? 'Upload templates, blank organizers, and other firm resources here.' : 'Ask a manager to upload files here.'}
              </p>
            </div>
          ) : (
            <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-surface-card dark:bg-[#252525]">
                    {['Name', 'Type', 'Size', 'Uploaded', 'Uploaded By', ''].map((col, i) => (
                      <th
                        key={i}
                        className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredDocs.map((doc, i) => (
                    <tr
                      key={doc.id}
                      className={[
                        'group transition-colors bg-surface-page dark:bg-dark-page',
                        'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                        i !== filteredDocs.length - 1
                          ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                          : '',
                      ].join(' ')}
                    >
                      {/* Name + description */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <FileTypeIcon contentType={doc.content_type} />
                          <div className="flex flex-col min-w-0">
                            <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] truncate">
                              {doc.filename}
                            </span>
                            {doc.description && (
                              <span className="text-[11px] text-[#6B7280] truncate mt-0.5">
                                {doc.description}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      {/* Type */}
                      <td className="px-4 py-3">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                          {fileTypeLabel(doc.content_type)}
                        </span>
                      </td>
                      {/* Size */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                          {formatBytes(doc.size_bytes)}
                        </span>
                      </td>
                      {/* Uploaded date */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                          {formatDate(doc.created_at)}
                        </span>
                      </td>
                      {/* Uploaded by */}
                      <td className="px-4 py-3">
                        <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                          {doc.uploaded_by_name ?? 'Staff'}
                        </span>
                      </td>
                      {/* Actions */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 justify-end">
                          <button
                            onClick={() => setCopyTarget(doc)}
                            className="h-7 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[11px] text-[#374151] dark:text-[#9CA3AF] hover:border-brand hover:text-brand transition-colors flex items-center gap-1.5 whitespace-nowrap opacity-0 group-hover:opacity-100"
                          >
                            <Copy className="h-3 w-3" />
                            Copy to...
                          </button>
                          <OverflowMenu
                            doc={doc}
                            isElevated={isElevated}
                            onCopyTo={() => setCopyTarget(doc)}
                            onDownload={() => handleDownload(doc)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      {copyTarget && (
        <CopyToModal
          doc={copyTarget}
          firmLibraryFolders={allFirmFolders}
          onClose={() => setCopyTarget(null)}
          onCopied={loadDocs}
        />
      )}
      {showUpload && (
        <UploadModal
          currentFolderId={currentFolderId}
          firmId=""
          onClose={() => setShowUpload(false)}
          onUploaded={loadDocs}
        />
      )}
      {showNewFolder && (
        <NewFolderModal
          parentFolderId={currentFolderId}
          onClose={() => setShowNewFolder(false)}
          onCreated={loadRootFolders}
        />
      )}
    </div>
  )
}
