// frontend/src/components/documents/DocumentCard.tsx
'use client'

import { useRouter } from 'next/navigation'
import { Document } from '@/lib/api/documents'
import { formatFileSize } from '@/lib/utils'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FileText } from 'lucide-react'

interface DocumentCardProps {
  document: Document
}

export function DocumentCard({ document }: DocumentCardProps) {
  const router = useRouter()

  return (
    <div
      onClick={() => router.push(`/documents/${document.id}`)}
      className="bg-surface-card dark:bg-dark-card rounded-card p-[13px] cursor-pointer hover:brightness-95 dark:hover:brightness-110 transition-all"
    >
      <div className="flex items-start gap-2 mb-2">
        <FileText className="h-4 w-4 text-[#6B7280] flex-shrink-0 mt-0.5" />
        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] leading-tight">
          {document.name}
        </span>
      </div>
      <div className="text-[11px] text-[#6B7280] mb-1">
        {document.clientName}
      </div>
      <div className="text-[11px] text-[#6B7280] mb-2 truncate">
        {document.engagementTitle}
      </div>
      <div className="flex items-center justify-between">
        <StatusBadge variant={document.status} />
        <span className="text-[11px] text-[#6B7280]">
          {formatFileSize(document.fileSizeKb)} · {document.fileType}
        </span>
      </div>
    </div>
  )
}
