// frontend/src/components/documents/FolderBrowser.tsx
'use client'

import { useState, useCallback, useEffect, useLayoutEffect, useRef, type ChangeEvent, type InputHTMLAttributes } from 'react'
import { createPortal } from 'react-dom'
import { ChevronRight, ChevronDown, ChevronUp, Folder, FolderOpen, FolderPlus, FolderInput, Upload, X, FileText, MoreVertical, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { importBatchesApi, type CreateImportBatchPayload } from '@/lib/api/importBatches'
import { enumerateFolder } from '@/lib/importEnumeration'
import { documentsApi } from '@/lib/api/documents'
import { useConfirm } from '@/lib/hooks/useConfirm'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrowserFolder {
  id: string
  name: string
  parent_folder_id: string | null
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

// ---------------------------------------------------------------------------
// FolderNode: renders one folder row and its children from a pre-built map.
// Built from scratch to match Firm Library's visual design but parameterised
// for any scope (no hardcoded 'firm_library').
// ---------------------------------------------------------------------------

function FolderNode({
  folder,
  depth,
  selectedId,
  onSelect,
  childrenOf,
  onDropDoc,
}: {
  folder: BrowserFolder
  depth: number
  selectedId: string | null
  onSelect: (f: BrowserFolder) => void
  childrenOf: Record<string, BrowserFolder[]>
  onDropDoc: (docId: string) => void
}) {
  const children = childrenOf[folder.id] ?? []
  const hasChildren = children.length > 0
  const [expanded, setExpanded] = useState(depth === 0)
  const isSelected = selectedId === folder.id
  const [isDragOver, setIsDragOver] = useState(false)

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-[13px] transition-colors select-none',
          isSelected
            ? 'bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] font-medium'
            : 'text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0]',
          isDragOver && 'ring-2 ring-inset ring-brand',
        )}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
        onClick={() => onSelect(folder)}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragOver(false)
          const docId = e.dataTransfer.getData('text/plain')
          if (docId) onDropDoc(docId)
        }}
      >
        {hasChildren ? (
          <button
            className="p-0 m-0 border-0 bg-transparent flex-shrink-0"
            onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v) }}
          >
            {expanded
              ? <ChevronDown className="h-3 w-3 text-[#6B7280]" />
              : <ChevronRight className="h-3 w-3 text-[#6B7280]" />
            }
          </button>
        ) : (
          <span className="w-3 flex-shrink-0" />
        )}
        {expanded && hasChildren
          ? <FolderOpen className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
          : <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
        }
        <span className="truncate">{folder.name}</span>
      </div>
      {expanded && children.map((child) => (
        <FolderNode
          key={child.id}
          folder={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
          childrenOf={childrenOf}
          onDropDoc={onDropDoc}
        />
      ))}
    </div>
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
      if (description.trim()) completePayload.description = description.trim()

      await api.post(`/documents/${document_id}/upload-complete`, completePayload)
      toast.success(`"${file.name}" uploaded`)
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
          <h2 className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">Upload Document</h2>
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
              placeholder="e.g. Q3 financial statements"
              className="w-full h-9 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none"
            />
          </div>
          {progress && (
            <p className="text-[12px] text-[#6B7280]">{progress}</p>
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
            disabled={!file || uploading}
            className="h-8 px-3.5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {uploading ? progress || 'Uploading...' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DocRow: single file row, shared between active and archived lists.
// Accepts folders and fetchDocs from the parent FolderBrowser so the
// three-dot move menu can list real folders and refresh after a move.
// ---------------------------------------------------------------------------

function DocRow({
  doc,
  borderBottom,
  folders,
  fetchDocs,
  isFinalized,
}: {
  doc: BrowserDoc
  borderBottom: boolean
  folders: BrowserFolder[]
  fetchDocs: () => void
  isFinalized?: boolean
}) {
  const { confirm, ConfirmDialog } = useConfirm()
  const [menuOpen, setMenuOpen] = useState(false)
  const [showMoveList, setShowMoveList] = useState(false)
  // triggerRef: the three-dot button itself, used for position measurement.
  const triggerRef = useRef<HTMLButtonElement>(null)
  // menuDropdownRef: the portaled dropdown rendered in document.body.
  const menuDropdownRef = useRef<HTMLDivElement>(null)
  // Pixel coordinates for position:fixed placement. null until measured.
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  // Local drag state: only this row dims while it is being dragged.
  const [isDragging, setIsDragging] = useState(false)

  // Measure the trigger button's real screen position and compute where to
  // open the dropdown, mirroring the ColorPicker portal pattern. Menu width
  // is w-44 = 176px. Default: open below and right-aligned to the button.
  // Flip upward if the bottom edge would overflow the viewport.
  // Flip rightward if the left edge would go off-screen.
  useLayoutEffect(() => {
    if (!menuOpen || !triggerRef.current || !menuDropdownRef.current) return
    const triggerRect = triggerRef.current.getBoundingClientRect()
    const menuHeight = menuDropdownRef.current.getBoundingClientRect().height
    const menuWidth = 176

    let top = triggerRect.bottom + 4
    let left = triggerRect.right - menuWidth

    if (top + menuHeight > window.innerHeight) {
      top = triggerRect.top - menuHeight - 4
    }
    if (left < 0) {
      left = triggerRect.left
    }

    setCoords({ top, left })
  }, [menuOpen])

  // Outside-click-to-close. Both refs must be checked: menuDropdownRef covers
  // clicks inside the portaled menu content, and triggerRef covers the button
  // itself so that clicking the button while the menu is open does not
  // double-fire (outside-click close + button toggle reopen).
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
    if (isFinalized) {
      toast.error('This engagement is finalized -- files cannot be moved')
      return
    }
    try {
      await api.patch(`/documents/${doc.id}/move`, { folder_id: targetFolderId })
      const name = targetFolderId
        ? (folders.find((f) => f.id === targetFolderId)?.name ?? 'folder')
        : 'root level'
      toast.success(`Moved to ${targetFolderId ? `"${name}"` : name}`)
      fetchDocs()
    } catch {
      toast.error('Could not move file -- please try again')
    }
  }

  const dropdown = (
    <div
      ref={menuDropdownRef}
      className="bg-white dark:bg-[#252525] border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] shadow-lg overflow-hidden w-44"
      style={{
        position: 'fixed',
        zIndex: 9999,
        top: coords?.top ?? 0,
        left: coords?.left ?? 0,
        visibility: coords ? 'visible' : 'hidden',
      }}
    >
      {/* Primary action */}
      <button
        onClick={() => setShowMoveList((v) => !v)}
        disabled={isFinalized}
        className="w-full text-left flex items-center gap-2 px-3 py-2 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
      >
        <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
        Move to Folder
      </button>

      {/* Folder list -- shown when "Move to Folder" is clicked */}
      {showMoveList && (
        <div className="border-t border-[0.5px] border-surface-border dark:border-dark-border max-h-48 overflow-y-auto">
          {/* Root option: disabled when doc is already at root */}
          <button
            onClick={() => handleMove(null)}
            disabled={doc.folder_id === null}
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-input dark:hover:bg-dark-card transition-colors disabled:opacity-40 disabled:cursor-default"
          >
            <Folder className="h-3.5 w-3.5 text-[#6B7280] flex-shrink-0" />
            Root level
          </button>
          {folders.map((f) => (
            /* Each folder option: disabled when doc is already in this folder */
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

      {/* Delete -- destructive action, separated from the move section */}
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
      className={cn(
        'group flex items-center gap-3 px-3 py-2.5',
        borderBottom ? 'border-b border-[0.5px] border-[#E5E7EB] dark:border-[#333]' : '',
        isDragging && 'opacity-50',
      )}
    >
      <FileText className="h-4 w-4 text-[#6B7280] flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate">{doc.filename}</p>
        <p className="text-[11px] text-[#9CA3AF]">
          {formatBytes(doc.size_bytes)}{doc.created_at ? ` · ${formatDate(doc.created_at)}` : ''}
        </p>
      </div>

      {/* Three-dot trigger button -- hover-reveal, matching this file's hover-action pattern */}
      <button
        ref={triggerRef}
        onClick={() => { setMenuOpen((v) => !v); setShowMoveList(false); setCoords(null) }}
        className="p-1 rounded text-[#9CA3AF] hover:text-[#6B7280] dark:hover:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
      >
        <MoreVertical className="h-3.5 w-3.5" />
      </button>

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
  const [docsLoading, setDocsLoading] = useState(true)
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [folderPath, setFolderPath] = useState<{ id: string; name: string }[]>([])
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [bulkImporting, setBulkImporting] = useState(false)
  const bulkImportRef = useRef<HTMLInputElement>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [rootDragOver, setRootDragOver] = useState(false)

  // Build a folder lookup map for path resolution
  const folderById: Record<string, BrowserFolder> = {}
  for (const f of folders) folderById[f.id] = f

  // Build children map for tree rendering
  const childrenOf: Record<string, BrowserFolder[]> = {}
  for (const f of folders) {
    const key = f.parent_folder_id ?? '__root__'
    if (!childrenOf[key]) childrenOf[key] = []
    childrenOf[key].push(f)
  }
  const rootFolders = childrenOf['__root__'] ?? []

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
    setDocsLoading(true)
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
    } finally {
      setDocsLoading(false)
    }
  }, [scope, engagementId, clientId])

  useEffect(() => {
    fetchFolders()
    fetchDocs()
  }, [fetchFolders, fetchDocs])

  function handleSelectFolder(f: BrowserFolder) {
    setSelectedFolderId(f.id)
    setShowArchived(false)
    // Build breadcrumb path by walking parent chain
    const path: { id: string; name: string }[] = []
    let current: BrowserFolder | undefined = f
    while (current) {
      path.unshift({ id: current.id, name: current.name })
      current = current.parent_folder_id ? folderById[current.parent_folder_id] : undefined
    }
    setFolderPath(path)
  }

  function handleSelectRoot() {
    setSelectedFolderId(null)
    setFolderPath([])
    setShowArchived(false)
  }

  // Shared move logic for drag-and-drop. DocRow's three-dot menu uses its own
  // handleMove (has all context locally); drag targets use this lifted version
  // so the API call, toasts, and refresh are not duplicated across drop sites.
  async function moveDoc(docId: string, targetFolderId: string | null, targetFolderName: string | null) {
    if (isFinalized) {
      toast.error('This engagement is finalized -- files cannot be moved')
      return
    }
    const doc = docs.find((d) => d.id === docId)
    if (!doc) return
    if (doc.folder_id === targetFolderId) return
    try {
      await api.patch(`/documents/${docId}/move`, { folder_id: targetFolderId })
      toast.success(`Moved to ${targetFolderName ? `"${targetFolderName}"` : 'root level'}`)
      fetchDocs()
    } catch {
      toast.error('Could not move file -- please try again')
    }
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
      if (selectedFolderId) payload.destination_folder_id = selectedFolderId
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

  // Files in the currently selected folder (or root files when null)
  const docsInCurrentFolder = docs.filter((d) => d.folder_id === selectedFolderId)
  const activeDocs = docsInCurrentFolder.filter((d) => !d.is_superseded)
  const archivedDocs = docsInCurrentFolder.filter((d) => d.is_superseded)

  if (foldersLoading) {
    return (
      <div className="mt-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">Folders</span>
        </div>
        <p className="text-[12px] text-[#6B7280] mb-3">{scope === 'engagement' ? 'Where all engagement files live, including files approved from client uploads.' : 'Permanent files for this client, kept separate from any single engagement.'}</p>
        <div className="rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-3 space-y-1.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-7 bg-[#E4E6EA] dark:bg-[#2D2D2D] animate-pulse rounded" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="mt-4">
      {/* Section header with New Folder button */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">Folders</span>
        {/* Upload and New Folder buttons are absent (not disabled) when the engagement is finalized */}
        {!isFinalized && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-1.5 h-7 px-2.5 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:border-brand dark:hover:border-[#4A7FA5] transition-colors"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload
            </button>
            <button
              onClick={() => setShowNewFolder(true)}
              className="flex items-center gap-1.5 h-7 px-2.5 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:border-brand dark:hover:border-[#4A7FA5] transition-colors"
            >
              <FolderPlus className="h-3.5 w-3.5" />
              New Folder
            </button>
            <button
              onClick={() => bulkImportRef.current?.click()}
              disabled={bulkImporting}
              className="flex items-center gap-1.5 h-7 px-2.5 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:border-brand dark:hover:border-[#4A7FA5] transition-colors disabled:opacity-50"
            >
              <FolderInput className="h-3.5 w-3.5" />
              {bulkImporting ? 'Importing...' : 'Bulk Import'}
            </button>
          </div>
        )}
      </div>
      <p className="text-[12px] text-[#6B7280] mb-3">{scope === 'engagement' ? 'Where all engagement files live, including files approved from client uploads.' : 'Permanent files for this client, kept separate from any single engagement.'}</p>

      {rootFolders.length === 0 ? (
        /* No folders exist: show a minimal empty state with just the file list */
        <div className="rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] overflow-hidden">
          <div className={cn(
            'px-3 py-2',
            isFinalized
              ? 'bg-amber-100 dark:bg-amber-900/30'
              : 'bg-[#E4E6EA] dark:bg-[#2D2D2D]',
          )}>
            <p className={cn(
              'text-[12px]',
              isFinalized
                ? 'font-medium text-amber-700 dark:text-amber-400'
                : 'text-[#9CA3AF]',
            )}>
              {isFinalized
                ? 'This engagement is finalized -- no new folders can be created.'
                : 'No folders yet. Click "New Folder" to create one.'}
            </p>
          </div>
          {renderFilePanel(activeDocs, archivedDocs, docsLoading)}
        </div>
      ) : (
        <div className="rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] overflow-hidden">
          {/* Folder tree */}
          <div className="bg-[#E4E6EA] dark:bg-[#2D2D2D] p-2">
            <div
              className={cn(
                'flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-[13px] transition-colors select-none',
                selectedFolderId === null
                  ? 'bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] font-medium'
                  : 'text-[#6B7280] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0]',
                rootDragOver && 'ring-2 ring-inset ring-brand',
              )}
              onClick={handleSelectRoot}
              onDragOver={(e) => { e.preventDefault(); setRootDragOver(true) }}
              onDragLeave={() => setRootDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setRootDragOver(false)
                if (isFinalized) return
                const docId = e.dataTransfer.getData('text/plain')
                if (docId) moveDoc(docId, null, null)
              }}
            >
              <Folder className="h-3.5 w-3.5 flex-shrink-0" />
              <span>All folders</span>
            </div>
            {rootFolders.map((f) => (
              <FolderNode
                key={f.id}
                folder={f}
                depth={1}
                selectedId={selectedFolderId}
                onSelect={handleSelectFolder}
                childrenOf={childrenOf}
                onDropDoc={(docId) => moveDoc(docId, f.id, f.name)}
              />
            ))}
          </div>

          {/* Breadcrumb path for selected folder */}
          {folderPath.length > 0 && (
            <div className="flex items-center gap-1 px-3 py-2 border-t border-[0.5px] border-[#D5D8DE] dark:border-[#383838] bg-white dark:bg-[#252525] flex-wrap">
              <button
                onClick={handleSelectRoot}
                className="text-[11px] text-[#9CA3AF] hover:text-brand transition-colors"
              >
                All
              </button>
              {folderPath.map((seg, i) => (
                <span key={seg.id} className="flex items-center gap-1">
                  <ChevronRight className="h-3 w-3 text-[#9CA3AF]" />
                  {i < folderPath.length - 1 ? (
                    <button
                      onClick={() => {
                        const f = folderById[seg.id]
                        if (f) handleSelectFolder(f)
                      }}
                      className="text-[11px] text-[#9CA3AF] hover:text-brand transition-colors"
                    >
                      {seg.name}
                    </button>
                  ) : (
                    <span className="text-[11px] font-medium text-brand dark:text-[#EDEEF0]">{seg.name}</span>
                  )}
                </span>
              ))}
            </div>
          )}

          {renderFilePanel(activeDocs, archivedDocs, docsLoading)}
        </div>
      )}

      {showNewFolder && (
        <NewFolderModal
          scope={scope}
          engagementId={engagementId}
          clientId={clientId}
          parentFolderId={selectedFolderId}
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
          currentFolderId={selectedFolderId}
          onClose={() => setShowUpload(false)}
          onUploaded={fetchDocs}
        />
      )}
    </div>
  )

  // Render the file list panel (active docs + optional archived toggle)
  function renderFilePanel(
    active: BrowserDoc[],
    archived: BrowserDoc[],
    loading: boolean,
  ) {
    return (
      <div className="bg-white dark:bg-[#252525] border-t border-[0.5px] border-[#D5D8DE] dark:border-[#383838]">
        {loading ? (
          <div className="p-3 space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-8 bg-[#E4E6EA] dark:bg-[#2D2D2D] animate-pulse rounded" />
            ))}
          </div>
        ) : active.length === 0 && archived.length === 0 ? (
          <p className="px-3 py-3 text-[12px] text-[#9CA3AF]">
            {selectedFolderId ? 'No files in this folder.' : 'No files at the root level.'}
          </p>
        ) : (
          <>
            {active.map((doc, i) => (
              <DocRow
                key={doc.id}
                doc={doc}
                borderBottom={i < active.length - 1 || (showArchivedToggle ? archived.length > 0 : false)}
                folders={folders}
                fetchDocs={fetchDocs}
                isFinalized={isFinalized}
              />
            ))}

            {/* Archived docs toggle -- only rendered when showArchivedToggle prop is true */}
            {showArchivedToggle && archived.length > 0 && (
              <>
                <div className="flex items-center gap-2 px-3 py-2 border-t border-[0.5px] border-[#E5E7EB] dark:border-[#333]">
                  <span className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">
                    Archived ({archived.length})
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
                {showArchived && (
                  <div style={{ opacity: 0.6 }}>
                    {archived.map((doc, i) => (
                      <DocRow
                        key={doc.id}
                        doc={doc}
                        borderBottom={i < archived.length - 1}
                        folders={folders}
                        fetchDocs={fetchDocs}
                        isFinalized={isFinalized}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    )
  }
}
