// frontend/src/components/portal/PortalDocuments.tsx
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  File,
  FileText,
  FileSpreadsheet,
  Folder,
  Upload,
  Search,
  ChevronLeft,
  Users,
} from 'lucide-react'
import { getPortalDocuments, getPortalFolders } from '@/lib/portal-api'
import type { PortalDocument, PortalFolder } from '@/lib/portal-api'

// Props interface unchanged so portal/page.tsx needs no edits.
// Dark-theme props (cardColor, portalMode, textPrimary, textMuted) are accepted
// but not used -- Documents page uses the fixed light-theme palette.
interface PortalDocumentsProps {
  firmName: string
  accentColor?: string
  cardColor?: string
  portalMode?: 'light' | 'dark'
  textPrimary?: string
  textMuted?: string
}

type Tab = 'all' | 'uploaded' | 'shared' | 'favorites'

function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function FileIcon({ fileType }: { fileType: string }) {
  const t = fileType.toUpperCase()
  if (t === 'PDF')
    return <FileText size={15} style={{ color: '#EF4444' }} className="flex-shrink-0" />
  if (['XLS', 'XLSX', 'CSV'].includes(t))
    return <FileSpreadsheet size={15} style={{ color: '#10B981' }} className="flex-shrink-0" />
  if (['DOC', 'DOCX'].includes(t))
    return <File size={15} style={{ color: '#3B82F6' }} className="flex-shrink-0" />
  return <File size={15} style={{ color: '#9CA3AF' }} className="flex-shrink-0" />
}

// Stat card: icon badge + label -> large number -> subtext -> small "View..." link.
// icon/viewLabel/onViewClick are optional.
function StatSection({
  value,
  label,
  subtext,
  icon,
  viewLabel,
  onViewClick,
}: {
  value: number
  label: string
  subtext: string
  icon?: React.ReactNode
  viewLabel?: string
  onViewClick?: () => void
}) {
  return (
    <div className="px-5 py-4 flex items-center gap-4">
      {/* Large icon circle on the left, vertically centered -- matches mock layout */}
      {icon && (
        <div
          className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: '#F3F4F6' }}
        >
          {icon}
        </div>
      )}
      {/* Text column to the right of the icon */}
      <div className="flex flex-col min-w-0">
        <p className="text-[11px] font-medium mb-1" style={{ color: '#9CA3AF' }}>{label}</p>
        <p className="text-[32px] font-bold leading-none mb-1" style={{ color: '#1F3148' }}>
          {value}
        </p>
        <p className="text-[11px] leading-snug" style={{ color: '#9CA3AF' }}>{subtext}</p>
        {viewLabel && onViewClick && (
          <button
            type="button"
            onClick={onViewClick}
            className="mt-1.5 text-left text-[11px] font-medium transition-opacity hover:opacity-70 self-start"
            style={{ color: '#3A6A94' }}
          >
            {viewLabel}
          </button>
        )}
      </div>
    </div>
  )
}

