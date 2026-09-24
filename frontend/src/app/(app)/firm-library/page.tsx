// frontend/src/app/(app)/firm-library/page.tsx
'use client'

import { useState, useEffect, useRef, useCallback, type ChangeEvent, type InputHTMLAttributes } from 'react'
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
  FolderInput,
  MoreHorizontal,
  Search,
  Upload,
  FolderPlus,
  Copy,
  Download,
  X,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'
import { FileTypeIcon, fileTypeLabel } from '@/components/documents/FileTypeIcon'
import { importBatchesApi, type CreateImportBatchPayload } from '@/lib/api/importBatches'
import { enumerateFolder } from '@/lib/importEnumeration'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { firmLibraryApi } from '@/lib/api/firmLibrary'

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
  source?: string
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

// Remembered copy destination (stored per-user in localStorage)
interface LastCopyDest {
  clientId: string
  clientName: string
  engagementId: string
  engagementName: string
  folderId: string | null
  folderName: string | null
}

const LAST_COPY_KEY = (userId: string) => `jamm_last_copy_dest_${userId}`

function getLastCopyDest(userId: string): LastCopyDest | null {
  if (!userId || typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(LAST_COPY_KEY(userId))
    return raw ? (JSON.parse(raw) as LastCopyDest) : null
  } catch {
    return null
  }
}

