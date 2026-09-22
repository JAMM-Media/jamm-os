// frontend/src/components/documents/FolderBrowser.tsx
'use client'

import { useState, useCallback, useEffect, useLayoutEffect, useRef, useMemo, type ChangeEvent, type InputHTMLAttributes } from 'react'
import { createPortal } from 'react-dom'
import { ChevronRight, ChevronDown, ChevronUp, Folder, FolderPlus, FolderInput, Upload, X, FileText, MoreVertical, Trash2, Loader2 } from 'lucide-react'
import { fileIconFromContentType } from '@/lib/fileIcons'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { importBatchesApi, type CreateImportBatchPayload } from '@/lib/api/importBatches'
import { enumerateFolder } from '@/lib/importEnumeration'
import { documentsApi, documentFoldersApi } from '@/lib/api/documents'
import { useConfirm } from '@/lib/hooks/useConfirm'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrowserFolder {
  id: string
  name: string
  parent_folder_id: string | null
  updated_at?: string
  created_at?: string
}

interface BrowserDoc {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  folder_id: string | null
  created_at: string
  is_superseded: boolean
}

export interface FolderBrowserProps {
  scope: 'engagement' | 'client'
  engagementId?: string
  clientId?: string
  /** When true (engagement is finalized), the New Folder action is absent from the DOM. */
  isFinalized?: boolean
  /**
   * When true, a collapsible "Archived (N)" toggle appears at the bottom of the
   * file list showing is_superseded documents in the current folder. Matches
   * the client page's existing archived-docs toggle behavior.
   */
  showArchivedToggle?: boolean
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
    return ''
  }
}

function getDescendantFolderIds(folderId: string, childrenOf: Record<string, BrowserFolder[]>): Set<string> {
  const result = new Set<string>()
  const queue: string[] = [folderId]
  while (queue.length > 0) {
    const current = queue.pop()!
    for (const child of (childrenOf[current] ?? [])) {
      result.add(child.id)
      queue.push(child.id)
    }
  }
  return result
}

async function moveDocument(
  docId: string,
  targetFolderId: string | null,
  targetFolderName: string | null,
  currentFolderId: string | null,
  isFinalized: boolean | undefined,
  fetchDocs: () => void,
) {
  if (isFinalized) {
    toast.error('This engagement is finalized -- files cannot be moved')
    return
  }
  if (currentFolderId === targetFolderId) return
  try {
    await api.patch(`/documents/${docId}/move`, { folder_id: targetFolderId })
    toast.success(`Moved to ${targetFolderName ? `"${targetFolderName}"` : 'root level'}`)
    fetchDocs()
  } catch {
    toast.error('Could not move file -- please try again')
  }
}

// ---------------------------------------------------------------------------
// FlatRow: discriminated union for rows in the unified flat table.
// ---------------------------------------------------------------------------

type FlatRow =
  | { kind: 'folder'; folder: BrowserFolder; depth: number; hasChildren: boolean }
  | { kind: 'doc'; doc: BrowserDoc; depth: number }

// ---------------------------------------------------------------------------
// FlatFolderRow: one folder row in the unified flat table. Depth-based left
// indent. All business logic (move, delete, drag-drop) preserved from the
// old FolderNode exactly; only the render shape changes.
// ---------------------------------------------------------------------------

