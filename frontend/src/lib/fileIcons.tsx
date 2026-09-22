// frontend/src/lib/fileIcons.tsx
import { type ReactElement } from 'react'
import { FileText, FileSpreadsheet, FileImage, File as FileGeneric, Presentation, Mail, FileArchive } from 'lucide-react'

// PowerPoint check must precede word/document: the .pptx MIME string
// 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
// contains the substring 'document', which would otherwise match the Word case.
export function fileIconFromContentType(contentType: string): ReactElement {
  if (contentType === 'application/pdf') {
    return <FileText size={15} style={{ color: '#EF4444' }} className="flex-shrink-0" />
  }
  if (
    contentType.includes('spreadsheet') ||
    contentType === 'text/csv' ||
    contentType === 'application/vnd.ms-excel' ||
    contentType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ) {
    return <FileSpreadsheet size={15} style={{ color: '#10B981' }} className="flex-shrink-0" />
  }
  if (contentType.startsWith('image/')) {
    return <FileImage size={15} style={{ color: '#8B5CF6' }} className="flex-shrink-0" />
  }
  if (contentType.includes('presentation') || contentType === 'application/vnd.ms-powerpoint') {
    return <Presentation size={15} style={{ color: '#F97316' }} className="flex-shrink-0" />
  }
  if (contentType.includes('word') || contentType.includes('document')) {
    return <FileGeneric size={15} style={{ color: '#3B82F6' }} className="flex-shrink-0" />
  }
  if (contentType === 'message/rfc822' || contentType === 'application/vnd.ms-outlook') {
    return <Mail size={15} style={{ color: '#14B8A6' }} className="flex-shrink-0" />
  }
  if (contentType.includes('zip') || contentType.includes('compressed') || contentType.includes('gzip')) {
    return <FileArchive size={15} style={{ color: '#92400E' }} className="flex-shrink-0" />
  }
  return <FileGeneric size={15} style={{ color: '#9CA3AF' }} className="flex-shrink-0" />
}