export function PortalDocuments({ firmName, accentColor = '#3A6A94' }: PortalDocumentsProps) {
  const [allDocuments, setAllDocuments] = useState<PortalDocument[]>([])
  const [viewDocuments, setViewDocuments] = useState<PortalDocument[]>([])
  const [folders, setFolders] = useState<PortalFolder[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [activeFolderId, setActiveFolderId] = useState<string | null>(null)
  const [activeFolderName, setActiveFolderName] = useState<string | null>(null)
  const [folderLoading, setFolderLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<Tab>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [showingFoldersOnly, setShowingFoldersOnly] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setFetchError(false)
    try {
      const [docs, flds] = await Promise.all([getPortalDocuments(), getPortalFolders()])
      setAllDocuments(docs)
      setViewDocuments(docs)
      setFolders(flds)
    } catch {
      setFetchError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const enterFolder = useCallback(async (folder: PortalFolder) => {
    setFolderLoading(true)
    setActiveTab('all')
    setSearchQuery('')
    setShowingFoldersOnly(false)
    try {
      const docs = await getPortalDocuments(folder.id)
      setViewDocuments(docs)
      setActiveFolderId(folder.id)
      setActiveFolderName(folder.name)
    } catch {
      // leave current view unchanged on error
    } finally {
      setFolderLoading(false)
    }
  }, [])

  const exitFolder = useCallback(() => {
    setViewDocuments(allDocuments)
    setActiveFolderId(null)
    setActiveFolderName(null)
    setActiveTab('all')
    setSearchQuery('')
    setShowingFoldersOnly(false)
  }, [allDocuments])

  const viewFoldersOnly = useCallback(() => {
    setViewDocuments(allDocuments)
    setActiveFolderId(null)
    setActiveFolderName(null)
    setActiveTab('all')
    setSearchQuery('')
    setShowingFoldersOnly(true)
  }, [allDocuments])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setToast('Document uploads are coming soon.')
    setTimeout(() => setToast(null), 4000)
    e.target.value = ''
  }

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <div className="h-8 w-48 rounded-lg animate-pulse bg-white border border-gray-100" />
        <div className="bg-white rounded-xl border border-gray-100 grid grid-cols-4 divide-x divide-gray-100">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="px-5 py-4 flex flex-col gap-2">
              <div className="h-3 w-20 rounded animate-pulse bg-gray-100" />
              <div className="h-8 w-10 rounded animate-pulse bg-gray-100" />
              <div className="h-3 w-16 rounded animate-pulse bg-gray-100" />
            </div>
          ))}
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 rounded-xl animate-pulse bg-white border border-gray-100" />
        ))}
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-6 flex flex-col items-center gap-3 py-16">
        <p className="text-[14px]" style={{ color: '#6B7280' }}>Failed to load documents.</p>
        <button
          onClick={load}
          className="px-4 py-2 rounded-lg text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
          style={{ backgroundColor: accentColor }}
        >
          Retry
        </button>
      </div>
    )
  }

  const activeDocs = allDocuments.filter((d) => !d.is_superseded)
  const sharedCount = activeDocs.filter((d) => d.uploaded_by === 'firm').length
  const uploadedCount = activeDocs.filter((d) => d.uploaded_by === 'client').length

  const viewActive = viewDocuments.filter((d) => !d.is_superseded)

  const tabFiltered =
    activeTab === 'all'
      ? viewActive
      : activeTab === 'uploaded'
      ? viewActive.filter((d) => d.uploaded_by === 'client')
      : activeTab === 'shared'
      ? viewActive.filter((d) => d.uploaded_by === 'firm')
      : []

  const displayed = searchQuery.trim()
    ? tabFiltered.filter((d) =>
        d.name.toLowerCase().includes(searchQuery.trim().toLowerCase())
      )
    : tabFiltered

  // Folders are only shown as rows when at root and on the "all" tab.
  const showFolderRows = !activeFolderId && activeTab === 'all' && folders.length > 0

  const TABS: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All Documents' },
    { key: 'uploaded', label: 'Uploaded by you' },
    { key: 'shared', label: 'Shared with you' },
    { key: 'favorites', label: 'Favorites' },
  ]

  // Whether the table has anything to show at all.
  // In folders-only mode, only folders count; document rows are hidden.
  const hasTableContent = showingFoldersOnly
    ? folders.length > 0
    : (showFolderRows || displayed.length > 0)

  return (
    <div className="p-6 flex flex-col gap-6">
      {/* Page heading */}
      <div>
        <h1 className="text-[22px] font-bold" style={{ color: '#1F3148' }}>Documents</h1>
        <p className="text-[13px] mt-1" style={{ color: '#6B7280' }}>
          Securely store, view, and share documents with your accounting team.
        </p>
      </div>

      {/* Stat strip with "View..." links wired to tab/folder filter state */}
      <div className="bg-white rounded-xl border border-gray-100 grid grid-cols-4 divide-x divide-gray-100">
        <StatSection
          value={folders.length}
          label="Folders"
          subtext="Active folders"
          icon={<Folder size={18} fill='#FBBF24' style={{ color: '#FBBF24' }} />}
          viewLabel="View folders"
          onViewClick={viewFoldersOnly}
        />
        <StatSection
          value={activeDocs.length}
          label="Documents"
          subtext="All files"
          icon={<FileText size={18} style={{ color: '#3B82F6' }} />}
          viewLabel="View all"
          onViewClick={() => { setActiveTab('all'); setSearchQuery('') }}
        />
        <StatSection
          value={sharedCount}
          label="Shared with you"
          subtext="From your firm"
          icon={<Users size={18} style={{ color: '#6B7280' }} />}
          viewLabel="View shared"
          onViewClick={() => { setActiveTab('shared'); setSearchQuery('') }}
        />
        <StatSection
          value={uploadedCount}
          label="Uploaded by you"
          subtext="Your uploads"
          icon={<Upload size={18} style={{ color: '#374151' }} />}
          viewLabel="View uploads"
          onViewClick={() => { setActiveTab('uploaded'); setSearchQuery('') }}
        />
      </div>

      {/* Controls row: search + upload */}
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: '#9CA3AF' }}
          />
          <input
            type="text"
            placeholder="Search documents by keyword"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setShowingFoldersOnly(false) }}
            className="w-full h-9 pl-9 pr-3 rounded-lg border border-gray-200 bg-white text-[13px] outline-none focus:ring-2 focus:ring-blue-100"
            style={{ color: '#1F3148' }}
          />
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1.5 h-9 px-4 rounded-lg text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex-shrink-0"
          style={{ backgroundColor: accentColor }}
        >
          <Upload size={14} />
          Upload
        </button>
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
          onChange={handleFileChange}
        />
      </div>

      {/* Tab row */}
      <div className="flex gap-0 border-b border-gray-100">
        {TABS.map(({ key, label }) => {
          const isActive = activeTab === key
          return (
            <button
              key={key}
              type="button"
              onClick={() => {
                setActiveTab(key)
                setSearchQuery('')
                setShowingFoldersOnly(false)
              }}
              className="px-4 py-2.5 text-[13px] font-medium transition-colors relative"
              style={{ color: isActive ? '#1F3148' : '#6B7280' }}
            >
              {label}
              {isActive && (
                <span
                  className="absolute bottom-0 left-0 right-0 h-[2px] rounded-full"
                  style={{ backgroundColor: '#1F3148' }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* Favorites empty state */}
      {activeTab === 'favorites' && (
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-12 text-center">
          <p className="text-[14px] font-medium" style={{ color: '#1F3148' }}>No favorites yet.</p>
          <p className="text-[12px] mt-1" style={{ color: '#6B7280' }}>
            Favoriting documents is coming soon.
          </p>
        </div>
      )}

      {activeTab !== 'favorites' && (
        <>
          {/* Folder breadcrumb (when inside a folder) */}
          {activeFolderId && (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={exitFolder}
                className="flex items-center gap-1 text-[13px] font-medium transition-opacity hover:opacity-70"
                style={{ color: accentColor }}
              >
                <ChevronLeft size={14} />
                All documents
              </button>
              <span className="text-[13px]" style={{ color: '#9CA3AF' }}>/</span>
              <span className="text-[13px] font-semibold" style={{ color: '#1F3148' }}>
                {activeFolderName}
              </span>
            </div>
          )}

          {/* Unified table: folder rows at top, then document rows */}
          {folderLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-12 rounded-xl animate-pulse bg-white border border-gray-100"
                />
              ))}
            </div>
          ) : !hasTableContent ? (
            <div className="bg-white rounded-xl border border-gray-100 px-5 py-12 text-center">
              {searchQuery.trim() ? (
                <>
                  <p className="text-[14px]" style={{ color: '#1F3148' }}>
                    No documents match your search.
                  </p>
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="mt-2 text-[12px] font-medium hover:opacity-70 transition-opacity"
                    style={{ color: accentColor }}
                  >
                    Clear search
                  </button>
                </>
              ) : activeFolderId ? (
                <p className="text-[14px]" style={{ color: '#6B7280' }}>
                  This folder is empty.
                </p>
              ) : (
                <>
                  <p className="text-[14px] font-medium" style={{ color: '#1F3148' }}>
                    No documents yet.
                  </p>
                  <p className="text-[12px] mt-1" style={{ color: '#6B7280' }}>
                    Your firm will share documents here.
                  </p>
                </>
              )}
            </div>
          ) : (
            <>
              {showingFoldersOnly && !activeFolderId && (
                <h2 className="text-[13px] font-semibold mb-3" style={{ color: '#374151' }}>
                  All folders
                </h2>
              )}
              <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th
                      className="text-left px-5 py-3 text-[11px] font-medium"
                      style={{ color: '#9CA3AF' }}
                    >
                      Name
                    </th>
                    <th
                      className="text-left px-4 py-3 text-[11px] font-medium"
                      style={{ color: '#9CA3AF' }}
                    >
                      Type
                    </th>
                    <th
                      className="text-left px-4 py-3 text-[11px] font-medium"
                      style={{ color: '#9CA3AF' }}
                    >
                      Uploaded
                    </th>
                    <th
                      className="text-left px-4 py-3 text-[11px] font-medium"
                      style={{ color: '#9CA3AF' }}
                    >
                      Uploaded by
                    </th>
                    <th
                      className="text-right px-5 py-3 text-[11px] font-medium"
                      style={{ color: '#9CA3AF' }}
                    >
                      Size
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {/* Folder rows at top of table (root view, all-tab only) */}
                  {showFolderRows && folders.map((folder, idx) => {
                    const isLastFolder = idx === folders.length - 1 && displayed.length === 0
                    return (
                      <tr
                        key={`folder-${folder.id}`}
                        className={isLastFolder ? '' : 'border-b border-gray-50'}
                      >
                        <td className="px-5 py-3">
                          <button
                            type="button"
                            onClick={() => enterFolder(folder)}
                            className="flex items-center gap-2.5 min-w-0 text-left hover:opacity-80 transition-opacity w-full"
                          >
                            {/* Circular muted-gray badge matching PortalTodo task-row icon */}
                            <div
                              className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
                              style={{ backgroundColor: '#E5E7EB' }}
                            >
                              <Folder size={13} fill='#FBBF24' style={{ color: '#FBBF24' }} />
                            </div>
                            <span
                              className="text-[13px] font-medium truncate"
                              style={{ color: '#1F3148' }}
                            >
                              {folder.name}
                            </span>
                          </button>
                        </td>
                        {/* Type: blank for folder rows -- redundant with icon */}
                        <td className="px-4 py-3" />
                        <td className="px-4 py-3" />
                        <td className="px-4 py-3" />
                        <td className="px-5 py-3" />
                      </tr>
                    )
                  })}

                  {/* Document rows -- hidden in folders-only view */}
                  {!showingFoldersOnly && displayed.map((doc, idx) => {
                    // Split at last dot so truncation never cuts into the extension.
                    const dotIdx = doc.name.lastIndexOf('.')
                    const basename = dotIdx > 0 ? doc.name.slice(0, dotIdx) : doc.name
                    const ext = dotIdx > 0 ? doc.name.slice(dotIdx) : ''
                    const isLast = idx === displayed.length - 1
                    return (
                      <tr
                        key={doc.id}
                        className={isLast ? '' : 'border-b border-gray-50'}
                      >
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <FileIcon fileType={doc.file_type} />
                            <div className="flex items-baseline min-w-0">
                              <span
                                className="text-[13px] font-medium truncate"
                                style={{ color: '#1F3148' }}
                                title={doc.name}
                              >
                                {basename}
                              </span>
                              <span
                                className="text-[13px] font-medium flex-shrink-0"
                                style={{ color: '#1F3148' }}
                              >
                                {ext}
                              </span>
                            </div>
                          </div>
                        </td>
                        {/* Type: de-emphasized -- real data but secondary metadata */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="text-[11px]" style={{ color: '#9CA3AF' }}>
                            {doc.file_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="text-[12px]" style={{ color: '#6B7280' }}>
                            {formatDate(doc.uploaded_at)}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="text-[12px]" style={{ color: '#6B7280' }}>
                            {doc.uploaded_by === 'firm' ? firmName : 'You'}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-right whitespace-nowrap">
                          <span className="text-[12px]" style={{ color: '#6B7280' }}>
                            {formatFileSize(doc.file_size_kb)}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </div>
            </>
          )}
        </>
      )}

      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-4 right-4 z-50 rounded-xl px-4 py-3 text-[12px] min-w-[260px] max-w-[320px] shadow-lg border border-gray-100 bg-white"
          style={{ color: '#1F3148' }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