function FlatFolderRow({
  folder,
  depth,
  hasChildren,
  isExpanded,
  onToggle,
  isTargeted,
  onTarget,
  onNavigate,
  folders,
  childrenOf,
  onDropDoc,
  onFolderChanged,
  isFinalized,
}: {
  folder: BrowserFolder
  depth: number
  hasChildren: boolean
  isExpanded: boolean
  onToggle: (id: string) => void
  isTargeted: boolean
  onTarget: () => void
  onNavigate: () => void
  folders: BrowserFolder[]
  childrenOf: Record<string, BrowserFolder[]>
  onDropDoc: (docId: string, targetFolderId: string, targetFolderName: string) => void
  onFolderChanged: () => void
  isFinalized?: boolean
}) {
  const [isDragOver, setIsDragOver] = useState(false)
  const { confirm, ConfirmDialog } = useConfirm()
  const [menuOpen, setMenuOpen] = useState(false)
  const [showMoveList, setShowMoveList] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuDropdownRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)

  useLayoutEffect(() => {
    if (!menuOpen || !triggerRef.current || !menuDropdownRef.current) return
    const triggerRect = triggerRef.current.getBoundingClientRect()
    const menuHeight = menuDropdownRef.current.getBoundingClientRect().height
    const menuWidth = 176
    let top = triggerRect.bottom + 4
    let left = triggerRect.right - menuWidth
    if (top + menuHeight > window.innerHeight) top = triggerRect.top - menuHeight - 4
    if (left < 0) left = triggerRect.left
    setCoords({ top, left })
  }, [menuOpen])

  useEffect(() => {
    if (!menuOpen) return
    function handler(e: MouseEvent) {
      const inDropdown = menuDropdownRef.current?.contains(e.target as Node)
      const inTrigger = triggerRef.current?.contains(e.target as Node)
      if (!inDropdown && !inTrigger) {
        setMenuOpen(false)
        setShowMoveList(false)
        setCoords(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  async function handleMove(targetFolderId: string | null) {
    setMenuOpen(false)
    setShowMoveList(false)
    setCoords(null)
    if (isFinalized) {
      toast.error('This engagement is finalized -- folders cannot be moved')
      return
    }
    try {
      await documentFoldersApi.moveFolder(folder.id, targetFolderId)
      const name = targetFolderId
        ? (folders.find((f) => f.id === targetFolderId)?.name ?? 'folder')
        : 'root level'
      toast.success(`Moved to ${targetFolderId ? `"${name}"` : name}`)
      onFolderChanged()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not move folder -- please try again')
    }
  }

  async function handleDelete() {
    setMenuOpen(false)
    setShowMoveList(false)
    setCoords(null)
    if (isFinalized) {
      toast.error('This engagement is finalized -- folders cannot be deleted')
      return
    }
    const confirmed = await confirm({
      message: `Delete folder "${folder.name}"? Files directly inside it will also be moved to trash. Subfolders and their contents will not be affected.`,
      confirmLabel: 'Delete',
      destructive: true,
    })
    if (!confirmed) return
    try {
      await documentFoldersApi.deleteFolder(folder.id)
      toast.success('Folder deleted')
      onFolderChanged()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not delete folder -- please try again')
    }
  }

  const descendantIds = getDescendantFolderIds(folder.id, childrenOf)
  const validDestinations = folders.filter((f) => f.id !== folder.id && !descendantIds.has(f.id))

  const dropdown = (
    <div
      ref={menuDropdownRef}
      className="bg-white dark:bg-[#252525] border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] shadow-lg overflow-hidden w-44"
      style={{ position: 'fixed', zIndex: 9999, top: coords?.top ?? 0, left: coords?.left ?? 0, visibility: coords ? 'visible' : 'hidden' }}
    >
      <button
        onClick={() => setShowMoveList((v) => !v)}
        disabled={isFinalized}
        className="w-full text-left flex items-center gap-2 px-3 py-2 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
      >
        <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
        Move to Folder
      </button>
      {showMoveList && (
        <div className="border-t border-[0.5px] border-surface-border dark:border-dark-border max-h-48 overflow-y-auto">
          <button
            onClick={() => handleMove(null)}
            disabled={folder.parent_folder_id === null}
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
          >
            <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
            Root level
          </button>
          {validDestinations.map((f) => (
            <button
              key={f.id}
              onClick={() => handleMove(f.id)}
              disabled={folder.parent_folder_id === f.id}
              className="w-full text-left px-3 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default truncate"
            >
              {f.name}
            </button>
          ))}
          {validDestinations.length === 0 && (
            <p className="px-3 py-2 text-[11px] text-[#9CA3AF]">No other folders available.</p>
          )}
        </div>
      )}
      <div className="border-t border-[0.5px] border-surface-border dark:border-dark-border">
        <button
          onClick={handleDelete}
          disabled={isFinalized}
          className="w-full text-left flex items-center gap-2 px-3 py-2 text-[12px] text-[#991B1B] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
        >
          <Trash2 className="h-3.5 w-3.5 flex-shrink-0" />
          Delete
        </button>
      </div>
    </div>
  )

  return (
    <>
      <div
        className={cn(
          'group flex items-center',
          isDragOver ? 'bg-blue-50 dark:bg-blue-900/10' : isTargeted ? 'bg-surface-input dark:bg-dark-card' : '',
        )}
        style={{ paddingTop: '11px', paddingBottom: '11px', paddingLeft: `${18 + depth * 22}px`, paddingRight: '18px' }}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragOver(false)
          if (isFinalized) return
          const docId = e.dataTransfer.getData('text/plain')
          if (docId) onDropDoc(docId, folder.id, folder.name)
        }}
      >
        <div className="flex-1 flex items-center gap-[9px] min-w-0 cursor-pointer" onClick={onTarget} onDoubleClick={onNavigate}>
          {hasChildren ? (
            <button
              className="p-0 m-0 border-0 bg-transparent flex-shrink-0"
              onClick={(e) => { e.stopPropagation(); onToggle(folder.id) }}
            >
              {isExpanded
                ? <ChevronDown className="h-[13px] w-[13px] text-[#9CA3AF]" />
                : <ChevronRight className="h-[13px] w-[13px] text-[#9CA3AF]" />
              }
            </button>
          ) : (
            <span className="inline-block w-[13px] flex-shrink-0" />
          )}
          <svg width="17" height="17" viewBox="0 0 24 24" fill="#F5B942" className="flex-shrink-0" aria-hidden="true">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
          <span className="text-[13.5px] font-medium text-[#111827] dark:text-[#EDEEF0] truncate">{folder.name}</span>
        </div>
        <div className="w-[130px] flex-shrink-0 text-[12.5px] text-[#9CA3AF]">
          {formatDate(folder.updated_at ?? folder.created_at ?? '')}
        </div>
        <div className="w-6 flex-shrink-0 flex items-center justify-center">
          <button
            ref={triggerRef}
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); setShowMoveList(false); setCoords(null) }}
            className="text-[#D1D5DB] hover:text-[#6B7280] dark:hover:text-[#EDEEF0] transition-colors opacity-0 group-hover:opacity-100"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </div>
        {menuOpen && createPortal(dropdown, document.body)}
      </div>
      {ConfirmDialog}
    </>
  )
}

