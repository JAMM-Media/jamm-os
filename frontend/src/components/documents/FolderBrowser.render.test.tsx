// frontend/src/components/documents/FolderBrowser.render.test.tsx
// Rendered-component tests for the Favorites-only filter switch.
// Kept separate from FolderBrowser.test.ts (pure-logic tests) per the
// established pattern: pure-logic tests and render tests in distinct files.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock next/navigation -- useRouter is used by FolderBrowser.
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
}))

// Mock the raw axios api client -- fetchFolders and fetchDocs call api.get.
// scope='client' means fetchPins returns early (no API call needed for pins).
vi.mock('@/lib/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}))

vi.mock('@/lib/api/engagements', () => ({
  engagementsApi: {
    listPins: vi.fn().mockResolvedValue([]),
    addPin: vi.fn().mockResolvedValue(undefined),
    removePin: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('@/lib/api/documents', () => ({
  documentsApi: {
    getSignedUrl: vi.fn().mockResolvedValue('https://example.com/file.pdf'),
    deleteDocument: vi.fn().mockResolvedValue(undefined),
  },
  documentFoldersApi: {
    moveDocument: vi.fn().mockResolvedValue(undefined),
    deleteFolder: vi.fn().mockResolvedValue(undefined),
    moveFolder: vi.fn().mockResolvedValue(undefined),
  },
  documentFavoritesApi: {
    add: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

import { FolderBrowser } from './FolderBrowser'
import api from '@/lib/api'
import { documentFavoritesApi } from '@/lib/api/documents'

// Raw API response shapes (before fetchDocs maps them to BrowserDoc).
const doc1Raw = {
  id: 'doc-1',
  filename: 'Alpha.pdf',
  content_type: 'application/pdf',
  size_bytes: 1024,
  folder_id: null,
  created_at: '2026-09-01T10:00:00Z',
  is_superseded: false,
  deleted_at: null,
}
const doc2Raw = {
  id: 'doc-2',
  filename: 'Beta.pdf',
  content_type: 'application/pdf',
  size_bytes: 512,
  folder_id: null,
  created_at: '2026-09-02T10:00:00Z',
  is_superseded: false,
  deleted_at: null,
}

// doc-1 is favorited; doc-2 is not.
const favoritesWithDoc1 = [
  { id: 'fav-1', item_type: 'document', item_id: 'doc-1', name: 'Alpha.pdf' },
]

function setupApiMocks({ hasFavorites }: { hasFavorites: boolean }) {
  // First call: folders endpoint returns empty list.
  // Second call: docs endpoint returns both documents.
  vi.mocked(api.get)
    .mockResolvedValueOnce({ data: [] })
    .mockResolvedValueOnce({ data: { items: [doc1Raw, doc2Raw] } })
  vi.mocked(documentFavoritesApi.list).mockResolvedValue(
    hasFavorites ? favoritesWithDoc1 : [],
  )
}

const browserProps = {
  scope: 'client' as const,
  clientId: 'client-123',
  isFinalized: false,
  canPin: false,
  showArchivedToggle: false,
}

describe('FolderBrowser Favorites-only switch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // (a) When zero items are favorited the switch must not appear at all.
  // Waiting for 'Alpha.pdf' guarantees we are past the loading skeleton
  // (which only renders pulse divs, not filenames).
  it('does not render the Favorites switch when no items are favorited', async () => {
    setupApiMocks({ hasFavorites: false })
    render(<FolderBrowser {...browserProps} />)
    // Wait past loading state.
    await screen.findByText('Alpha.pdf')
    expect(screen.queryByRole('switch')).toBeNull()
  })

  // (b) When at least one item is favorited the switch appears with aria-checked="false".
  it('renders the Favorites switch with aria-checked="false" when favorites exist', async () => {
    setupApiMocks({ hasFavorites: true })
    render(<FolderBrowser {...browserProps} />)
    await screen.findByText('Alpha.pdf')
    const sw = screen.getByRole('switch')
    expect(sw).toBeInTheDocument()
    expect(sw).toHaveAttribute('aria-checked', 'false')
  })

  // (c) Toggling the switch on hides non-favorited documents and keeps favorited ones.
  // This test proves the filter changes actual rendered content, not just aria state.
  it('clicking the switch filters rows to only favorited documents', async () => {
    const user = userEvent.setup()
    setupApiMocks({ hasFavorites: true })
    render(<FolderBrowser {...browserProps} />)
    // Wait past loading -- both docs visible before filter.
    await screen.findByText('Alpha.pdf')
    expect(screen.getByText('Beta.pdf')).toBeInTheDocument()

    await user.click(screen.getByRole('switch'))

    await waitFor(() => {
      expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    })
    // Favorited doc still visible.
    expect(screen.getByText('Alpha.pdf')).toBeInTheDocument()
    // Non-favorited doc no longer in the DOM.
    expect(screen.queryByText('Beta.pdf')).toBeNull()
  })

  // (d) Toggling the switch off restores both documents.
  it('clicking the switch again shows all documents again', async () => {
    const user = userEvent.setup()
    setupApiMocks({ hasFavorites: true })
    render(<FolderBrowser {...browserProps} />)
    await screen.findByText('Alpha.pdf')

    // Toggle on.
    await user.click(screen.getByRole('switch'))
    await waitFor(() => {
      expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    })
    expect(screen.queryByText('Beta.pdf')).toBeNull()

    // Toggle off.
    await user.click(screen.getByRole('switch'))
    await waitFor(() => {
      expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
    })
    expect(screen.getByText('Alpha.pdf')).toBeInTheDocument()
    expect(screen.getByText('Beta.pdf')).toBeInTheDocument()
  })
})

describe('FolderBrowser isFinalized gates', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Upload, New Folder, and Bulk Import are hidden entirely (not disabled) when
  // isFinalized is true -- the real {!isFinalized && (...)} pattern.
  it('Upload, New Folder, and Bulk Import buttons are absent when isFinalized is true', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: { items: [doc1Raw, doc2Raw] } })
    vi.mocked(documentFavoritesApi.list).mockResolvedValue([])
    render(<FolderBrowser {...browserProps} isFinalized={true} />)
    // Wait past loading state.
    await screen.findByText('Alpha.pdf')
    expect(screen.queryByText('Upload')).toBeNull()
    expect(screen.queryByText('New Folder')).toBeNull()
    expect(screen.queryByText('Bulk Import')).toBeNull()
  })

  // The empty-state message switches to 'This engagement is finalized.' when
  // isFinalized is true, distinct from the normal 'No files or folders yet.' message.
  it('shows "This engagement is finalized." as the empty-state message when finalized', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: { items: [] } })
    vi.mocked(documentFavoritesApi.list).mockResolvedValue([])
    render(<FolderBrowser {...browserProps} isFinalized={true} />)
    // findByText waits past the loading skeleton.
    expect(await screen.findByText('This engagement is finalized.')).toBeInTheDocument()
    expect(screen.queryByText('No files or folders yet.')).toBeNull()
  })
})

// Step 4 (drop-blocking): DragEvent.dataTransfer is a read-only property in the
// DOM spec. fireEvent.drop in happy-dom cannot inject getData-returning data into
// the synthetic event, making it impossible to verify that the isFinalized early
// return (not an empty docId) is what blocked onDropDoc. Skipped as a genuine
// environment limitation rather than forced with a test that proves nothing.
