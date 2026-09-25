// frontend/src/components/import/ReviewImportPage.tsx
'use client'

import { useState, useEffect, useMemo, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  ChevronRight,
  ChevronDown,
  FileText,
  Folder,
  FolderOpen,
  Files,
  HardDrive,
  AlertTriangle,
  X,
  ArrowLeft,
  Search,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { importBatchesApi } from '@/lib/api/importBatches'
import type { ImportBatchOut, ImportItemOut, ImportBatchPreview, ImportItemPreview } from '@/lib/api/importBatches'
import { engagementsApi, clientsApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ItemStatus = 'ready' | 'willSkip' | 'excluded'
type FilterMode = 'all' | 'willSkip' | 'excluded' | 'ready'

interface FileNode {
  kind: 'file'
  item: ImportItemOut
  preview: ImportItemPreview | null
  status: ItemStatus
}

interface FolderNode {
  kind: 'folder'
  name: string
  path: string
  children: TreeNode[]
  rollupStatus: ItemStatus
  issueCount: number
}

type TreeNode = FolderNode | FileNode

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

// Maps a MIME type string to a Tailwind text-color class for the thin-outline
// file icon.  Uses standard Tailwind palette (text-red-500, text-blue-500, etc.)
// since no type-colored-plain-icon precedent exists in this codebase.
function mimeTypeColor(mimeType: string): string {
  if (mimeType.includes('pdf')) return 'text-red-500'
  if (mimeType.includes('word') || mimeType.includes('docx') || mimeType.includes('document')) return 'text-blue-500'
  if (mimeType.includes('excel') || mimeType.includes('xlsx') || mimeType.includes('spreadsheet')) return 'text-green-600'
  if (mimeType.includes('powerpoint') || mimeType.includes('pptx') || mimeType.includes('presentation')) return 'text-amber-500'
  if (mimeType.includes('image')) return 'text-purple-500'
  return 'text-[#6B7280]'
}

function itemStatus(preview: ImportItemPreview | null): ItemStatus {
  // excluded: only when the path would genuinely fail at finalization (depth limit exceeded).
  // A folder that does not yet exist is not grounds for exclusion -- _finalize_one_item
  // always creates missing folders.  resolved=false simply means no conflict check was
  // possible; the file will still be imported successfully.
  if (!preview || preview.pathWouldExceedDepth) return 'excluded'
  if (preview.hasConflict) return 'willSkip'
  return 'ready'
}

const STATUS_ORDER: Record<ItemStatus, number> = { excluded: 0, willSkip: 1, ready: 2 }

function worstStatus(a: ItemStatus, b: ItemStatus): ItemStatus {
  return STATUS_ORDER[a] <= STATUS_ORDER[b] ? a : b
}

function buildTree(items: ImportItemOut[], previewItems: ImportItemPreview[]): FolderNode {
  const previewMap = new Map(previewItems.map((p) => [p.itemId, p]))
  const root: FolderNode = { kind: 'folder', name: '__root__', path: '', children: [], rollupStatus: 'ready', issueCount: 0 }

  for (const item of items) {
    const preview = previewMap.get(item.id) ?? null
    const status = itemStatus(preview)
    const parts = item.normalizedRelativePath.split('/')

    // Navigate to parent folder, creating folder nodes as needed
    let current = root
    for (let i = 0; i < parts.length - 1; i++) {
      const name = parts[i]
      if (!name) continue
      let child = current.children.find((c): c is FolderNode => c.kind === 'folder' && c.name === name)
      if (!child) {
        child = {
          kind: 'folder',
          name,
          path: parts.slice(0, i + 1).join('/'),
          children: [],
          rollupStatus: 'ready',
          issueCount: 0,
        }
        current.children.push(child)
      }
      current = child
    }

    const fileNode: FileNode = { kind: 'file', item, preview, status }
    current.children.push(fileNode)
  }

  // Sort: folders before files, then alphabetically within each group
  function sortChildren(node: FolderNode) {
    node.children.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1
      const aName = a.kind === 'folder' ? a.name : a.item.filename
      const bName = b.kind === 'folder' ? b.name : b.item.filename
      return aName.localeCompare(bName)
    })
    for (const child of node.children) {
      if (child.kind === 'folder') sortChildren(child)
    }
  }
  sortChildren(root)

  // Compute folder rollup bottom-up
  function rollup(node: FolderNode): { status: ItemStatus; issues: number } {
    let status: ItemStatus = 'ready'
    let issues = 0
    for (const child of node.children) {
      if (child.kind === 'file') {
        if (child.status !== 'ready') issues++
        status = worstStatus(status, child.status)
      } else {
        const r = rollup(child)
        issues += r.issues
        status = worstStatus(status, r.status)
        child.rollupStatus = r.status
        child.issueCount = r.issues
      }
    }
    node.rollupStatus = status
    node.issueCount = issues
    return { status, issues }
  }
  rollup(root)

  return root
}

