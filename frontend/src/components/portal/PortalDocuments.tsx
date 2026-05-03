// frontend/src/components/portal/PortalDocuments.tsx
'use client'

import { useState, useEffect } from 'react'
import { FileText, Upload } from 'lucide-react'

interface PortalDocumentItem {
  id: string
  name: string
  uploaded_at: string
  file_type: string
  file_size_kb: number
  uploaded_by: 'client' | 'firm'
}

function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

export function PortalDocuments() {
  const [documents, setDocuments] = useState<PortalDocumentItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    fetch('/api/backend/portal/documents', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setDocuments(Array.isArray(data) ? data : []))
      .catch(() => setDocuments([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#383838] animate-pulse" />
        ))}
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
          <p className="text-[12px] text-[#9CA3AF]">Documents shared with you will appear here.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 bg-[#383838] rounded-[8px] px-4 py-3 cursor-pointer hover:brightness-110 transition-all"
            >
              <FileText className="h-4 w-4 text-[#9CA3AF] flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-[#EDEEF0] truncate">{doc.name}</p>
                <p className="text-[11px] text-[#9CA3AF]">
                  {doc.file_type} · {formatFileSize(doc.file_size_kb)} · {doc.uploaded_at.split('T')[0]}
                </p>
              </div>
              <span className="text-[11px] text-[#9CA3AF] flex-shrink-0">
                {doc.uploaded_by === 'firm' ? 'From firm' : 'Uploaded by you'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