// ---------------------------------------------------------------------------
// New Folder modal: visual design matches Firm Library's NewFolderModal
// exactly, but parameterised for any scope.
// ---------------------------------------------------------------------------

function NewFolderModal({
  scope,
  engagementId,
  clientId,
  parentFolderId,
  onClose,
  onCreated,
}: {
  scope: 'engagement' | 'client'
  engagementId?: string
  clientId?: string
  parentFolderId: string | null
  onClose: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  async function handleCreate() {
    const trimmed = name.trim()
    if (!trimmed) return
    setCreating(true)
    try {
      const body: Record<string, unknown> = { scope, name: trimmed }
      if (engagementId) body.engagement_id = engagementId
      if (clientId) body.client_id = clientId
      if (parentFolderId) body.parent_folder_id = parentFolderId
      await api.post('/document-folders/', body)
      toast.success(`Folder "${trimmed}" created`)
      onCreated()
      onClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not create folder -- please try again')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
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
            placeholder="e.g. Workpapers"
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
// Upload modal: mirrors firm-library/page.tsx's UploadModal exactly, with
// the addition of client_id and engagement_id in both payloads so uploads
// are scoped to the correct client or engagement record.
// ---------------------------------------------------------------------------

type FileEntry = { file: File; status: 'pending' | 'uploading' | 'done' | 'failed' }

function UploadModal({
  scope,
  engagementId,
  clientId,
  currentFolderId,
  onClose,
  onUploaded,
}: {
  scope: 'engagement' | 'client'
  engagementId?: string
  clientId?: string
  currentFolderId: string | null
  onClose: () => void
  onUploaded: () => void
}) {
  const [fileList, setFileList] = useState<FileEntry[]>([])
  const [description, setDescription] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadSummary, setUploadSummary] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFilesChange(incoming: File[]) {
    setFileList(incoming.map((f) => ({ file: f, status: 'pending' })))
    setUploadSummary('')
  }

  async function handleUpload() {
    if (fileList.length === 0) return
    setUploading(true)
    setUploadSummary('')

    const entries = fileList.map((e) => ({ ...e }))
    // Seed from already-succeeded files so the final summary covers the full batch.
    let doneCount = entries.filter((e) => e.status === 'done').length

    for (let i = 0; i < entries.length; i++) {
      if (entries[i].status === 'done') continue
      entries[i].status = 'uploading'
      setFileList([...entries])

      const { file } = entries[i]
      try {
        const urlPayload: Record<string, unknown> = {
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
        }
        if (currentFolderId) urlPayload.folder_id = currentFolderId
        if (clientId) urlPayload.client_id = clientId
        if (engagementId) urlPayload.engagement_id = engagementId

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
        if (clientId) completePayload.client_id = clientId
        if (engagementId) completePayload.engagement_id = engagementId
        if (fileList.length === 1 && description.trim()) completePayload.description = description.trim()

        await api.post(`/documents/${document_id}/upload-complete`, completePayload)
        entries[i].status = 'done'
        doneCount++
      } catch {
        entries[i].status = 'failed'
      }
      setFileList([...entries])
    }

    setUploading(false)
    const total = entries.length
    const failed = total - doneCount

    if (failed === 0) {
      toast.success(total === 1 ? `"${entries[0].file.name}" uploaded` : `${total} files uploaded`)
      onUploaded()
      onClose()
    } else {
      setUploadSummary(`${doneCount} of ${total} uploaded, ${failed} failed`)
      if (doneCount > 0) {
        toast.success(`${doneCount} of ${total} files uploaded`)
        onUploaded()
      }
    }
  }

  const uploadedCount = fileList.filter((e) => e.status === 'done' || e.status === 'failed').length
  const retryCount = fileList.filter((e) => e.status === 'failed' || e.status === 'pending').length
  const isRetry = fileList.some((e) => e.status === 'done')

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-page dark:bg-dark-page rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-[480px] max-w-[92vw] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Upload Document</h2>
          <button onClick={onClose} disabled={uploading} className="text-[#6B7280] hover:text-brand transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5 flex flex-col gap-4">
          <div>
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
              Files
            </label>
            <div
              className="border border-dashed border-surface-border dark:border-dark-border rounded-[6px] p-6 text-center cursor-pointer hover:bg-surface-input dark:hover:bg-dark-card transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              {fileList.length === 0 ? (
                <>
                  <Upload className="h-6 w-6 text-[#6B7280] mx-auto mb-2" />
                  <p className="text-[13px] text-[#6B7280]">Click to select files</p>
                </>
              ) : (
                <p className="text-[13px] text-brand dark:text-[#EDEEF0]">
                  {fileList.length} {fileList.length === 1 ? 'file' : 'files'} selected -- click to change
                </p>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => handleFilesChange(Array.from(e.target.files ?? []))}
              />
            </div>
          </div>
          {fileList.length > 0 && (
            <div className="flex flex-col gap-0.5">
              {fileList.map((entry, idx) => (
                <div key={idx} className="flex items-center gap-3 px-3 py-2 rounded-[6px] bg-surface-input dark:bg-dark-card">
                  <FileText className="h-3.5 w-3.5 text-[#6B7280] shrink-0" />
                  <p className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate flex-1">{entry.file.name}</p>
                  {entry.status === 'uploading' && (
                    <Loader2 className="h-3.5 w-3.5 text-[#6B7280] animate-spin shrink-0" />
                  )}
                  {entry.status === 'done' && (
                    <span className="text-[11px] text-green-600 dark:text-green-400 shrink-0">Done</span>
                  )}
                  {entry.status === 'failed' && (
                    <span className="text-[11px] text-[#991B1B] shrink-0">Failed</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {fileList.length === 1 && (
            <div>
              <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] block mb-1.5">
                Description (optional)
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Q3 financial statements"
                className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none"
              />
            </div>
          )}
          {uploadSummary && (
            <p className="text-[12px] text-[#991B1B]">{uploadSummary}</p>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[0.5px] border-surface-border dark:border-dark-border">
          <button
            onClick={onClose}
            disabled={uploading}
            className="h-8 px-3.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={fileList.length === 0 || uploading}
            className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {uploading
              ? `${uploadedCount} / ${fileList.length}`
              : isRetry
              ? `Retry ${retryCount} failed`
              : fileList.length > 1
              ? `Upload ${fileList.length} files`
              : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// FlatDocRow: one document row in the unified flat table. Depth-based left
// indent. All business logic (move, delete, drag) preserved from the old
// DocRow exactly; only the render shape changes.
// ---------------------------------------------------------------------------

function FlatDocRow({
  doc,
  depth,
  folders,
  fetchDocs,
  isFinalized,
}: {
  doc: BrowserDoc
  depth: number
  folders: BrowserFolder[]
  fetchDocs: () => void
  isFinalized?: boolean
}) {
  const { confirm, ConfirmDialog } = useConfirm()
  const [menuOpen, setMenuOpen] = useState(false)
  const [showMoveList, setShowMoveList] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuDropdownRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  useLayoutEffect(() => {
    if (!menuOpen || !triggerRef.current || !menuDropdownRef.current) return
    const triggerRect = triggerRef.current.getBoundingClientRect()
    const menuHeight = menuDropdownRef.current.getBoundingClientRect().height
    const menuWidth = 176
    let top = triggerRect.bottom + 4
    let left = triggerRect.right - menuWidth
    if (top + menuHeight > window.innerHeight) top = triggerRect.top - menuHeight - 4
    if (left < 0) left = triggerRect.left
    setCoords({ top, left })
  }, [menuOpen])

  useEffect(() => {
    if (!menuOpen) return
    function handler(e: MouseEvent) {
      const inDropdown = menuDropdownRef.current?.contains(e.target as Node)
      const inTrigger = triggerRef.current?.contains(e.target as Node)
      if (!inDropdown && !inTrigger) {
        setMenuOpen(false)
        setShowMoveList(false)
        setCoords(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  async function handleDelete() {
    setMenuOpen(false)
    setShowMoveList(false)
    setCoords(null)
    if (isFinalized) {
      toast.error('This engagement is finalized -- files cannot be deleted')
      return
    }
    const confirmed = await confirm({
      message: `Delete "${doc.filename}"? This will move the file to trash.`,
      confirmLabel: 'Delete',
      destructive: true,
    })
    if (!confirmed) return
    try {
      await documentsApi.deleteDocument(doc.id)
      toast.success('File deleted')
      fetchDocs()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not delete file -- please try again')
    }
  }

  async function handleMove(targetFolderId: string | null) {
    setMenuOpen(false)
    setShowMoveList(false)
    setCoords(null)
    const targetName = targetFolderId
      ? (folders.find((f) => f.id === targetFolderId)?.name ?? 'folder')
      : null
    await moveDocument(doc.id, targetFolderId, targetName, doc.folder_id, isFinalized, fetchDocs)
  }

  const dropdown = (
    <div
      ref={menuDropdownRef}
      className="bg-white dark:bg-[#252525] border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] shadow-lg overflow-hidden w-44"
      style={{ position: 'fixed', zIndex: 9999, top: coords?.top ?? 0, left: coords?.left ?? 0, visibility: coords ? 'visible' : 'hidden' }}
    >
      <button
        onClick={() => setShowMoveList((v) => !v)}
        disabled={isFinalized}
        className="w-full text-left flex items-center gap-2 px-3 py-2 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
      >
        <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
        Move to Folder
      </button>
      {showMoveList && (
        <div className="border-t border-[0.5px] border-surface-border dark:border-dark-border max-h-48 overflow-y-auto">
          <button
            onClick={() => handleMove(null)}
            disabled={doc.folder_id === null}
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
          >
            <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
            Root level
          </button>
          {folders.map((f) => (
            <button
              key={f.id}
              onClick={() => handleMove(f.id)}
              disabled={doc.folder_id === f.id}
              className="w-full text-left px-3 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default truncate"
            >
              {f.name}
            </button>
          ))}
          {folders.length === 0 && (
            <p className="px-3 py-2 text-[11px] text-[#9CA3AF]">No folders yet.</p>
          )}
        </div>
      )}
      <div className="border-t border-[0.5px] border-surface-border dark:border-dark-border">
        <button
          onClick={handleDelete}
          disabled={isFinalized}
          className="w-full text-left flex items-center gap-2 px-3 py-2 text-[12px] text-[#991B1B] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
        >
          <Trash2 className="h-3.5 w-3.5 flex-shrink-0" />
          Delete
        </button>
      </div>
    </div>
  )

  return (
    <>
      <div
        draggable="true"
        onDragStart={(e) => { e.dataTransfer.setData('text/plain', doc.id); setIsDragging(true) }}
        onDragEnd={() => setIsDragging(false)}
        className={cn('group flex items-center', isDragging && 'opacity-50', doc.is_superseded && 'opacity-60')}
        style={{ paddingTop: '11px', paddingBottom: '11px', paddingLeft: `${18 + depth * 22}px`, paddingRight: '18px' }}
      >
        <div className="flex-1 flex items-center gap-[9px] min-w-0">
          {fileIconFromContentType(doc.content_type)}
          <span className="text-[13.5px] font-medium text-[#111827] dark:text-[#EDEEF0] truncate">{doc.filename}</span>
        </div>
        <div className="w-[130px] flex-shrink-0 text-[12.5px] text-[#9CA3AF]">
          {doc.created_at ? formatDate(doc.created_at) : ''}
        </div>
        <div className="w-6 flex-shrink-0 flex items-center justify-center">
          <button
            ref={triggerRef}
            onClick={() => { setMenuOpen((v) => !v); setShowMoveList(false); setCoords(null) }}
            className="text-[#D1D5DB] hover:text-[#6B7280] dark:hover:text-[#EDEEF0] transition-colors opacity-0 group-hover:opacity-100"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </div>
        {menuOpen && createPortal(dropdown, document.body)}
      </div>
      {ConfirmDialog}
    </>
  )
}

// ---------------------------------------------------------------------------
// Main FolderBrowser component
// ---------------------------------------------------------------------------

export function FolderBrowser({
  scope,
  engagementId,
  clientId,
  isFinalized,
  showArchivedToggle,
}: FolderBrowserProps) {
  const router = useRouter()
  const [folders, setFolders] = useState<BrowserFolder[]>([])
  const [foldersLoading, setFoldersLoading] = useState(true)
  const [docs, setDocs] = useState<BrowserDoc[]>([])
  const [expandedFolderIds, setExpandedFolderIds] = useState<Set<string>>(new Set())
  const [targetFolderId, setTargetFolderId] = useState<string | null>(null)
  const [navigationRootId, setNavigationRootId] = useState<string | null>(null)
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [bulkImporting, setBulkImporting] = useState(false)
  const bulkImportRef = useRef<HTMLInputElement>(null)
  const [showArchived, setShowArchived] = useState(false)

  // childrenOf map: used both for visibleRows and passed to FlatFolderRow for
  // the cycle-exclusion check in the destination picker.
  const childrenOf: Record<string, BrowserFolder[]> = {}
  for (const f of folders) {
    const key = f.parent_folder_id ?? '__root__'
    if (!childrenOf[key]) childrenOf[key] = []
    childrenOf[key].push(f)
  }

  // Breadcrumb path from true root to the currently navigated folder.
  const navigationPath: BrowserFolder[] = []
  if (navigationRootId) {
    const folderById: Record<string, BrowserFolder> = {}
    for (const f of folders) folderById[f.id] = f
    let current: BrowserFolder | undefined = folderById[navigationRootId]
    while (current) {
      navigationPath.unshift(current)
      current = current.parent_folder_id ? folderById[current.parent_folder_id] : undefined
    }
  }

  // Effective folder for Upload/New Folder/bulk import:
  // (1) a row was single-clicked (targetFolderId), else
  // (2) the folder being viewed (navigationRootId), else
  // (3) true root (null).
  const effectiveFolderId = targetFolderId ?? navigationRootId

  // Flat ordered row array for the table. Scoped to navigationRootId when set,
  // otherwise walks from true root.
  const visibleRows = useMemo<FlatRow[]>(() => {
    const localChildrenOf: Record<string, BrowserFolder[]> = {}
    for (const f of folders) {
      const key = f.parent_folder_id ?? '__root__'
      if (!localChildrenOf[key]) localChildrenOf[key] = []
      localChildrenOf[key].push(f)
    }
    const localRootFolders = localChildrenOf['__root__'] ?? []

    const shown = showArchived ? docs : docs.filter((d) => !d.is_superseded)
    const rows: FlatRow[] = []

    function addFolder(folder: BrowserFolder, depth: number) {
      const children = localChildrenOf[folder.id] ?? []
      const docsHere = shown.filter((d) => d.folder_id === folder.id)
      const hasChildren = children.length > 0 || docsHere.length > 0
      rows.push({ kind: 'folder', folder, depth, hasChildren })
      if (expandedFolderIds.has(folder.id)) {
        for (const child of children) addFolder(child, depth + 1)
        for (const doc of docsHere) rows.push({ kind: 'doc', doc, depth: depth + 1 })
      }
    }

    const startFolders = navigationRootId
      ? (localChildrenOf[navigationRootId] ?? [])
      : localRootFolders
    for (const f of startFolders) addFolder(f, 0)
    const rootDocs = shown.filter((d) => d.folder_id === navigationRootId)
    for (const doc of rootDocs) rows.push({ kind: 'doc', doc, depth: 0 })
    return rows
  }, [folders, docs, expandedFolderIds, showArchived, navigationRootId])

  const fetchFolders = useCallback(async () => {
    setFoldersLoading(true)
    try {
      const params: Record<string, string> = { scope }
      if (engagementId) params.engagement_id = engagementId
      if (clientId) params.client_id = clientId
      const { data } = await api.get('/document-folders/', { params })
      setFolders(Array.isArray(data) ? data : [])
    } catch {
      setFolders([])
    } finally {
      setFoldersLoading(false)
    }
  }, [scope, engagementId, clientId])

  const fetchDocs = useCallback(async () => {
    try {
      const params: Record<string, unknown> = { scope, limit: 200 }
      if (engagementId) params.engagement_id = engagementId
      if (clientId) params.client_id = clientId
      const { data } = await api.get('/documents/', { params })
      const items = data.items ?? data ?? []
      setDocs(
        items
          .filter((d: Record<string, unknown>) => !d.deleted_at)
          .map((d: Record<string, unknown>) => ({
            id: String(d.id),
            filename: String(d.filename ?? d.name ?? ''),
            content_type: String(d.content_type ?? ''),
            size_bytes: Number(d.size_bytes ?? 0),
            folder_id: d.folder_id ? String(d.folder_id) : null,
            created_at: String(d.created_at ?? ''),
            is_superseded: Boolean(d.is_superseded ?? false),
          })),
      )
    } catch {
      setDocs([])
    }
  }, [scope, engagementId, clientId])

  useEffect(() => {
    fetchFolders()
    fetchDocs()
  }, [fetchFolders, fetchDocs])

  function toggleFolder(id: string) {
    setExpandedFolderIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function moveDoc(docId: string, targetFolderId: string | null, targetFolderName: string | null) {
    const doc = docs.find((d) => d.id === docId)
    if (!doc) return
    await moveDocument(docId, targetFolderId, targetFolderName, doc.folder_id, isFinalized, fetchDocs)
  }

  function handleFolderCreated() {
    fetchFolders()
  }

  async function handleBulkImportChange(e: ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    setBulkImporting(true)
    try {
      const items = enumerateFolder(files)
      const payload: CreateImportBatchPayload = {
        scope,
        conflict_policy: 'skip',
        items,
      }
      if (engagementId) payload.engagement_id = engagementId
      if (clientId) payload.client_id = clientId
      if (effectiveFolderId) payload.destination_folder_id = effectiveFolderId
      const batch = await importBatchesApi.create(payload)
      const reviewPath = scope === 'engagement'
        ? `/engagements/${engagementId}/import-review?batch=${batch.id}`
        : `/clients/${clientId}/import-review?batch=${batch.id}`
      router.push(reviewPath)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Bulk import failed -- please try again')
    } finally {
      setBulkImporting(false)
      e.target.value = ''
    }
  }

  if (foldersLoading) {
    return (
      <div className="mt-4">
        <div className="rounded-[12px] border border-[#E5E7EB] dark:border-[#484848] bg-white dark:bg-[#252525] overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.05)]">
          <div className="flex items-center px-[18px] py-[10px] border-b border-[#F3F4F6] dark:border-[#333]">
            <div className="flex-1 h-3 bg-[#E4E6EA] dark:bg-[#2D2D2D] animate-pulse rounded" />
          </div>
          <div className="p-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-9 bg-[#E4E6EA] dark:bg-[#2D2D2D] animate-pulse rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4">
      {/* Header: title, subtitle, action buttons */}
      <div className="flex items-start justify-between mb-[18px]">
        <div>
          <h2 className="text-[17px] font-semibold text-[#111827] dark:text-[#EDEEF0] mb-[3px]">Documents</h2>
          <p className="text-[12.5px] text-[#6B7280]">
            {scope === 'engagement'
              ? 'Where all engagement files live, including files approved from client uploads.'
              : 'Permanent files for this client, kept separate from any single engagement.'}
          </p>
        </div>
        {!isFinalized && (
          <div className="flex items-center gap-2 flex-shrink-0 ml-4">
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-[5px] bg-white dark:bg-[#252525] border border-[#E5E7EB] dark:border-[#484848] rounded-[8px] text-[#374151] dark:text-[#EDEEF0] text-[12.5px] font-medium px-[14px] py-[7px] shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:bg-[#F9FAFB] dark:hover:bg-[#2D2D2D] transition-colors"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload
            </button>
            <button
              onClick={() => setShowNewFolder(true)}
              className="flex items-center gap-[5px] bg-white dark:bg-[#252525] border border-[#E5E7EB] dark:border-[#484848] rounded-[8px] text-[#374151] dark:text-[#EDEEF0] text-[12.5px] font-medium px-[14px] py-[7px] shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:bg-[#F9FAFB] dark:hover:bg-[#2D2D2D] transition-colors"
            >
              <FolderPlus className="h-3.5 w-3.5" />
              New Folder
            </button>
            <button
              onClick={() => bulkImportRef.current?.click()}
              disabled={bulkImporting}
              className="flex items-center gap-[5px] bg-[#1F3148] dark:bg-brand-btn rounded-[8px] text-white text-[12.5px] font-medium px-[14px] py-[7px] hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <FolderInput className="h-3.5 w-3.5" />
              {bulkImporting ? 'Importing...' : 'Bulk Import'}
            </button>
          </div>
        )}
      </div>

      {/* Navigation breadcrumb -- visible when navigated into a subfolder */}
      {navigationRootId && (
        <nav className="flex items-center gap-1.5 text-[13px] mb-3">
          <button
            onClick={() => { setNavigationRootId(null); setTargetFolderId(null); setExpandedFolderIds(new Set()) }}
            className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            All
          </button>
          {navigationPath.map((folder, i) => (
            <span key={folder.id} className="flex items-center gap-1.5">
              <span className="text-[#9CA3AF]">/</span>
              {i < navigationPath.length - 1 ? (
                <button
                  onClick={() => { setNavigationRootId(folder.id); setTargetFolderId(null); setExpandedFolderIds(new Set()) }}
                  className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
                >
                  {folder.name}
                </button>
              ) : (
                <span className="text-brand dark:text-[#EDEEF0] font-medium">{folder.name}</span>
              )}
            </span>
          ))}
        </nav>
      )}

      {/* Flat table card */}
      <div className="rounded-[12px] border border-[#E5E7EB] dark:border-[#484848] bg-white dark:bg-[#252525] overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.05)]">
        {/* Column headers */}
        <div className="flex items-center px-[18px] py-[10px] border-b border-[#F3F4F6] dark:border-[#333]">
          <div className="flex-1 text-[11px] font-semibold tracking-[0.04em] text-[#9CA3AF] uppercase">Name</div>
          <div className="w-[130px] flex-shrink-0 text-[11px] font-semibold tracking-[0.04em] text-[#9CA3AF] uppercase">Updated</div>
          <div className="w-6 flex-shrink-0" />
        </div>

        {/* Rows */}
        {visibleRows.length === 0 ? (
          <p className="px-[18px] py-3 text-[12px] text-[#9CA3AF]">
            {isFinalized ? 'This engagement is finalized.' : navigationRootId ? 'This folder is empty.' : 'No files or folders yet.'}
          </p>
        ) : (
          visibleRows.flatMap((row, i) => {
            const key = row.kind === 'folder' ? `folder-${row.folder.id}` : `doc-${row.doc.id}`
            const divider = i > 0
              ? <div key={`div-${key}`} className="h-px bg-[#F9FAFB] dark:bg-[#333] mx-[18px]" />
              : null
            const rowEl = row.kind === 'folder'
              ? (
                <FlatFolderRow
                  key={key}
                  folder={row.folder}
                  depth={row.depth}
                  hasChildren={row.hasChildren}
                  isExpanded={expandedFolderIds.has(row.folder.id)}
                  onToggle={toggleFolder}
                  isTargeted={targetFolderId === row.folder.id}
                  onTarget={() => setTargetFolderId((prev) => (prev === row.folder.id ? null : row.folder.id))}
                  onNavigate={() => { setNavigationRootId(row.folder.id); setTargetFolderId(null); setExpandedFolderIds(new Set()) }}
                  folders={folders}
                  childrenOf={childrenOf}
                  onDropDoc={moveDoc}
                  onFolderChanged={() => { fetchFolders(); fetchDocs() }}
                  isFinalized={isFinalized}
                />
              )
              : (
                <FlatDocRow
                  key={key}
                  doc={row.doc}
                  depth={row.depth}
                  folders={folders}
                  fetchDocs={fetchDocs}
                  isFinalized={isFinalized}
                />
              )
            return divider ? [divider, rowEl] : [rowEl]
          })
        )}

        {/* Archived toggle */}
        {showArchivedToggle && docs.some((d) => d.is_superseded) && (
          <div className="flex items-center gap-2 px-[18px] py-[10px] border-t border-[#F3F4F6] dark:border-[#333]">
            <span className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">
              Archived ({docs.filter((d) => d.is_superseded).length})
            </span>
            <button
              onClick={() => setShowArchived((v) => !v)}
              className="p-0.5 rounded text-[#9CA3AF] hover:text-brand transition-colors"
            >
              {showArchived
                ? <ChevronUp className="h-3.5 w-3.5" />
                : <ChevronDown className="h-3.5 w-3.5" />
              }
            </button>
          </div>
        )}
      </div>

      {showNewFolder && (
        <NewFolderModal
          scope={scope}
          engagementId={engagementId}
          clientId={clientId}
          parentFolderId={effectiveFolderId}
          onClose={() => setShowNewFolder(false)}
          onCreated={handleFolderCreated}
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
          scope={scope}
          engagementId={engagementId}
          clientId={clientId}
          currentFolderId={effectiveFolderId}
          onClose={() => setShowUpload(false)}
          onUploaded={fetchDocs}
        />
      )}
    </div>
  )
}
