// frontend/src/app/(app)/engagements/[id]/page.test.ts
// Colocated with page.tsx, matching the convention established by
// FolderBrowser.test.ts and StatusBadge.test.tsx (both colocated).
// .ts not .tsx because contentTypeFromFilename is a pure function with no JSX.
import { describe, it, expect, vi } from 'vitest'

// next/navigation throws when hooks are *called* outside Next.js context,
// but does not throw on import. Stub it out to keep tests hermetic.
vi.mock('next/navigation', () => ({
  useParams: vi.fn(() => ({ id: 'test-id' })),
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}))

import { contentTypeFromFilename } from './page'

describe('contentTypeFromFilename', () => {
  // (a) .pdf
  it('returns application/pdf for a .pdf filename', () => {
    expect(contentTypeFromFilename('report.pdf')).toBe('application/pdf')
  })

  // (b) .xlsx and .xls both map to the same spreadsheet MIME string
  it('returns the Excel MIME type for .xlsx and .xls', () => {
    const expected = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    expect(contentTypeFromFilename('data.xlsx')).toBe(expected)
    expect(contentTypeFromFilename('legacy.xls')).toBe(expected)
  })

  // (c) .csv
  it('returns text/csv for a .csv filename', () => {
    expect(contentTypeFromFilename('export.csv')).toBe('text/csv')
  })

  // (d) All six image extensions return 'image/png' -- intentional simplification,
  // not the specific subtype. Documented here as known, intentional behavior.
  it('returns image/png for any recognized image extension, not the specific subtype', () => {
    expect(contentTypeFromFilename('photo.png')).toBe('image/png')
    expect(contentTypeFromFilename('photo.jpg')).toBe('image/png')
    expect(contentTypeFromFilename('photo.jpeg')).toBe('image/png')
    expect(contentTypeFromFilename('photo.gif')).toBe('image/png')
    expect(contentTypeFromFilename('photo.webp')).toBe('image/png')
    expect(contentTypeFromFilename('photo.svg')).toBe('image/png')
  })

  // (e) .docx and .doc both map to the same Word MIME string
  it('returns the Word MIME type for .docx and .doc', () => {
    const expected = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    expect(contentTypeFromFilename('letter.docx')).toBe(expected)
    expect(contentTypeFromFilename('legacy.doc')).toBe(expected)
  })

  // (f) Unrecognized extension falls back to application/octet-stream
  it('returns application/octet-stream for unrecognized extensions', () => {
    expect(contentTypeFromFilename('archive.zip')).toBe('application/octet-stream')
    expect(contentTypeFromFilename('notes.txt')).toBe('application/octet-stream')
  })

  // (g) No extension at all returns application/octet-stream without throwing
  it('returns application/octet-stream for a filename with no extension', () => {
    expect(contentTypeFromFilename('README')).toBe('application/octet-stream')
    expect(contentTypeFromFilename('makefile')).toBe('application/octet-stream')
  })

  // (h) Extension matching is case-insensitive (.PDF == .pdf)
  it('is case-insensitive: .PDF returns application/pdf', () => {
    expect(contentTypeFromFilename('REPORT.PDF')).toBe('application/pdf')
    expect(contentTypeFromFilename('DATA.XLSX')).toBe('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    expect(contentTypeFromFilename('PHOTO.JPG')).toBe('image/png')
  })
})