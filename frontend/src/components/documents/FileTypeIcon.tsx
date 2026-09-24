// frontend/src/components/documents/FileTypeIcon.tsx
// Shared file-type badge extracted from firm-library/page.tsx.
// Takes any MIME type string (content_type from Document rows, mimeType from
// ImportItem rows -- both are standard MIME strings, compatible with the
// includes-based matching below).

import { FileText } from 'lucide-react'
import { cn } from '@/lib/utils'

export function fileTypeLabel(contentType: string): string {
  if (contentType.includes('pdf')) return 'PDF'
  if (contentType.includes('word') || contentType.includes('docx') || contentType.includes('document')) return 'Word'
  if (contentType.includes('excel') || contentType.includes('xlsx') || contentType.includes('spreadsheet')) return 'Excel'
  if (contentType.includes('powerpoint') || contentType.includes('pptx') || contentType.includes('presentation')) return 'PPT'
  if (contentType.includes('image')) return 'Image'
  if (contentType.includes('text')) return 'Text'
  if (contentType.includes('csv')) return 'CSV'
  return 'File'
}

interface FileTypeIconProps {
  contentType: string
  className?: string
}

export function FileTypeIcon({ contentType, className }: FileTypeIconProps) {
  let bgColor = '#6B7280'
  const label = fileTypeLabel(contentType)
  if (label === 'PDF') bgColor = '#DC2626'
  else if (label === 'Word') bgColor = '#2563EB'
  else if (label === 'Excel') bgColor = '#16A34A'
  else if (label === 'PPT') bgColor = '#D97706'
  else if (label === 'Image') bgColor = '#7C3AED'
  return (
    <div
      className={cn('flex items-center justify-center rounded flex-shrink-0', className ?? 'w-8 h-8')}
      style={{ backgroundColor: bgColor }}
    >
      <FileText className="h-4 w-4 text-white" />
    </div>
  )
}
