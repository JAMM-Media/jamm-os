// frontend/src/components/portal/PortalDocuments.tsx
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { FileText, Upload, ChevronDown, ChevronUp } from 'lucide-react'
import { getPortalDocuments } from '@/lib/portal-api'
import type { PortalDocument as PortalDocumentItem } from '@/lib/portal-api'

function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

interface PortalDocumentsProps {
  firmName: string
  accentColor?: string
  cardColor?: string
  portalMode?: 'light' | 'dark'
  textPrimary?: string
  textMuted?: string
}

export function PortalDocuments({ firmName, accentColor = '#3A6A94', cardColor = '#383838', portalMode = 'dark', textPrimary = '#EDEEF0', textMuted = '#9CA3AF' }: PortalDocumentsProps) {
  const primaryText = textPrimary
  const mutedText = textMuted

  const [documents, setDocuments] = useState<PortalDocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setToast('Upload coming soon — document uploads will be available in the next update.')
    setTimeout(() => setToast(null), 4000)
    e.target.value = ''
  }

  const fetchDocuments = useCallback(async () => {
    setLoading(true)
    setFetchError(false)
    try {
      const data = await getPortalDocuments()
      setDocuments(data)
    } catch {
      setFetchError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  if (loading) {
    const barStyle = { backgroundColor: portalMode === 'light' ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.12)' }
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-3 rounded-[8px] px-5 py-4" style={{ backgroundColor: cardColor }}>
            <div className="h-5 w-5 rounded flex-shrink-0 animate-pulse" style={barStyle} />
            <div className="flex-1 flex flex-col gap-1.5 min-w-0">
              <div className="h-3 w-[55%] rounded animate-pulse" style={barStyle} />
              <div className="h-3 w-[40%] rounded animate-pulse" style={barStyle} />
            </div>
            <div className="h-3 w-20 rounded flex-shrink-0 animate-pulse" style={barStyle} />
          </div>
        ))}
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-5 max-w-2xl mx-auto">
        <div className="rounded-[8px] px-4 py-6 flex flex-col items-center gap-3" style={{ backgroundColor: cardColor }}>
          <p className="text-[13px]" style={{ color: mutedText }}>Failed to load documents.</p>
          <button
            onClick={fetchDocuments}
            className="h-8 px-4 rounded-[6px] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            style={{ backgroundColor: accentColor }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const activeDocs = documents.filter((d) => !d.is_superseded)
  const archivedDocs = documents.filter((d) => d.is_superseded)

  return (
    <div className="p-6 flex flex-col gap-5 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-medium uppercase tracking-[0.05em]" style={{ color: mutedText }}>
          Documents ({activeDocs.length})
        </p>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1.5 h-8 px-3 rounded-[6px] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
          style={{ backgroundColor: accentColor }}
        >
          <Upload className="h-3.5 w-3.5" />
          Upload
        </button>
      </div>
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
        onChange={handleFileChange}
      />
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 rounded-[8px] px-4 py-3 text-[12px] min-w-[260px] max-w-[320px] shadow-lg" style={{ backgroundColor: '#383838', borderLeft: '3px solid #10B981', color: '#EDEEF0' }}>
          {toast}
        </div>
      )}

      {activeDocs.length === 0 && archivedDocs.length === 0 ? (
        <div className="flex flex-col items-center gap-1 py-12">
          <p className="text-[13px] font-medium" style={{ color: primaryText }}>No documents yet.</p>
          <p className="text-[12px]" style={{ color: mutedText }}>
            Your firm will share documents here.
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {activeDocs.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 rounded-[8px] px-5 py-4"
                style={{ backgroundColor: cardColor }}
              >
                <FileText className="h-5 w-5 flex-shrink-0" style={{ color: mutedText }} />
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] font-medium truncate" style={{ color: primaryText }}>{doc.name}</p>
                  <p className="text-[12px]" style={{ color: mutedText }}>
                    {doc.file_type} · {formatFileSize(doc.file_size_kb)} ·{' '}
                    {doc.uploaded_at.split('T')[0]}
                  </p>
                </div>
                <span className="text-[12px] flex-shrink-0" style={{ color: mutedText }}>
                  {doc.uploaded_by === 'firm' ? firmName : 'Uploaded by you'}
                </span>
              </div>
            ))}
          </div>

          {archivedDocs.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-medium uppercase tracking-[0.05em]" style={{ color: mutedText }}>
                  Archived ({archivedDocs.length})
                </span>
                <button
                  onClick={() => setShowArchived((v) => !v)}
                  className="p-0.5 rounded hover:opacity-80 transition-opacity"
                  style={{ color: mutedText }}
                >
                  {showArchived ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
              </div>
              {showArchived && (
                <div className="flex flex-col gap-3" style={{ opacity: 0.6 }}>
                  {archivedDocs.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center gap-3 rounded-[8px] px-5 py-4"
                      style={{ backgroundColor: cardColor }}
                    >
                      <FileText className="h-5 w-5 flex-shrink-0" style={{ color: mutedText }} />
                      <div className="flex-1 min-w-0 flex items-center gap-2">
                        <p className="text-[14px] font-medium truncate" style={{ color: primaryText }}>{doc.name}</p>
                        <span className="flex-shrink-0 rounded px-1.5 py-0.5 text-[10px]" style={{ backgroundColor: cardColor, color: mutedText, border: `1px solid ${mutedText}33` }}>
                          Archived
                        </span>
                      </div>
                      <span className="text-[12px] flex-shrink-0" style={{ color: mutedText }}>
                        {doc.uploaded_by === 'firm' ? firmName : 'Uploaded by you'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
