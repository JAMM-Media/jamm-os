// frontend/src/components/portal/PortalDocuments.tsx
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { FileText, Upload } from 'lucide-react'
import { getPortalDocuments } from '@/lib/portal-api'
import type { PortalDocument as PortalDocumentItem } from '@/lib/portal-api'

function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

interface PortalDocumentsProps {
  firmName: string
  accentColor?: string
}

export function PortalDocuments({ firmName, accentColor = '#3A6A94' }: PortalDocumentsProps) {
  const [documents, setDocuments] = useState<PortalDocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
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
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#383838] animate-pulse" />
        ))}
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-5 max-w-2xl mx-auto">
        <div className="bg-[#383838] rounded-[8px] px-4 py-6 flex flex-col items-center gap-3">
          <p className="text-[13px] text-[#9CA3AF]">Failed to load documents.</p>
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

  return (
    <div className="p-6 flex flex-col gap-5 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">
          Documents ({documents.length})
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

      {documents.length === 0 ? (
        <div className="flex flex-col items-center gap-1 py-12">
          <p className="text-[13px] font-medium text-[#EDEEF0]">No documents yet.</p>
          <p className="text-[12px] text-[#9CA3AF]">
            Your firm will share documents here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 bg-[#383838] rounded-[8px] px-5 py-4"
            >
              <FileText className="h-5 w-5 text-[#9CA3AF] flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-medium text-[#EDEEF0] truncate">{doc.name}</p>
                <p className="text-[12px] text-[#9CA3AF]">
                  {doc.file_type} · {formatFileSize(doc.file_size_kb)} ·{' '}
                  {doc.uploaded_at.split('T')[0]}
                </p>
              </div>
              <span className="text-[12px] text-[#9CA3AF] flex-shrink-0">
                {doc.uploaded_by === 'firm' ? firmName : 'Uploaded by you'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