function countUniqueFolders(items: ImportItemOut[]): number {
  const paths = new Set<string>()
  for (const item of items) {
    const parts = item.normalizedRelativePath.split('/')
    for (let i = 0; i < parts.length - 1; i++) {
      if (parts[i]) paths.add(parts.slice(0, i + 1).join('/'))
    }
  }
  return paths.size
}

function policyLabel(policy: string): string {
  if (policy === 'skip') return 'Skip (default)'
  if (policy === 'replace') return 'Replace'
  if (policy === 'keep_both') return 'Keep both'
  return policy
}

function policyConsequence(policy: string, skipCount: number): string {
  if (policy === 'skip') return `${skipCount} file${skipCount !== 1 ? 's' : ''} with a name conflict will be skipped.`
  if (policy === 'replace') return `${skipCount} existing file${skipCount !== 1 ? 's' : ''} will be replaced.`
  if (policy === 'keep_both') return `${skipCount} file${skipCount !== 1 ? 's' : ''} will be imported with a suffix to avoid name conflicts.`
  return ''
}

function backPath(batch: ImportBatchOut): string {
  if (batch.scope === 'engagement' && batch.engagementId) return `/engagements/${batch.engagementId}`
  if (batch.scope === 'client' && batch.clientId) return `/clients/${batch.clientId}`
  return '/firm-library'
}

// ---------------------------------------------------------------------------
// Status dot
// ---------------------------------------------------------------------------

function StatusDot({ status }: { status: ItemStatus }) {
  if (status === 'ready') return null
  return (
    <span
      className={cn(
        'inline-block w-2 h-2 rounded-full flex-shrink-0',
        status === 'willSkip' ? 'bg-[#991B1B]' : 'bg-[#9CA3AF]',
      )}
    />
  )
}

