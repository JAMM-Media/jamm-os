// frontend/src/components/engagements/RollForwardModal.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { CheckCircle, FileText, ChevronRight, FolderOpen } from 'lucide-react'
import { type Engagement, engagementsApi } from '@/lib/api'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Local types -- raw API shapes used only within this component
// ---------------------------------------------------------------------------

interface SourceFolder {
  id: string
  name: string
  parentFolderId: string | null
}

interface SourceDocument {
  id: string
  filename: string
  contentType: string
  sizeBytes: number
  folderId: string | null
  createdAt: string
}

interface RollForwardModalProps {
  newEngagement: Engagement
  priorEngagement: Engagement
  clientName: string
  onDone: (engagement: Engagement) => void
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Folder path resolution: walks parent_folder_id chains on the client
// ---------------------------------------------------------------------------

function buildFolderMap(folders: SourceFolder[]): Record<string, SourceFolder> {
  const map: Record<string, SourceFolder> = {}
  for (const f of folders) map[f.id] = f
  return map
}

function resolveFolderPath(folderId: string | null, folderMap: Record<string, SourceFolder>): string {
  if (!folderId) return ''
  const parts: string[] = []
  let current: string | null = folderId
  let guard = 0
  while (current && guard < 25) {
    const f = folderMap[current]
    if (!f) break
    parts.unshift(f.name)
    current = f.parentFolderId
    guard++
  }
  return parts.join(' > ')
}

// ---------------------------------------------------------------------------
// Render a nested folder tree from a flat folder list
// ---------------------------------------------------------------------------

function FolderTree({ folders }: { folders: SourceFolder[] }) {
  const childrenOf: Record<string, SourceFolder[]> = {}
  for (const f of folders) {
    const key = f.parentFolderId ?? '__root__'
    if (!childrenOf[key]) childrenOf[key] = []
    childrenOf[key].push(f)
  }

  function renderLevel(parentKey: string, depth: number): JSX.Element[] {
    const children = childrenOf[parentKey] ?? []
    return children.map((f) => (
      <div key={f.id}>
        <div
          className="flex items-center gap-1.5 py-0.5"
          style={{ paddingLeft: `${depth * 16}px` }}
        >
          <FolderOpen size={13} className="text-[#6B7280] flex-shrink-0" />
          <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">{f.name}</span>
        </div>
        {renderLevel(f.id, depth + 1)}
      </div>
    ))
  }

  if (folders.length === 0) {
    return <p className="text-[12px] text-[#6B7280]">No folders were copied.</p>
  }

  return <div>{renderLevel('__root__', 0)}</div>
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function RollForwardModal({
  newEngagement,
  priorEngagement,
  clientName,
  onDone,
  onClose,
}: RollForwardModalProps) {
  const [step, setStep] = useState<'offer' | 'confirm'>('offer')
  const [rolling, setRolling] = useState(false)

  // Confirm step data
  const [idMap, setIdMap] = useState<Record<string, string>>({})
  const [createdCount, setCreatedCount] = useState(0)
  const [sourceFolders, setSourceFolders] = useState<SourceFolder[]>([])
  const [sourceDocs, setSourceDocs] = useState<SourceDocument[]>([])
  const [loadingDetails, setLoadingDetails] = useState(false)

  // Cherry-pick state
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [copying, setCopying] = useState(false)
  const [copyResult, setCopyResult] = useState<{ succeeded: number; failed: number } | null>(null)

  const folderMap = buildFolderMap(sourceFolders)

  // After roll-forward succeeds, fetch source folders + docs for confirmation screen
  const loadConfirmDetails = useCallback(async () => {
    setLoadingDetails(true)
    try {
      const [foldersRes, docsRes] = await Promise.all([
        api.get('/document-folders/', {
          params: { engagement_id: priorEngagement.id, scope: 'engagement' },
        }),
        api.get('/documents/', {
          params: { engagement_id: priorEngagement.id, limit: 200 },
        }),
      ])

      const rawFolders: SourceFolder[] = (foldersRes.data ?? []).map(
        (f: Record<string, unknown>) => ({
          id: String(f.id),
          name: String(f.name ?? ''),
          parentFolderId: f.parent_folder_id ? String(f.parent_folder_id) : null,
        }),
      )
      setSourceFolders(rawFolders)

      const rawItems = docsRes.data?.items ?? docsRes.data ?? []
      const rawDocs: SourceDocument[] = rawItems
        .filter((d: Record<string, unknown>) => !d.deleted_at && d.triage_status !== 'pending')
        .map((d: Record<string, unknown>) => ({
          id: String(d.id),
          filename: String(d.filename ?? d.name ?? ''),
          contentType: String(d.content_type ?? ''),
          sizeBytes: Number(d.size_bytes ?? 0),
          folderId: d.folder_id ? String(d.folder_id) : null,
          createdAt: String(d.created_at ?? d.uploaded_at ?? ''),
        }))
      setSourceDocs(rawDocs)
    } catch {
      // Non-fatal: cherry-pick section shows empty gracefully
    } finally {
      setLoadingDetails(false)
    }
  }, [priorEngagement.id])

  async function handleCopyFolders() {
    setRolling(true)
    try {
      const result = await engagementsApi.rollForwardFolders(
        newEngagement.id,
        priorEngagement.id,
      )
      setIdMap(result.id_map)
      setCreatedCount(result.folders_created)
      setStep('confirm')
      await loadConfirmDetails()
    } catch {
      toast.error('Could not copy folder structure. Please try again.')
    } finally {
      setRolling(false)
    }
  }

  function handleStartEmpty() {
    onDone(newEngagement)
    onClose()
  }

  function handleSkip() {
    onDone(newEngagement)
    onClose()
  }

  function toggleDoc(docId: string) {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  async function handleCopyFiles() {
    setCopying(true)
    let succeeded = 0
    let failed = 0

    for (const docId of checkedIds) {
      const doc = sourceDocs.find((d) => d.id === docId)
      if (!doc) continue

      // Resolve destination folder from id_map; fall back to engagement root
      const destFolderId = doc.folderId ? idMap[doc.folderId] : undefined

      const body: Record<string, unknown> = {}
      if (destFolderId) {
        body.folder_id = destFolderId
      } else {
        body.dest_engagement_id = newEngagement.id
        body.dest_client_id = newEngagement.clientId
      }

      try {
        await api.post(`/documents/${docId}/copy`, body)
        succeeded++
      } catch {
        failed++
      }
    }

    setCopyResult({ succeeded, failed })
    setCopying(false)

    if (failed === 0) {
      toast.success(`${succeeded} file${succeeded !== 1 ? 's' : ''} copied successfully`)
      onDone(newEngagement)
      onClose()
    }
    // If partial failure, stay open and show the result inline
  }

  // Format file size for display
  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    const kb = bytes / 1024
    if (kb < 1024) return `${Math.round(kb)} KB`
    return `${(kb / 1024).toFixed(1)} MB`
  }

  // Format a ISO date string to "Jan 15, 2024"
  function formatDate(iso: string): string {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch {
      return ''
    }
  }

  // ---------------------------------------------------------------------------
  // Screen 1: Offer
  // ---------------------------------------------------------------------------
  if (step === 'offer') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="bg-[#EDEEF0] dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-6 w-full max-w-md shadow-lg">
          {/* Header */}
          <h2 className="text-[15px] font-semibold text-brand dark:text-[#EDEEF0] mb-1 text-center">
            Roll forward from last year?
          </h2>
          <p className="text-[12px] text-[#6B7280] text-center mb-5">
            This client has a {priorEngagement.name}. Would you like to copy its
            folder structure to get started with this engagement?
          </p>

          {/* Engagement comparison */}
          <div className="flex items-center gap-3 mb-2">
            {/* Source */}
            <div className="flex-1 bg-white dark:bg-[#252525] rounded-[8px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-3 text-center">
              <p className="text-[11px] text-[#9CA3AF] mb-0.5">{clientName}</p>
              <p className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate">
                {priorEngagement.name}
              </p>
            </div>

            <ChevronRight size={16} className="text-[#9CA3AF] flex-shrink-0" />

            {/* Destination */}
            <div className="flex-1 bg-white dark:bg-[#252525] rounded-[8px] border border-[0.5px] border-[#1F3148] dark:border-[#4A7FA5] p-3 text-center">
              <p className="text-[11px] text-[#9CA3AF] mb-0.5">{clientName}</p>
              <p className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate">
                {newEngagement.name}
              </p>
            </div>
          </div>

          <p className="text-[11px] text-[#9CA3AF] text-center mb-5">
            We'll copy the folder names and structure only -- no files will be copied.
          </p>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={handleStartEmpty}
              className="flex-1 h-9 rounded-[6px] border border-[0.5px] border-[#1F3148] dark:border-[#4A7FA5] text-[#1F3148] dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
            >
              Start empty
            </button>
            <button
              onClick={handleCopyFolders}
              disabled={rolling}
              className="flex-1 h-9 rounded-[6px] bg-[#1F3148] dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {rolling ? 'Copying...' : 'Copy folder structure'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Screen 2: Confirmation + cherry-pick
  // ---------------------------------------------------------------------------
  const selectedCount = checkedIds.size
  const hasPartialFailure = copyResult && copyResult.failed > 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-[#EDEEF0] dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] w-full max-w-md shadow-lg flex flex-col max-h-[90vh]">

        {/* Fixed header */}
        <div className="p-6 pb-4">
          <div className="flex flex-col items-center mb-4">
            <CheckCircle size={32} className="text-green-500 mb-2" />
            <h2 className="text-[15px] font-semibold text-brand dark:text-[#EDEEF0]">
              Folder structure copied
            </h2>
            <p className="text-[12px] text-[#6B7280] text-center mt-1">
              {createdCount} folder{createdCount !== 1 ? 's' : ''} copied to {newEngagement.name}.
            </p>
          </div>

          {/* Folder tree */}
          {sourceFolders.length > 0 && (
            <div className="bg-white dark:bg-[#252525] rounded-[8px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-3 mb-4 max-h-36 overflow-y-auto">
              <FolderTree folders={sourceFolders} />
            </div>
          )}
        </div>

        {/* Scrollable cherry-pick section */}
        <div className="flex-1 overflow-y-auto px-6 pb-2">
          <p className="text-[12px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">
            Want to bring any files over too?
          </p>

          {loadingDetails && (
            <p className="text-[12px] text-[#9CA3AF] text-center py-4">Loading files...</p>
          )}

          {!loadingDetails && sourceDocs.length === 0 && (
            <p className="text-[12px] text-[#9CA3AF] text-center py-4">
              No files in the source engagement.
            </p>
          )}

          {!loadingDetails && sourceDocs.length > 0 && (
            <div className="flex flex-col gap-1">
              {sourceDocs.map((doc) => {
                const folderPath = resolveFolderPath(doc.folderId, folderMap)
                const isChecked = checkedIds.has(doc.id)
                return (
                  <label
                    key={doc.id}
                    className={cn(
                      'flex items-start gap-3 p-2.5 rounded-[6px] cursor-pointer transition-colors',
                      isChecked
                        ? 'bg-[#E0E7FF] dark:bg-[#1E2A40]'
                        : 'bg-white dark:bg-[#252525] hover:bg-[#F5F6F8] dark:hover:bg-[#2D2D2D]',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleDoc(doc.id)}
                      className="mt-0.5 flex-shrink-0"
                    />
                    <FileText size={14} className="text-[#6B7280] flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate">
                        {doc.filename}
                      </p>
                      <p className="text-[11px] text-[#9CA3AF]">
                        {folderPath ? `in ${folderPath} · ` : ''}{formatSize(doc.sizeBytes)}
                        {doc.createdAt ? ` · ${formatDate(doc.createdAt)}` : ''}
                      </p>
                    </div>
                  </label>
                )
              })}
            </div>
          )}

          {/* Partial failure message */}
          {hasPartialFailure && (
            <div className="mt-3 p-2.5 rounded-[6px] bg-[#FEF2F2] dark:bg-[#3D1A1A] border border-[0.5px] border-[#FECACA]">
              <p className="text-[12px] text-[#B91C1C] dark:text-[#FCA5A5]">
                {copyResult.succeeded} of {copyResult.succeeded + copyResult.failed} files copied.
                Some files could not be copied -- please try again from the Documents tab.
              </p>
            </div>
          )}
        </div>

        {/* Fixed footer */}
        <div className="p-6 pt-4 flex flex-col gap-2 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848]">
          <button
            onClick={handleCopyFiles}
            disabled={selectedCount === 0 || copying}
            className={cn(
              'w-full h-9 rounded-[6px] text-[13px] font-medium transition-opacity',
              selectedCount > 0
                ? 'bg-[#1F3148] dark:bg-brand-btn text-white hover:opacity-90'
                : 'bg-[#D1D5DB] text-[#9CA3AF] cursor-not-allowed',
              copying ? 'opacity-50' : '',
            )}
          >
            {copying
              ? 'Copying...'
              : selectedCount > 0
              ? `Copy ${selectedCount} selected file${selectedCount !== 1 ? 's' : ''}`
              : 'Copy selected files'}
          </button>

          <button
            onClick={handleSkip}
            className="text-[12px] text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors text-center py-1"
          >
            Skip, I'll add files later
          </button>
        </div>
      </div>
    </div>
  )
}
