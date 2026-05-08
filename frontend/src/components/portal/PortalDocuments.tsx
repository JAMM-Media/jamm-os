// frontend/src/components/portal/PortalDocuments.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { FileText, Upload } from 'lucide-react'
import { getPortalDocuments } from '@/lib/portal-api'
import type { PortalDocument as PortalDocumentItem } from '@/lib/portal-api'

function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

interface PortalDocumentsProps {
  firmName: string
}

export function PortalDocuments({ firmName }: PortalDocumentsProps) {
  const [documents, setDocuments] = useState<PortalDocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)

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
            className="h-8 px-4 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-5 flex flex-col gap-4 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em]">
          Documents ({documents.length})
        </p>
        <button className="flex items-center gap-1.5 h-8 px-3 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity">
          <Upload className="h-3.5 w-3.5" />
          Upload
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="flex flex-col items-center gap-1 py-12">
          <p className="text-[13px] font-medium text-[#EDEEF0]">No documents yet.</p>
          <p className="text-[12px] text-[#9CA3AF]">
            Your firm will share documents here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 bg-[#383838] rounded-[8px] px-4 py-3"
            >
              <FileText className="h-4 w-4 text-[#9CA3AF] flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-[#EDEEF0] truncate">{doc.name}</p>
                <p className="text-[11px] text-[#9CA3AF]">
                  {doc.file_type} · {formatFileSize(doc.file_size_kb)} ·{' '}
                  {doc.uploaded_at.split('T')[0]}
                </p>
              </div>
              <span className="text-[11px] text-[#9CA3AF] flex-shrink-0">
                {doc.uploaded_by === 'firm' ? firmName : 'Uploaded by you'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
