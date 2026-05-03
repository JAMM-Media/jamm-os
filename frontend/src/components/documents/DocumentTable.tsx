// frontend/src/components/documents/DocumentTable.tsx
'use client'

import { useRouter } from 'next/navigation'
import { MockDocument, formatFileSize } from '@/lib/mock/documents'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FileText } from 'lucide-react'

interface DocumentTableProps {
  documents: MockDocument[]
}

export function DocumentTable({ documents }: DocumentTableProps) {
  const router = useRouter()

  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface-card dark:bg-[#252525]">
            {['Document', 'Client', 'Engagement', 'Uploaded By', 'Date', 'Size', 'Status'].map((col) => (
              <th
                key={col}
                className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {documents.map((doc, i) => (
            <tr
              key={doc.id}
              onClick={() => router.push(`/documents/${doc.id}`)}
              className={[
                'group cursor-pointer transition-colors',
                'bg-surface-page dark:bg-dark-page',
                'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                i !== documents.length - 1
                  ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                  : '',
              ].join(' ')}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-[#6B7280] flex-shrink-0" />
                  <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                    {doc.name}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3">
                <span
                  onClick={(e) => { e.stopPropagation(); router.push(`/clients/${doc.clientId}`) }}
                  className="text-[12px] text-brand-light hover:underline cursor-pointer"
                >
                  {doc.clientName}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {doc.engagementTitle}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {doc.uploadedBy}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {doc.uploadedAt}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {formatFileSize(doc.fileSizeKb)}
                </span>
              </td>
              <td className="px-4 py-3">
                <StatusBadge variant={doc.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