function StatusLabel({ status, issueCount, conflictPolicy }: { status: ItemStatus; issueCount?: number; conflictPolicy?: string }) {
  if (status === 'ready') return <span className="text-[#9CA3AF] text-[12px]">Ready</span>
  if (status === 'willSkip') {
    // Label reflects what the backend will actually do: skip only under 'skip' policy;
    // under 'replace' the existing file is overwritten, under 'keep_both' the new file
    // is imported with a deduplicated suffix -- neither is a skip.
    let label: string
    if (conflictPolicy === 'replace') label = 'Will replace'
    else if (conflictPolicy === 'keep_both') label = 'Will import (renamed)'
    else label = 'Will skip'
    return (
      <span className="text-[#991B1B] text-[12px]">
        {label}{issueCount !== undefined && issueCount > 0 ? `, ${issueCount} issue${issueCount !== 1 ? 's' : ''}` : ''}
      </span>
    )
  }
  return (
    <span className="text-[#6B7280] text-[12px]">
      Excluded{issueCount !== undefined && issueCount > 0 ? `, ${issueCount} issue${issueCount !== 1 ? 's' : ''}` : ''}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Tree row rendering
// ---------------------------------------------------------------------------

interface RowProps {
  node: TreeNode
  depth: number
  expandedPaths: Set<string>
  toggleExpand: (path: string) => void
  selectedItemId: string | null
  onSelectItem: (id: string) => void
  filter: FilterMode
}

function nodeMatchesFilter(node: TreeNode, filter: FilterMode): boolean {
  if (filter === 'all') return true
  if (node.kind === 'file') {
    if (filter === 'ready') return node.status === 'ready'
    if (filter === 'willSkip') return node.status === 'willSkip'
    if (filter === 'excluded') return node.status === 'excluded'
  } else {
    // Folder matches if any descendant matches
    return folderHasMatchingDescendant(node, filter)
  }
  return false
}

function folderHasMatchingDescendant(folder: FolderNode, filter: FilterMode): boolean {
  for (const child of folder.children) {
    if (child.kind === 'file') {
      if (filter === 'ready' && child.status === 'ready') return true
      if (filter === 'willSkip' && child.status === 'willSkip') return true
      if (filter === 'excluded' && child.status === 'excluded') return true
    } else if (folderHasMatchingDescendant(child, filter)) {
      return true
    }
  }
  return false
}

function TreeRows({
  nodes,
  depth,
  expandedPaths,
  toggleExpand,
  selectedItemId,
  onSelectItem,
  filter,
  conflictPolicy,
}: {
  nodes: TreeNode[]
  depth: number
  expandedPaths: Set<string>
  toggleExpand: (path: string) => void
  selectedItemId: string | null
  onSelectItem: (id: string) => void
  filter: FilterMode
  conflictPolicy: string
}) {
  return (
    <>
      {nodes.map((node) => {
        if (!nodeMatchesFilter(node, filter)) return null

        if (node.kind === 'folder') {
          const isExpanded = expandedPaths.has(node.path)
          return (
            <div key={node.path}>
              <div
                className="flex items-center gap-2 px-3 py-2 hover:bg-[#F5F7FA] dark:hover:bg-[#2A2F37] cursor-pointer select-none border-b border-[0.5px] border-[#F0F2F5] dark:border-[#333840]"
                style={{ paddingLeft: `${12 + depth * 20}px` }}
                onClick={() => toggleExpand(node.path)}
              >
                <span className="text-[#9CA3AF] flex-shrink-0 w-4">
                  {isExpanded
                    ? <ChevronDown className="h-3.5 w-3.5" />
                    : <ChevronRight className="h-3.5 w-3.5" />}
                </span>
                {isExpanded
                  ? <FolderOpen className="h-4 w-4 flex-shrink-0" fill='#FBBF24' style={{ color: '#FBBF24' }} />
                  : <Folder className="h-4 w-4 flex-shrink-0" fill='#FBBF24' style={{ color: '#FBBF24' }} />}
                <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] flex-1 truncate min-w-0">
                  {node.name}
                </span>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <StatusDot status={node.rollupStatus} />
                  <StatusLabel status={node.rollupStatus} issueCount={node.issueCount > 0 ? node.issueCount : undefined} conflictPolicy={conflictPolicy} />
                </div>
                <span className="text-[12px] text-[#9CA3AF] flex-shrink-0 w-16 text-right" />
              </div>
              {isExpanded && (
                <TreeRows
                  nodes={node.children}
                  depth={depth + 1}
                  expandedPaths={expandedPaths}
                  toggleExpand={toggleExpand}
                  selectedItemId={selectedItemId}
                  onSelectItem={onSelectItem}
                  filter={filter}
                  conflictPolicy={conflictPolicy}
                />
              )}
            </div>
          )
        }

        // File node
        const isSelected = selectedItemId === node.item.id
        return (
          <div
            key={node.item.id}
            className={cn(
              'flex items-center gap-2 px-3 py-2 cursor-pointer border-b border-[0.5px] border-[#F0F2F5] dark:border-[#333840]',
              isSelected
                ? 'bg-[#EEF2F7] dark:bg-[#2D3440]'
                : 'hover:bg-[#F5F7FA] dark:hover:bg-[#2A2F37]',
            )}
            style={{ paddingLeft: `${12 + depth * 20}px` }}
            onClick={() => onSelectItem(node.item.id)}
          >
            <span className="w-4 flex-shrink-0" />
            <FileText className={cn('h-4 w-4 flex-shrink-0', mimeTypeColor(node.item.mimeType ?? ''))} />
            <span className="text-[13px] text-brand dark:text-[#EDEEF0] flex-1 truncate min-w-0">
              {node.item.filename}
            </span>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <StatusDot status={node.status} />
              <StatusLabel status={node.status} conflictPolicy={conflictPolicy} />
            </div>
            <span className="text-[12px] text-[#9CA3AF] flex-shrink-0 w-16 text-right">
              {formatBytes(node.item.expectedBytes)}
            </span>
          </div>
        )
      })}
    </>
  )
}

// ---------------------------------------------------------------------------
// Details drawer
// ---------------------------------------------------------------------------

function DetailsDrawer({
  item,
  preview,
  conflictPolicy,
  onClose,
}: {
  item: ImportItemOut
  preview: ImportItemPreview | null
  conflictPolicy: string
  onClose: () => void
}) {
  const status = itemStatus(preview)

  return (
    <div className="flex flex-col h-full">
      {/* Drawer header */}
      <div className="flex items-start gap-2 px-4 py-3 border-b border-[0.5px] border-[#E5E9EF] dark:border-[#3B444F]">
        <FileText className={cn('h-5 w-5 flex-shrink-0', mimeTypeColor(item.mimeType ?? ''))} />
        <span className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0] flex-1 min-w-0 break-words">
          {item.filename}
        </span>
        <button
          onClick={onClose}
          className="text-[#9CA3AF] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors flex-shrink-0"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Drawer body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        <div>
          <p className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-1">From</p>
          <p className="text-[13px] text-brand dark:text-[#EDEEF0] break-all">{item.relativePath}</p>
        </div>

        <div>
          <p className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-1">
            Destination path
          </p>
          <p className="text-[13px] text-brand dark:text-[#EDEEF0] break-all">{item.normalizedRelativePath}</p>
        </div>

        <div className="flex gap-6">
          <div>
            <p className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-1">Size</p>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{formatBytes(item.expectedBytes)}</p>
          </div>
        </div>

        {/* Conflict details */}
        {status === 'willSkip' && preview && (
          <div className="rounded-[8px] bg-[#FEE2E2] border border-[0.5px] border-[#FCA5A5] px-3 py-3">
            <p className="text-[12px] font-medium text-[#991B1B] mb-1">
              Name conflict detected
            </p>
            {preview.existingDocumentFilename && (
              <p className="text-[12px] text-[#991B1B] mb-2">
                Existing file: {preview.existingDocumentFilename}
              </p>
            )}
            <p className="text-[12px] text-[#991B1B]">
              Batch default: {policyLabel(conflictPolicy)}
            </p>
            <p className="text-[11px] text-[#B45309] mt-2 italic">
              Per-file overrides are set at batch creation, before this review step.
            </p>
          </div>
        )}

        {status === 'excluded' && (
          <div className="rounded-[8px] bg-[#F3F4F6] border border-[0.5px] border-[#E5E7EB] px-3 py-3">
            <p className="text-[12px] font-medium text-[#374151] mb-1">Path not resolvable</p>
            <p className="text-[12px] text-[#6B7280]">
              One or more parent folders in this file's path do not yet exist. This file will be excluded from the import.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  sub,
  iconBg,
  icon,
}: {
  label: string
  value: string
  sub?: string
  iconBg: string
  icon: React.ReactNode
}) {
  return (
    <div className="bg-white dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#E5E9EF] dark:border-[#3B444F] px-5 py-4 flex items-center gap-4 flex-1 min-w-0">
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', iconBg)}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-[#9CA3AF] mb-1 truncate">{label}</p>
        <p className="text-[22px] font-semibold leading-none text-brand dark:text-[#EDEEF0] mb-0.5">{value}</p>
        {sub && <p className="text-[11px] text-[#9CA3AF] leading-snug">{sub}</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

function ReviewImportInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const batchId = searchParams.get('batch')

  const [batch, setBatch] = useState<ImportBatchOut | null>(null)
  const [previewData, setPreviewData] = useState<ImportBatchPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterMode>('all')
  const [search, setSearch] = useState('')
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set())
  const [confirming, setConfirming] = useState(false)
  const [policyUpdating, setPolicyUpdating] = useState(false)
  const [destName, setDestName] = useState<string | null>(null)

  useEffect(() => {
    if (!batchId) {
      setLoadError('No batch ID provided.')
      setLoading(false)
      return
    }
    setLoading(true)
    Promise.all([
      importBatchesApi.get(batchId),
      importBatchesApi.preview(batchId),
    ])
      .then(([batchRes, previewRes]) => {
        setBatch(batchRes)
        setPreviewData(previewRes)
        // Auto-expand root-level folders on load
        const rootFolders = new Set<string>()
        for (const item of batchRes.items) {
          const parts = item.normalizedRelativePath.split('/')
          if (parts.length > 1 && parts[0]) rootFolders.add(parts[0])
        }
        setExpandedPaths(rootFolders)
        setLoading(false)
        // Fetch the real entity name for the destination line (best-effort; errors are silent).
        if (batchRes.scope === 'engagement' && batchRes.engagementId) {
          engagementsApi.get(batchRes.engagementId).then((e) => setDestName(e.name)).catch(() => {})
        } else if (batchRes.scope === 'client' && batchRes.clientId) {
          clientsApi.get(batchRes.clientId).then((c) => setDestName(c.name)).catch(() => {})
        } else if (batchRes.scope === 'firm_library') {
          setDestName('Firm Library')
        }
      })
      .catch((err: unknown) => {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setLoadError(detail ?? 'Failed to load import data.')
        setLoading(false)
      })
  }, [batchId])

  const tree = useMemo(() => {
    if (!batch || !previewData) return null
    return buildTree(batch.items, previewData.items)
  }, [batch, previewData])

  const counts = useMemo(() => {
    if (!batch || !previewData) return { total: 0, willSkip: 0, excluded: 0, ready: 0, folders: 0, totalBytes: 0 }
    const previewMap = new Map(previewData.items.map((p) => [p.itemId, p]))
    let willSkip = 0
    let excluded = 0
    let ready = 0
    for (const item of batch.items) {
      const p = previewMap.get(item.id)
      const s = itemStatus(p ?? null)
      if (s === 'willSkip') willSkip++
      else if (s === 'excluded') excluded++
      else ready++
    }
    return {
      total: batch.totalFiles,
      willSkip,
      excluded,
      ready,
      folders: countUniqueFolders(batch.items),
      totalBytes: batch.totalBytes,
    }
  }, [batch, previewData])

  const selectedData = useMemo(() => {
    if (!selectedItemId || !batch || !previewData) return null
    const item = batch.items.find((i) => i.id === selectedItemId)
    const preview = previewData.items.find((p) => p.itemId === selectedItemId) ?? null
    return item ? { item, preview } : null
  }, [selectedItemId, batch, previewData])

  const toggleExpand = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const handlePolicyChange = useCallback(async (policy: string) => {
    if (!batchId || !batch || batch.status !== 'draft') return
    setPolicyUpdating(true)
    try {
      const updated = await importBatchesApi.updateConflictPolicy(batchId, policy)
      setBatch(updated)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to update conflict policy -- please try again')
    } finally {
      setPolicyUpdating(false)
    }
  }, [batchId, batch])

  const handleConfirm = useCallback(async () => {
    if (!batchId || !batch) return
    setConfirming(true)
    try {
      await importBatchesApi.confirm(batchId)
      toast.success('Import started. Files are being processed in the background.')
      router.push(backPath(batch))
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to start import -- please try again')
    } finally {
      setConfirming(false)
    }
  }, [batchId, batch, router])

  // Apply search filter to visible items (simple substring on filename/path)
  const filteredTree = useMemo(() => {
    if (!tree || !search.trim()) return tree
    const q = search.toLowerCase()
    function filterNode(node: TreeNode): TreeNode | null {
      if (node.kind === 'file') {
        return node.item.filename.toLowerCase().includes(q) ||
          node.item.normalizedRelativePath.toLowerCase().includes(q)
          ? node
          : null
      }
      const filteredChildren = node.children.map(filterNode).filter((c): c is TreeNode => c !== null)
      if (filteredChildren.length === 0) return null
      return { ...node, children: filteredChildren }
    }
    const filteredChildren = tree.children.map(filterNode).filter((c): c is TreeNode => c !== null)
    return { ...tree, children: filteredChildren }
  }, [tree, search])

  // Loading / error states
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[13px] text-[#9CA3AF]">Loading import review...</div>
      </div>
    )
  }

  if (loadError || !batch || !filteredTree) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[13px] text-status-red-text">{loadError ?? 'Batch not found.'}</div>
      </div>
    )
  }

  // Under 'skip': willSkip items produce no document (marked skipped by the finalizer).
  // Under 'replace'/'keep_both': willSkip items DO produce a document (existing file is
  // replaced or the incoming file is imported with a suffix). Only excluded items
  // (unresolvable paths) never produce a document under any policy.
  const importCount = batch.conflictPolicy === 'skip'
    ? counts.ready
    : counts.ready + counts.willSkip
  const cancelHref = backPath(batch)

  return (
    <div className="flex flex-col min-h-screen bg-surface-page dark:bg-dark-page pb-20">
      <div className="px-6 pt-5 pb-0">
        {/* Breadcrumb */}
        <Breadcrumb
          items={[
            { label: 'Back', href: cancelHref },
            { label: 'Review Import' },
          ]}
        />

        {/* Title + destination */}
        <div className="mb-4">
          <h1 className="text-[22px] font-semibold text-brand dark:text-[#EDEEF0] mb-1">Review Import</h1>
          <p className="text-[13px] text-[#6B7280]">
            Review the destination below and resolve any conflicts before importing.
          </p>
          <div className="mt-2 flex items-center gap-2 text-[13px]">
            <span className="text-[#9CA3AF]">Destination:</span>
            <span className="text-brand dark:text-[#EDEEF0] font-medium">
              {destName ?? (batch.scope === 'firm_library' ? 'Firm Library' : '...')}
              {batch.destinationFolderId ? ' / subfolder' : ''}
            </span>
          </div>
        </div>

        {/* Summary strip */}
        <div className="flex gap-3 mb-5 flex-wrap">
          <StatCard
            label="Files scanned"
            value={counts.total.toString()}
            iconBg="bg-blue-200"
            icon={<Files className="h-[18px] w-[18px] text-[#3B82F6]" />}
          />
          <StatCard
            label="Folders"
            value={counts.folders.toString()}
            iconBg="bg-amber-200"
            icon={<Folder className="h-[18px] w-[18px]" fill='#FBBF24' style={{ color: '#FBBF24' }} />}
          />
          <StatCard
            label="Total size"
            value={formatBytes(counts.totalBytes)}
            iconBg="bg-emerald-200"
            icon={<HardDrive className="h-[18px] w-[18px] text-[#10B981]" />}
          />
          <StatCard
            label="Will skip"
            value={counts.willSkip.toString()}
            sub={counts.willSkip > 0 ? 'name conflict' : undefined}
            iconBg="bg-[#FEE2E2]"
            icon={<AlertTriangle className="h-[18px] w-[18px] text-[#991B1B]" />}
          />
          <StatCard
            label="Excluded"
            value={counts.excluded.toString()}
            sub={counts.excluded > 0 ? 'path unresolvable' : undefined}
            iconBg="bg-gray-200"
            icon={<X className="h-[18px] w-[18px] text-[#6B7280]" />}
          />
        </div>

        {/* Conflict policy control -- interactive for draft batches, read-only once confirmed */}
        <div className="mb-4">
          <div className="flex items-center gap-5 flex-wrap">
            <span className="text-[13px] text-[#6B7280]">If a file already exists:</span>
            {(['skip', 'replace', 'keep_both'] as const).map((p) => {
              const isSelected = batch.conflictPolicy === p
              const isInteractive = batch.status === 'draft' && !policyUpdating
              return (
                <button
                  key={p}
                  type="button"
                  disabled={!isInteractive}
                  onClick={() => { if (isInteractive && !isSelected) handlePolicyChange(p) }}
                  className={cn(
                    'flex items-center gap-2 text-[13px] transition-colors',
                    isInteractive && !isSelected ? 'cursor-pointer hover:opacity-80' : 'cursor-default',
                    policyUpdating ? 'opacity-50' : '',
                  )}
                >
                  <span className={cn(
                    'w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors',
                    isSelected ? 'border-brand' : 'border-[#C8CDD6] dark:border-[#484848]',
                  )}>
                    {isSelected && <span className="w-2 h-2 rounded-full bg-brand" />}
                  </span>
                  <span className={cn(
                    'transition-colors',
                    isSelected ? 'text-brand dark:text-[#EDEEF0] font-medium' : 'text-[#6B7280]',
                  )}>
                    {policyLabel(p)}
                  </span>
                </button>
              )
            })}
          </div>
          {counts.willSkip > 0 && (
            <p className="mt-1.5 text-[12px] text-[#991B1B]">
              {policyConsequence(batch.conflictPolicy, counts.willSkip)}
            </p>
          )}
        </div>

        {/* Filter chips + search */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-1.5">
            {(
              [
                { key: 'all', label: `All ${counts.total}` },
                { key: 'willSkip', label: `${batch.conflictPolicy === 'replace' ? 'Will replace' : batch.conflictPolicy === 'keep_both' ? 'Has conflict' : 'Will skip'} ${counts.willSkip}` },
                { key: 'excluded', label: `Excluded ${counts.excluded}` },
                { key: 'ready', label: `Ready ${counts.ready}` },
              ] as { key: FilterMode; label: string }[]
            ).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={cn(
                  'h-7 px-3 rounded-[6px] text-[12px] font-medium border border-[0.5px] transition-colors',
                  filter === key
                    ? 'bg-brand text-white border-brand'
                    : 'bg-transparent text-[#6B7280] border-[#C8CDD6] dark:border-[#484848] hover:border-brand hover:text-brand',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#9CA3AF]" />
            <input
              type="text"
              placeholder="Search files or folders..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-7 pl-8 pr-3 rounded-[6px] bg-white dark:bg-dark-card border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[12px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Main content: tree + drawer */}
      <div className="flex-1 px-6 flex gap-4 min-h-0 overflow-hidden">
        {/* Tree table */}
        <div
          className={cn(
            'flex-1 bg-white dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#E5E9EF] dark:border-[#3B444F] overflow-y-auto min-h-[400px]',
            selectedData ? 'flex-[3]' : 'flex-1',
          )}
        >
          {/* Table header */}
          <div className="flex items-center px-3 py-2 border-b border-[0.5px] border-[#E5E9EF] dark:border-[#3B444F] bg-[#F9FAFB] dark:bg-[#23282F] sticky top-0 z-10">
            <span className="flex-1 text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">Name</span>
            <span className="w-28 text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">Status</span>
            <span className="w-16 text-right text-[11px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">Size</span>
          </div>

          {filteredTree.children.length === 0 ? (
            <div className="flex items-center justify-center h-32">
              <p className="text-[13px] text-[#9CA3AF]">No items match the current filter.</p>
            </div>
          ) : (
            <TreeRows
              nodes={filteredTree.children}
              depth={0}
              expandedPaths={expandedPaths}
              toggleExpand={toggleExpand}
              selectedItemId={selectedItemId}
              onSelectItem={setSelectedItemId}
              filter={filter}
              conflictPolicy={batch.conflictPolicy}
            />
          )}
        </div>

        {/* Details drawer */}
        {selectedData && (
          <div className="w-72 flex-shrink-0 bg-white dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#E5E9EF] dark:border-[#3B444F] overflow-hidden flex flex-col min-h-[400px]">
            <DetailsDrawer
              item={selectedData.item}
              preview={selectedData.preview}
              conflictPolicy={batch.conflictPolicy}
              onClose={() => setSelectedItemId(null)}
            />
          </div>
        )}
      </div>

      {/* Sticky footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white dark:bg-dark-card border-t border-[0.5px] border-[#E5E9EF] dark:border-[#3B444F] px-6 py-3.5 flex items-center justify-between z-20">
        <p className="text-[13px] text-[#6B7280]">
          <span className="font-medium text-brand dark:text-[#EDEEF0]">{importCount}</span> files will import
          {counts.excluded > 0 && (
            <span> &middot; <span className="text-[#9CA3AF]">{counts.excluded} excluded</span></span>
          )}
          {counts.willSkip > 0 && batch.conflictPolicy === 'skip' && (
            <span> &middot; <span className="text-[#9CA3AF]">{counts.willSkip} will skip</span></span>
          )}
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(cancelHref)}
            className="h-9 px-4 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[13px] text-[#6B7280] hover:text-brand hover:border-brand transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={confirming || importCount === 0}
            className="h-9 px-5 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {confirming ? 'Starting...' : `Import ${importCount} File${importCount !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ReviewImportPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64 text-[13px] text-[#9CA3AF]">Loading...</div>}>
      <ReviewImportInner />
    </Suspense>
  )
}