function saveLastCopyDest(userId: string, dest: LastCopyDest): void {
  if (!userId || typeof window === 'undefined') return
  try {
    localStorage.setItem(LAST_COPY_KEY(userId), JSON.stringify(dest))
  } catch {
    // localStorage unavailable -- silent no-op
  }
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
// Copy To modal -- two-screen flow with remembered last destination
// ---------------------------------------------------------------------------

function CopyToModal({
  doc,
  firmLibraryFolders,
  userId,
  onClose,
  onCopied,
}: {
  doc: FirmDoc
  firmLibraryFolders: FirmFolder[]
  userId: string
  onClose: () => void
  onCopied: () => void
}) {
  const lastDest = getLastCopyDest(userId)
  const [screen, setScreen] = useState<'default' | 'picker'>(lastDest ? 'default' : 'picker')

  const [destType, setDestType] = useState<'firm_library' | 'engagement'>('firm_library')
  const [selectedFolderId, setSelectedFolderId] = useState<string>('')
  const [clients, setClients] = useState<ClientOption[]>([])
  const [selectedClientId, setSelectedClientId] = useState('')
  const [selectedClientName, setSelectedClientName] = useState('')
  const [engagements, setEngagements] = useState<EngagementOption[]>([])
  const [selectedEngagementId, setSelectedEngagementId] = useState('')
  const [selectedEngagementName, setSelectedEngagementName] = useState('')
  const [engagementFolders, setEngagementFolders] = useState<{ id: string; name: string }[]>([])
  const [engagementFoldersLoading, setEngagementFoldersLoading] = useState(false)
  const [selectedEngFolderDecision, setSelectedEngFolderDecision] = useState<string | undefined>(undefined)
  const [selectedFolderName, setSelectedFolderName] = useState<string | null>(null)
  const [copying, setCopying] = useState(false)
  const [conflict, setConflict] = useState<{ existing_id: string; filename: string } | null>(null)

  useEffect(() => {
    if (screen === 'picker' && destType === 'engagement') {
      api.get('/clients/', { params: { limit: 200 } })
        .then((r) => setClients(r.data.items ?? r.data ?? []))
        .catch(() => {})
    }
  }, [screen, destType])

  useEffect(() => {
    if (selectedClientId) {
      api.get('/engagements/', { params: { client_id: selectedClientId, limit: 100 } })
        .then((r) => setEngagements(r.data.items ?? r.data ?? []))
        .catch(() => {})
    } else {
      setEngagements([])
      setSelectedEngagementId('')
      setSelectedEngagementName('')
    }
  }, [selectedClientId])

  useEffect(() => {
    if (!selectedEngagementId) {
      setEngagementFolders([])
      setSelectedEngFolderDecision(undefined)
      setSelectedFolderName(null)
      return
    }
    setEngagementFoldersLoading(true)
    setSelectedEngFolderDecision(undefined)
    setSelectedFolderName(null)
    api.get('/document-folders/', { params: { scope: 'engagement', engagement_id: selectedEngagementId } })
      .then((r) => setEngagementFolders(Array.isArray(r.data) ? r.data : []))
      .catch(() => setEngagementFolders([]))
      .finally(() => setEngagementFoldersLoading(false))
  }, [selectedEngagementId])

  // Live breadcrumb for the picker screen
  const breadcrumbParts: string[] = []
  if (destType === 'firm_library') {
    breadcrumbParts.push('Firm Library')
    if (selectedFolderId) {
      const f = firmLibraryFolders.find((fl) => fl.id === selectedFolderId)
      if (f) breadcrumbParts.push(f.name)
    }
  } else {
    breadcrumbParts.push(selectedClientName || '1. Select a client')
    if (selectedClientId) breadcrumbParts.push(selectedEngagementName || '2. Select an engagement')
    if (selectedEngagementId) {
      if (selectedEngFolderDecision === '') breadcrumbParts.push('Engagement root')
      else if (selectedEngFolderDecision) breadcrumbParts.push(selectedFolderName || '3. Select a destination folder')
      else breadcrumbParts.push('3. Select a destination folder')
    }
  }
  const breadcrumb = breadcrumbParts.join(' > ')

  async function executeCopy(body: Record<string, unknown>, dest: LastCopyDest, duplicateAction?: 'replace' | 'keep_both') {
    setCopying(true)
    try {
      if (duplicateAction) body.duplicate_action = duplicateAction
      const { data } = await api.post(`/documents/${doc.id}/copy`, body)
      if (data.conflict) { setConflict(data.conflict); return }
      saveLastCopyDest(userId, dest)
      toast.success(`"${doc.filename}" copied successfully`)
      onCopied()
      onClose()
    } catch {
      toast.error('Copy failed -- please try again')
    } finally {
      setCopying(false)
    }
  }

  async function handleOneClickCopy(duplicateAction?: 'replace' | 'keep_both') {
    if (!lastDest) return
    const body: Record<string, unknown> = {}
    if (lastDest.folderId) {
      body.folder_id = lastDest.folderId
    } else {
      body.dest_engagement_id = lastDest.engagementId
      body.dest_client_id = lastDest.clientId
    }
    await executeCopy(body, lastDest, duplicateAction)
  }

  async function handlePickerCopy(duplicateAction?: 'replace' | 'keep_both') {
    const body: Record<string, unknown> = {}
    const dest: LastCopyDest = {
      clientId: selectedClientId,
      clientName: selectedClientName,
      engagementId: selectedEngagementId,
      engagementName: selectedEngagementName,
      folderId: selectedEngFolderDecision || null,
      folderName: selectedEngFolderDecision ? (selectedFolderName ?? null) : null,
    }
    if (destType === 'firm_library') {
      if (selectedFolderId) body.folder_id = selectedFolderId
    } else {
      if (selectedEngFolderDecision) body.folder_id = selectedEngFolderDecision
      else { body.dest_engagement_id = selectedEngagementId; body.dest_client_id = selectedClientId }
    }
    await executeCopy(body, dest, duplicateAction)
  }

  const canSubmitPicker =
    !copying && (
      destType === 'firm_library' ||
      (destType === 'engagement' && !!selectedEngagementId && selectedEngFolderDecision !== undefined)
    )

  // Conflict resolution screen (shared between default and picker paths)
  if (conflict) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[480px] max-w-[92vw] shadow-lg" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
            <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Copy to...</h2>
            <button onClick={onClose} className="text-[#6B7280] hover:text-brand transition-colors"><X className="h-4 w-4" /></button>
          </div>
          <div className="p-5 flex flex-col gap-4">
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">
              A file named <strong>&ldquo;{conflict.filename}&rdquo;</strong> already exists at this destination.
            </p>
            <p className="text-[12px] text-[#6B7280]">How would you like to handle this?</p>
            <div className="flex gap-2">
              <button onClick={() => screen === 'default' ? handleOneClickCopy('replace') : handlePickerCopy('replace')} disabled={copying} className="flex-1 h-9 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] hover:border-brand hover:text-brand transition-colors disabled:opacity-50">
                {copying ? 'Working...' : 'Replace existing'}
              </button>
              <button onClick={() => screen === 'default' ? handleOneClickCopy('keep_both') : handlePickerCopy('keep_both')} disabled={copying} className="flex-1 h-9 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
                {copying ? 'Working...' : 'Keep both'}
              </button>
            </div>
            <button onClick={() => setConflict(null)} className="text-[11px] text-[#6B7280] hover:text-brand underline self-start">Go back</button>
          </div>
        </div>
      </div>
    )
  }

  // Screen 1: one-click default
  if (screen === 'default' && lastDest) {
    const destLabel = [lastDest.clientName, lastDest.engagementName, lastDest.folderName].filter(Boolean).join(' > ')
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[400px] max-w-[92vw] shadow-lg" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
            <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Copy to...</h2>
            <button onClick={onClose} className="text-[#6B7280] hover:text-brand transition-colors"><X className="h-4 w-4" /></button>
          </div>
          <div className="p-5 flex flex-col gap-4">
            <div className="flex items-center gap-3 p-3 rounded-[8px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
              <FileTypeIcon contentType={doc.content_type} />
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] truncate">{doc.filename}</p>
                <p className="text-[11px] text-[#9CA3AF]">{formatBytes(doc.size_bytes)}</p>
              </div>
            </div>
            <button onClick={() => handleOneClickCopy()} disabled={copying} className="w-full flex items-center justify-between px-4 py-3 rounded-[8px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border hover:border-brand dark:hover:border-[#4A7FA5] transition-colors disabled:opacity-50 text-left group">
              <div className="flex flex-col gap-0.5">
                <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                  Copy to {lastDest.clientName}
                </span>
                <span className="text-[11px] text-[#6B7280]">
                  {destLabel} <span className="text-[#9CA3AF]">(Most recent)</span>
                </span>
              </div>
              <ChevronRight className="h-4 w-4 text-[#9CA3AF] flex-shrink-0" />
            </button>
            <button onClick={() => { setScreen('picker'); setDestType('engagement') }} className="text-[12px] text-[#6B7280] hover:text-brand transition-colors text-center">
              Choose a different destination...
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Screen 2: full picker with sequential reveal and live breadcrumb
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[480px] max-w-[92vw] shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Copy to...</h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand transition-colors"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 flex flex-col gap-4">
          <div className="flex items-center gap-3 p-3 rounded-[8px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
            <FileTypeIcon contentType={doc.content_type} />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] truncate">{doc.filename}</p>
              <p className="text-[11px] text-[#9CA3AF]">{formatBytes(doc.size_bytes)}</p>
            </div>
          </div>
          <p className="text-[12px] text-[#6B7280] truncate">{breadcrumb}</p>
          <div className="flex gap-2">
            <button onClick={() => setDestType('firm_library')} className={['flex-1 py-2 rounded-[6px] text-[12px] font-medium border border-[0.5px] transition-colors', destType === 'firm_library' ? 'bg-brand text-white border-brand' : 'border-surface-border dark:border-dark-border text-[#6B7280] hover:text-brand'].join(' ')}>Firm Library</button>
            <button onClick={() => setDestType('engagement')} className={['flex-1 py-2 rounded-[6px] text-[12px] font-medium border border-[0.5px] transition-colors', destType === 'engagement' ? 'bg-brand text-white border-brand' : 'border-surface-border dark:border-dark-border text-[#6B7280] hover:text-brand'].join(' ')}>Engagement</button>
          </div>
          {destType === 'firm_library' && (
            <div>
              <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">Destination folder</label>
              <select value={selectedFolderId} onChange={(e) => setSelectedFolderId(e.target.value)} className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]">
                <option value="">Firm Library root</option>
                {firmLibraryFolders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
          )}
          {destType === 'engagement' && (
            <>
              <div>
                <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">1. Select a client</label>
                <select value={selectedClientId} onChange={(e) => { const id = e.target.value; const name = clients.find((c) => c.id === id)?.name ?? ''; setSelectedClientId(id); setSelectedClientName(name); setSelectedEngagementId(''); setSelectedEngagementName(''); setSelectedEngFolderDecision(undefined); setSelectedFolderName(null) }} className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]">
                  <option value="">Select client...</option>
                  {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              {selectedClientId && (
                <div>
                  <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">2. Select an engagement</label>
                  <select value={selectedEngagementId} onChange={(e) => { const id = e.target.value; const name = engagements.find((eng) => eng.id === id)?.name ?? ''; setSelectedEngagementId(id); setSelectedEngagementName(name); setSelectedEngFolderDecision(undefined); setSelectedFolderName(null) }} className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]">
                    <option value="">Select engagement...</option>
                    {engagements.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
                  </select>
                </div>
              )}
              {selectedEngagementId && (
                <div>
                  <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">3. Select a destination folder</label>
                  {engagementFoldersLoading ? (
                    <div className="h-9 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card flex items-center px-2.5"><Loader2 className="h-3.5 w-3.5 animate-spin text-[#6B7280]" /></div>
                  ) : (
                    <select value={selectedEngFolderDecision === undefined ? '__unset__' : selectedEngFolderDecision} onChange={(e) => { const v = e.target.value; if (v === '__unset__') { setSelectedEngFolderDecision(undefined); setSelectedFolderName(null) } else { setSelectedEngFolderDecision(v); setSelectedFolderName(v === '' ? null : (engagementFolders.find((f) => f.id === v)?.name ?? null)) } }} className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0]">
                      <option value="__unset__" disabled>Choose a destination...</option>
                      <option value="">Engagement root</option>
                      {engagementFolders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                  )}
                </div>
              )}
            </>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[0.5px] border-surface-border dark:border-dark-border">
          <button onClick={onClose} className="h-8 px-3.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand transition-colors">Cancel</button>
          <button onClick={() => handlePickerCopy()} disabled={!canSubmitPicker} className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
            {copying ? 'Copying...' : 'Copy here'}
          </button>
        </div>
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
    setProgress('Uploading...')
    try {
      const urlPayload: Record<string, unknown> = {
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      }
      if (currentFolderId) urlPayload.folder_id = currentFolderId

      const { data: urlData } = await api.post('/documents/upload-url', urlPayload)
      const { document_id, upload_url } = urlData

      await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      })

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
// Draft guidance modal
// ---------------------------------------------------------------------------

function DraftGuidanceModal({
  doc,
  onCancel,
  onContinue,
}: {
  doc: FirmDoc
  onCancel: () => void
  onContinue: (doc: FirmDoc) => void
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onCancel}>
      <div
        className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[400px] max-w-[92vw] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Before you download</h2>
          <button onClick={onCancel} className="text-[#6B7280] hover:text-brand transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">
          <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">
            The file downloads to your computer. Edit it locally, then use the Upload button to add your finished version to Firm Library.
          </p>
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[0.5px] border-surface-border dark:border-dark-border">
          <button
            onClick={onCancel}
            className="h-8 px-3.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onContinue(doc)}
            className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
          >
            Continue
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
// ---------------------------------------------------------------------------
// StarterTemplatesPanel
// ---------------------------------------------------------------------------

interface StarterTemplatesPanelProps {
  seeded: boolean | null
  docs: FirmDoc[]
  loading: boolean
  seeding: boolean
  ackAccepted: boolean
  ackChecked: boolean
  onAckCheck: (v: boolean) => void
  onAckAccept: () => void
  onSeed: () => void
  onDownload: (doc: FirmDoc) => void
}

function StarterTemplatesPanel({
  seeded,
  docs,
  loading,
  seeding,
  ackAccepted,
  ackChecked,
  onAckCheck,
  onAckAccept,
  onSeed,
  onDownload,
}: StarterTemplatesPanelProps) {
  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  function cleanTemplateName(filename: string): string {
    return filename
      .replace(/^\d+_/, '')
      .replace(/\.docx$/i, '')
      .replace(/_/g, ' ')
  }

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-4 flex-1 overflow-y-auto">
        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Starter Templates</h1>
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 rounded bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // Acknowledgment gate -- shown once before the user can access this section.
  if (!ackAccepted) {
    return (
      <div className="p-6 flex flex-col gap-6 flex-1 overflow-y-auto">
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">Starter Templates</h1>
          <p className="text-[12px] text-[#6B7280]">Ready-to-customize documents for your team.</p>
        </div>
        <div className="max-w-lg rounded-[12px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card p-6 flex flex-col gap-4">
          <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF] leading-relaxed">
            I understand that these are editable starter templates, not legal or professional advice. My firm is responsible for reviewing, customizing, and approving any document before it's used with a client.
          </p>
          <label className="flex items-start gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={ackChecked}
              onChange={(e) => onAckCheck(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded accent-brand flex-shrink-0"
            />
            <span className="text-[13px] text-brand dark:text-[#EDEEF0] select-none">
              I understand and agree
            </span>
          </label>
          <button
            onClick={onAckAccept}
            disabled={!ackChecked}
            className="self-start h-9 px-4 rounded-[6px] bg-brand text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-default"
          >
            Continue
          </button>
        </div>
      </div>
    )
  }

  // Not yet seeded -- show prompt.
  if (seeded === false) {
    return (
      <div className="p-6 flex flex-col gap-6 flex-1 overflow-y-auto">
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">Starter Templates</h1>
          <p className="text-[12px] text-[#6B7280]">Ready-to-customize documents for your team.</p>
        </div>
        <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
            <Sparkles className="h-5 w-5 text-[#6B7280]" />
          </div>
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No starter templates yet</p>
          <p className="text-[12px] text-[#6B7280]">Add 8 ready-to-customize documents to get your firm started.</p>
          <button
            onClick={onSeed}
            disabled={seeding}
            className="mt-2 h-9 px-4 rounded-[6px] bg-brand text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
          >
            {seeding && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {seeding ? 'Adding...' : 'Add starter templates'}
          </button>
        </div>
      </div>
    )
  }

  // Seeded -- show the 8 vendor_sample documents.
  return (
    <div className="p-6 flex flex-col gap-4 flex-1 overflow-y-auto">
      <div>
        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">Starter Templates</h1>
        <p className="text-[12px] text-[#6B7280]">Ready-to-customize documents. Create a draft to make your own version.</p>
      </div>
      {docs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
          <p className="text-[13px] text-[#9CA3AF]">No starter templates found.</p>
        </div>
      ) : (
        <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-surface-card dark:bg-[#252525]">
                {['Name', 'Type', 'Size', '', 'Action'].map((col, i) => (
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
              {docs.map((doc, i) => (
                <tr
                  key={doc.id}
                  className={[
                    'group transition-colors bg-surface-page dark:bg-dark-page',
                    'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                    i !== docs.length - 1
                      ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                      : '',
                  ].join(' ')}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <FileTypeIcon contentType={doc.content_type} />
                      <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] truncate">{cleanTemplateName(doc.filename)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">{fileTypeLabel(doc.content_type)}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">{formatBytes(doc.size_bytes)}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center h-[18px] px-2 rounded text-[10px] font-medium bg-[#E5E7EB] dark:bg-[#2D2D2D] text-[#6B7280] dark:text-[#9CA3AF] whitespace-nowrap">
                      Sample
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => onDownload(doc)}
                      className="text-[12px] text-brand dark:text-[#EDEEF0] hover:underline"
                    >
                      Create a draft
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
// Main page
// ---------------------------------------------------------------------------

export default function FirmLibraryPage() {
  const { user, isLoading: authLoading } = useAuth()
  const router = useRouter()
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

  // Starter Templates view state
  const [view, setView] = useState<'all-files' | 'starter-templates'>('all-files')
  const [starterSeeded, setStarterSeeded] = useState<boolean | null>(null)
  const [starterDocs, setStarterDocs] = useState<FirmDoc[]>([])
  const [starterLoading, setStarterLoading] = useState(false)
  const [seeding, setSeeding] = useState(false)
  const [ackAccepted, setAckAccepted] = useState(false)
  const [ackChecked, setAckChecked] = useState(false)
  const [draftGuidanceShown, setDraftGuidanceShown] = useState(false)

  // TEMP DIAGNOSTIC -- remove after bug is traced
  console.log('[FirmLibrary render] user?.firm_id=', user?.firm_id, 'ackAccepted=', ackAccepted)

  // Read firm-specific acknowledgment from localStorage once user is available.
  useEffect(() => {
    console.log('[FirmLibrary ack effect] fired -- user?.firm_id=', user?.firm_id)
    if (user?.firm_id) {
      const key = `jamm_starter_ack_${user.firm_id}`
      const raw = localStorage.getItem(key)
      console.log('[FirmLibrary ack effect] key=', key, 'raw=', raw, 'result=', raw === '1')
      setAckAccepted(raw === '1')
      setDraftGuidanceShown(localStorage.getItem(`jamm_draft_guidance_${user.firm_id}`) === '1')
    } else {
      console.log('[FirmLibrary ack effect] user?.firm_id is falsy -- skipping localStorage read')
    }
  }, [user?.firm_id])

  // Modals
  const [copyTarget, setCopyTarget] = useState<FirmDoc | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [draftGuidanceDoc, setDraftGuidanceDoc] = useState<FirmDoc | null>(null)

  const [bulkImporting, setBulkImporting] = useState(false)
  const bulkImportRef = useRef<HTMLInputElement>(null)

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
      setDocs((data.items ?? data ?? []).filter((d: Record<string, unknown>) => d.source !== 'system'))
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
    setView('all-files')
    setCurrentFolderId(null)
    setFolderPath([])
    setSearch('')
  }

  async function handleStarterSelect() {
    setView('starter-templates')
    if (starterSeeded !== null) return
    setStarterLoading(true)
    try {
      const s = await firmLibraryApi.getStarterTemplatesStatus()
      setStarterSeeded(s.has_starter_templates)
      if (s.has_starter_templates) {
        const { data } = await api.get('/documents/', {
          params: { scope: 'firm_library', limit: 200 },
        })
        const all: FirmDoc[] = (data.items ?? data ?? []) as FirmDoc[]
        setStarterDocs(all.filter((d) => d.source === 'system'))
      }
    } catch {
      toast.error('Could not load starter templates status')
    } finally {
      setStarterLoading(false)
    }
  }

  async function handleSeedStarters() {
    setSeeding(true)
    try {
      await firmLibraryApi.seedStarterTemplates()
      toast.success('Starter templates added')
      setStarterSeeded(true)
      const { data } = await api.get('/documents/', {
        params: { scope: 'firm_library', limit: 200 },
      })
      const all: FirmDoc[] = (data.items ?? data ?? []) as FirmDoc[]
      setStarterDocs(all.filter((d) => d.source === 'system'))
    } catch {
      toast.error('Could not add starter templates')
    } finally {
      setSeeding(false)
    }
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

  async function handleDraftDownload(doc: FirmDoc) {
    // window.open on a cross-origin S3 URL ignores any download attribute and
    // saves under the stored filename. Fetch as a blob first so we can give the
    // file a "Draft - ..." name that can never collide with the vendor sample on
    // re-upload.
    try {
      const { data } = await api.get(`/documents/${doc.id}/download`)
      const url = data.url ?? data.signed_url
      if (!url) return
      const response = await fetch(url)
      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)
      const ext = doc.filename.match(/\.[^.]+$/)?.[0] ?? ''
      const base = doc.filename
        .replace(/^\d+_/, '')
        .replace(/\.[^.]+$/, '')
        .replace(/_/g, ' ')
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = `Draft - ${base}${ext}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } catch {
      toast.error('Could not generate download link')
    }
  }

  function handleCreateDraft(doc: FirmDoc) {
    if (!draftGuidanceShown) {
      setDraftGuidanceDoc(doc)
      return
    }
    handleDraftDownload(doc)
  }

  async function handleBulkImportChange(e: ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    setBulkImporting(true)
    try {
      const items = enumerateFolder(files)
      const payload: CreateImportBatchPayload = {
        scope: 'firm_library',
        conflict_policy: 'skip',
        items,
        ...(currentFolderId ? { destination_folder_id: currentFolderId } : {}),
      }
      const batch = await importBatchesApi.create(payload)
      router.push(`/firm-library/import-review?batch=${batch.id}`)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Bulk import failed -- please try again')
    } finally {
      setBulkImporting(false)
      e.target.value = ''
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

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <p className="text-[13px] text-muted-foreground text-center py-6">Loading...</p>
      </div>
    )
  }

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
              view === 'all-files'
                ? 'bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] font-medium'
                : 'text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0]',
            ].join(' ')}
            onClick={handleRootSelect}
          >
            <FolderOpen className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
            <span>All Files</span>
          </div>

          {isElevated && (
            <div
              className={[
                'flex items-center gap-2 px-3 py-1.5 rounded cursor-pointer text-[13px] transition-colors mx-1',
                view === 'starter-templates'
                  ? 'bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] font-medium'
                  : 'text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0]',
              ].join(' ')}
              onClick={handleStarterSelect}
            >
              <Sparkles className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
              <span>Starter Templates</span>
            </div>
          )}

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
        {view === 'starter-templates' ? (
          <StarterTemplatesPanel
            seeded={starterSeeded}
            docs={starterDocs}
            loading={starterLoading}
            seeding={seeding}
            ackAccepted={ackAccepted}
            ackChecked={ackChecked}
            onAckCheck={setAckChecked}
            onAckAccept={() => {
              setAckAccepted(true)
              setAckChecked(false)
              if (typeof window !== 'undefined' && user?.firm_id) localStorage.setItem(`jamm_starter_ack_${user.firm_id}`, '1')
            }}
            onSeed={handleSeedStarters}
            onDownload={handleCreateDraft}
          />
        ) : (
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
                  onClick={() => bulkImportRef.current?.click()}
                  disabled={bulkImporting}
                  className="h-9 px-3 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:text-brand hover:border-brand transition-colors flex items-center gap-1.5 whitespace-nowrap flex-shrink-0 disabled:opacity-50"
                >
                  <FolderInput className="h-4 w-4" />
                  {bulkImporting ? 'Importing...' : 'Bulk Import'}
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
        )}
      </div>

      {/* Modals */}
      {copyTarget && (
        <CopyToModal
          doc={copyTarget}
          firmLibraryFolders={allFirmFolders}
          userId={user?.id ?? ''}
          onClose={() => setCopyTarget(null)}
          onCopied={loadDocs}
        />
      )}

      <input
        ref={bulkImportRef}
        type="file"
        style={{ display: 'none' }}
        multiple
        {...({ webkitdirectory: '' } as unknown as InputHTMLAttributes<HTMLInputElement>)}
        onChange={handleBulkImportChange}
      />

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
      {draftGuidanceDoc && (
        <DraftGuidanceModal
          doc={draftGuidanceDoc}
          onCancel={() => setDraftGuidanceDoc(null)}
          onContinue={async (doc) => {
            setDraftGuidanceDoc(null)
            setDraftGuidanceShown(true)
            if (user?.firm_id) localStorage.setItem(`jamm_draft_guidance_${user.firm_id}`, '1')
            await handleDraftDownload(doc)
          }}
        />
      )}
    </div>
  )
}
