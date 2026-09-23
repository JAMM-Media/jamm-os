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


describe('FolderBrowser breadcrumb navigation', () => {
  // Fixture: root -> Parent Folder -> Child Folder (two-level tree)
  const parentFolder = { id: 'parent-id', name: 'Parent Folder', parent_folder_id: null }
  const childFolder = { id: 'child-id', name: 'Child Folder', parent_folder_id: 'parent-id' }

  function setupNavMocks() {
    // First api.get: folders endpoint returns both folders.
    // Second api.get: docs endpoint returns no documents.
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [parentFolder, childFolder] })
      .mockResolvedValueOnce({ data: { items: [] } })
    vi.mocked(documentFavoritesApi.list).mockResolvedValue([])
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // (a) At root, no breadcrumb exists -- navigationRootId is null.
  // 'All' is the reliable signal since it only renders inside the breadcrumb nav.
  it('shows no breadcrumb at root level', async () => {
    setupNavMocks()
    render(<FolderBrowser {...browserProps} />)
    await screen.findByText('Parent Folder')
    expect(screen.queryByText('All')).toBeNull()
  })

  // (b) Double-click Parent: breadcrumb appears with 'All' and 'Parent Folder'.
  // Parent Folder is the final segment, so it is a span, not a button.
  it('shows breadcrumb with Parent Folder as the current non-clickable segment after navigating in', async () => {
    const user = userEvent.setup()
    setupNavMocks()
    render(<FolderBrowser {...browserProps} />)
    await user.dblClick(await screen.findByText('Parent Folder'))
    expect(await screen.findByText('All')).toBeInTheDocument()
    // Final breadcrumb segment is a span, not a button.
    const segment = await screen.findByText('Parent Folder')
    expect(segment.tagName.toLowerCase()).toBe('span')
    expect(screen.queryByRole('button', { name: 'Parent Folder' })).toBeNull()
  })

  // (c) Double-click Child from inside Parent: breadcrumb shows All / Parent / Child.
  // Parent is now a button (no longer final); Child is the new non-clickable span.
  it('shows three-segment breadcrumb with Parent as button and Child as span after two-level navigation', async () => {
    const user = userEvent.setup()
    setupNavMocks()
    render(<FolderBrowser {...browserProps} />)
    // Navigate to Parent.
    await user.dblClick(await screen.findByText('Parent Folder'))
    // Child Folder is now visible as a row inside Parent.
    await user.dblClick(await screen.findByText('Child Folder'))
    // All still present.
    expect(await screen.findByText('All')).toBeInTheDocument()
    // Parent Folder is now a button (intermediate segment).
    expect(screen.getByRole('button', { name: 'Parent Folder' })).toBeInTheDocument()
    // Child Folder is the final span (non-clickable).
    await waitFor(() => {
      const childSegment = screen.getByText('Child Folder')
      expect(childSegment.tagName.toLowerCase()).toBe('span')
    })
    expect(screen.queryByRole('button', { name: 'Child Folder' })).toBeNull()
  })

  // (d) Click 'All' from Child level: breadcrumb disappears, root view restored.
  it('returns to root and removes breadcrumb when "All" is clicked', async () => {
    const user = userEvent.setup()
    setupNavMocks()
    render(<FolderBrowser {...browserProps} />)
    await user.dblClick(await screen.findByText('Parent Folder'))
    await user.dblClick(await screen.findByText('Child Folder'))
    await screen.findByText('All')
    await user.click(screen.getByText('All'))
    // Breadcrumb gone.
    await waitFor(() => {
      expect(screen.queryByText('All')).toBeNull()
    })
    // Root view: Parent Folder row is visible again.
    expect(await screen.findByText('Parent Folder')).toBeInTheDocument()
  })

  // (e) Click the intermediate 'Parent Folder' button from Child level: lands at
  // Parent level, not root. Breadcrumb shows 'All / Parent Folder' (Parent as span
  // now -- the new final segment), and Child Folder row is visible in the table.
  it('clicking an intermediate breadcrumb segment navigates to that level, not root', async () => {
    const user = userEvent.setup()
    setupNavMocks()
    render(<FolderBrowser {...browserProps} />)
    // Navigate to Child level.
    await user.dblClick(await screen.findByText('Parent Folder'))
    await user.dblClick(await screen.findByText('Child Folder'))
    // Click the intermediate 'Parent Folder' button in the breadcrumb.
    await user.click(screen.getByRole('button', { name: 'Parent Folder' }))
    // Breadcrumb shows All / Parent Folder with Parent as the non-clickable span.
    expect(await screen.findByText('All')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Parent Folder' })).toBeNull()
    })
    const parentSegment = screen.getByText('Parent Folder')
    expect(parentSegment.tagName.toLowerCase()).toBe('span')
    // Child Folder is visible as a row -- confirming we landed at Parent, not root.
    expect(screen.getByText('Child Folder')).toBeInTheDocument()
  })
})


describe('FolderBrowser Archived toggle', () => {
  // Fixture docs: one active (is_superseded:false), one archived (is_superseded:true).
  const activeDocRaw = {
    id: 'doc-active-1',
    filename: 'Current.pdf',
    content_type: 'application/pdf',
    size_bytes: 1024,
    folder_id: null,
    created_at: '2026-09-01T10:00:00Z',
    is_superseded: false,
    deleted_at: null,
  }
  const archivedDocRaw = {
    id: 'doc-archived-1',
    filename: 'Archived.pdf',
    content_type: 'application/pdf',
    size_bytes: 512,
    folder_id: null,
    created_at: '2026-09-01T09:00:00Z',
    is_superseded: true,
    deleted_at: null,
  }

  function setupArchivedMocks(items: typeof activeDocRaw[]) {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: { items } })
    vi.mocked(documentFavoritesApi.list).mockResolvedValue([])
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // (a) showArchivedToggle:false -- toggle absent even when superseded doc exists.
  // Tests the prop half of the gate independently.
  it('does not render the Archived toggle when showArchivedToggle is false', async () => {
    setupArchivedMocks([activeDocRaw, archivedDocRaw])
    render(<FolderBrowser {...browserProps} showArchivedToggle={false} />)
    await screen.findByText('Current.pdf')
    expect(screen.queryByText('Archived (1)')).toBeNull()
  })

  // (b) showArchivedToggle:true but zero superseded docs -- toggle absent.
  // Tests the data half of the gate independently; distinct from (a)'s reason.
  it('does not render the Archived toggle when no superseded documents exist', async () => {
    setupArchivedMocks([activeDocRaw])
    render(<FolderBrowser {...browserProps} showArchivedToggle={true} />)
    await screen.findByText('Current.pdf')
    expect(screen.queryByText('Archived (1)')).toBeNull()
  })

  // (c) Both conditions met: toggle appears with correct count. Active doc visible,
  // superseded doc hidden (real default showArchived:false state).
  it('shows "Archived (1)" toggle and hides the superseded doc by default', async () => {
    setupArchivedMocks([activeDocRaw, archivedDocRaw])
    render(<FolderBrowser {...browserProps} showArchivedToggle={true} />)
    await screen.findByText('Current.pdf')
    // Toggle present with real count.
    expect(screen.getByText('Archived (1)')).toBeInTheDocument()
    // Active doc visible, archived doc hidden.
    expect(screen.queryByText('Archived.pdf')).toBeNull()
  })

  // (d) Click toggle: archived doc becomes visible AND active doc remains visible.
  // This proves the real inclusive behavior (reveals archived alongside active),
  // distinct from the Favorites-only switch's exclusive (narrowing) behavior.
  it('reveals the superseded doc alongside the active doc after clicking the toggle', async () => {
    const user = userEvent.setup()
    setupArchivedMocks([activeDocRaw, archivedDocRaw])
    render(<FolderBrowser {...browserProps} showArchivedToggle={true} />)
    await screen.findByText('Current.pdf')
    // Click the toggle button (sibling of the "Archived (1)" span).
    const toggleBtn = screen.getByText('Archived (1)').parentElement!.querySelector('button')!
    await user.click(toggleBtn)
    // Both active and archived are now visible.
    await waitFor(() => {
      expect(screen.getByText('Archived.pdf')).toBeInTheDocument()
    })
    expect(screen.getByText('Current.pdf')).toBeInTheDocument()
  })

  // (e) Click toggle again: archived doc hidden, active doc still visible.
  // Proves the toggle is reversible.
  it('hides the superseded doc again after clicking the toggle a second time', async () => {
    const user = userEvent.setup()
    setupArchivedMocks([activeDocRaw, archivedDocRaw])
    render(<FolderBrowser {...browserProps} showArchivedToggle={true} />)
    await screen.findByText('Current.pdf')
    const toggleBtn = screen.getByText('Archived (1)').parentElement!.querySelector('button')!
    // Toggle on.
    await user.click(toggleBtn)
    await waitFor(() => expect(screen.getByText('Archived.pdf')).toBeInTheDocument())
    // Toggle off.
    await user.click(toggleBtn)
    await waitFor(() => expect(screen.queryByText('Archived.pdf')).toBeNull())
    expect(screen.getByText('Current.pdf')).toBeInTheDocument()
  })
})
