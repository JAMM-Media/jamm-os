// frontend/src/components/documents/FlatDocRow.test.tsx
// .tsx because this test renders real JSX components via @testing-library/react.
// Colocated with FolderBrowser.tsx per this codebase's established convention.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock next/navigation -- useRouter is imported by FolderBrowser.tsx and
// throws when called outside a Next.js context.
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
}))

// Mock the documents API module. documentFavoritesApi is the function under
// test; documentsApi and documentFoldersApi are mocked so no HTTP calls are
// made if other handlers were accidentally triggered.
vi.mock('@/lib/api/documents', () => ({
  documentsApi: {
    getSignedUrl: vi.fn().mockResolvedValue('https://example.com/file.pdf'),
    deleteDocument: vi.fn().mockResolvedValue(undefined),
  },
  documentFoldersApi: {
    moveDocument: vi.fn().mockResolvedValue(undefined),
  },
  documentFavoritesApi: {
    add: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue([]),
  },
}))

// Mock sonner to suppress toast output and allow assertions.
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

// Imports must come after vi.mock calls (vitest hoists mocks, but the import
// of the mocked module needs to happen after the factory is registered).
import { FlatDocRow } from './FolderBrowser'
import { documentFavoritesApi } from '@/lib/api/documents'
import { toast } from 'sonner'

// useConfirm does NOT need mocking: it uses only React state, renders null for
// ConfirmDialog until confirm() is called, and confirm() is never triggered
// since none of these tests click the Delete button.

const mockDoc = {
  id: 'doc-abc-123',
  filename: 'test-document.pdf',
  content_type: 'application/pdf',
  size_bytes: 1024,
  folder_id: null,
  created_at: '2026-09-01T10:00:00Z',
  is_superseded: false,
}

const baseProps = {
  doc: mockDoc,
  depth: 0,
  folders: [],
  fetchDocs: vi.fn(),
  isFinalized: false,
  isPinned: false,
  isFavorited: false,
  canPin: false,
  engagementId: undefined,
  onPinsChanged: vi.fn(),
  onFavoritesChanged: vi.fn(),
}

// Finds the star button (contains a polygon element unique to the star SVG).
// Avoids CSS :has() for happy-dom compatibility; uses querySelectorAll + find.
function findStarButton(container: HTMLElement): HTMLButtonElement {
  const buttons = Array.from(container.querySelectorAll('button'))
  const btn = buttons.find(b => b.querySelector('polygon'))
  if (!btn) throw new Error('Star button (polygon) not found in rendered output')
  return btn as HTMLButtonElement
}

// Finds the three-dot menu button (MoreVertical renders as circles).
function findMenuButton(container: HTMLElement): HTMLButtonElement {
  const buttons = Array.from(container.querySelectorAll('button'))
  const btn = buttons.find(b => b.querySelector('circle'))
  if (!btn) throw new Error('Three-dot menu button (circle) not found in rendered output')
  return btn as HTMLButtonElement
}

describe('FlatDocRow favorites', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Restore default resolved behavior after any per-test override.
    vi.mocked(documentFavoritesApi.add).mockResolvedValue(undefined)
    vi.mocked(documentFavoritesApi.remove).mockResolvedValue(undefined)
  })

  // (a) Unfavorited state: star SVG has fill="none" stroke="#9CA3AF".
  // Reliable selector: fill="#9CA3AF" is unique to the unfavorited star
  // (lucide icons use stroke="currentColor", not a literal hex; fill="#F5B942" absent).
  it('renders the star in unfavorited state when isFavorited is false', () => {
    const { container } = render(<FlatDocRow {...baseProps} isFavorited={false} />)
    // Favorited gold star must be absent.
    expect(container.querySelector('svg[fill="#F5B942"]')).toBeNull()
    // Unfavorited outline star must be present (fill="none" + literal stroke hex).
    expect(container.querySelector('svg[fill="none"][stroke="#9CA3AF"]')).not.toBeNull()
  })

  // (b) Click star (unfavorited) -> documentFavoritesApi.add called with correct args.
  it('calls documentFavoritesApi.add with correct args when star is clicked while unfavorited', async () => {
    const user = userEvent.setup()
    const onFavoritesChanged = vi.fn()
    const { container } = render(
      <FlatDocRow {...baseProps} isFavorited={false} onFavoritesChanged={onFavoritesChanged} />
    )
    await user.click(findStarButton(container))
    await waitFor(() => {
      expect(documentFavoritesApi.add).toHaveBeenCalledTimes(1)
      expect(documentFavoritesApi.add).toHaveBeenCalledWith('document', 'doc-abc-123')
      expect(onFavoritesChanged).toHaveBeenCalledTimes(1)
    })
    expect(documentFavoritesApi.remove).not.toHaveBeenCalled()
  })

  // (c) Favorited state: star SVG has fill="#F5B942".
  it('renders the star in favorited state when isFavorited is true', () => {
    const { container } = render(<FlatDocRow {...baseProps} isFavorited={true} />)
    expect(container.querySelector('svg[fill="#F5B942"]')).not.toBeNull()
    expect(container.querySelector('svg[fill="none"][stroke="#9CA3AF"]')).toBeNull()
  })

  // (d) Click star (favorited) -> documentFavoritesApi.remove called, not .add.
  it('calls documentFavoritesApi.remove when star is clicked while favorited', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatDocRow {...baseProps} isFavorited={true} />)
    await user.click(findStarButton(container))
    await waitFor(() => {
      expect(documentFavoritesApi.remove).toHaveBeenCalledTimes(1)
      expect(documentFavoritesApi.remove).toHaveBeenCalledWith('document', 'doc-abc-123')
    })
    expect(documentFavoritesApi.add).not.toHaveBeenCalled()
  })

  // (e) "Add to Favorites" menu item calls documentFavoritesApi.add with identical
  // args to clicking the star -- proving both controls call the same logic, not two
  // independent implementations that happen to look similar.
  it('"Add to Favorites" in three-dot menu calls .add with the same args as the star', async () => {
    const user = userEvent.setup()
    const onFavoritesChanged = vi.fn()
    const { container } = render(
      <FlatDocRow {...baseProps} isFavorited={false} onFavoritesChanged={onFavoritesChanged} />
    )
    // Open the three-dot menu (portaled to document.body).
    await user.click(findMenuButton(container))
    // Menu is rendered via createPortal; use screen to search document-wide.
    const menuItem = await screen.findByText('Add to Favorites')
    await user.click(menuItem)
    await waitFor(() => {
      expect(documentFavoritesApi.add).toHaveBeenCalledTimes(1)
      expect(documentFavoritesApi.add).toHaveBeenCalledWith('document', 'doc-abc-123')
      expect(onFavoritesChanged).toHaveBeenCalledTimes(1)
    })
  })

  // (f) API rejection -> toast.error called, onFavoritesChanged NOT called.
  it('calls toast.error and withholds onFavoritesChanged when the API rejects', async () => {
    vi.mocked(documentFavoritesApi.add).mockRejectedValueOnce(new Error('Network error'))
    const user = userEvent.setup()
    const onFavoritesChanged = vi.fn()
    const { container } = render(
      <FlatDocRow {...baseProps} isFavorited={false} onFavoritesChanged={onFavoritesChanged} />
    )
    await user.click(findStarButton(container))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledTimes(1)
    })
    expect(onFavoritesChanged).not.toHaveBeenCalled()
  })
})

describe('FlatDocRow double-click to open', () => {
  let mockWindowOpen: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(documentFavoritesApi.add).mockResolvedValue(undefined)
    vi.mocked(documentFavoritesApi.remove).mockResolvedValue(undefined)
    // happy-dom provides window.open but it is not a spy by default.
    // vi.stubGlobal replaces the global with a real vi.fn() for assertions.
    mockWindowOpen = vi.fn()
    vi.stubGlobal('open', mockWindowOpen)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // (a) Single click on the name-cell area does NOT call getSignedUrl or window.open.
  // The name-cell div has onDoubleClick={handleOpen} but no onClick -- a single click
  // fires no dblclick event and therefore never enters handleOpen.
  it('single click does not call getSignedUrl or window.open', async () => {
    const user = userEvent.setup()
    render(<FlatDocRow {...baseProps} />)
    await user.click(screen.getByText('test-document.pdf'))
    expect(documentFavoritesApi.add).not.toHaveBeenCalled()  // star not clicked
    // documentsApi.getSignedUrl is mocked via vi.mock above
    // Access the mock directly through the mocked module
    const { documentsApi: mockDocsApi } = await import('@/lib/api/documents') as any
    expect(mockDocsApi.getSignedUrl).not.toHaveBeenCalled()
    expect(mockWindowOpen).not.toHaveBeenCalled()
  })

  // (b) Double-click calls getSignedUrl with the real doc id, then window.open with
  // the resolved URL and '_blank'. Uses waitFor to confirm the real async chain
  // completes -- getSignedUrl resolves first, then window.open is called.
  it('double-click calls getSignedUrl with the doc id and window.open with the resolved URL', async () => {
    const user = userEvent.setup()
    render(<FlatDocRow {...baseProps} />)
    await user.dblClick(screen.getByText('test-document.pdf'))
    const { documentsApi: mockDocsApi } = await import('@/lib/api/documents') as any
    await waitFor(() => {
      expect(mockDocsApi.getSignedUrl).toHaveBeenCalledTimes(1)
      expect(mockDocsApi.getSignedUrl).toHaveBeenCalledWith('doc-abc-123')
      expect(mockWindowOpen).toHaveBeenCalledTimes(1)
      expect(mockWindowOpen).toHaveBeenCalledWith('https://example.com/file.pdf', '_blank')
    })
  })

  // (c) getSignedUrl rejection -> toast.error called, window.open NOT called.
  // A failed open should not partially succeed.
  it('calls toast.error and does not call window.open when getSignedUrl rejects', async () => {
    const user = userEvent.setup()
    const { documentsApi: mockDocsApi } = await import('@/lib/api/documents') as any
    mockDocsApi.getSignedUrl.mockRejectedValueOnce(new Error('Network error'))
    render(<FlatDocRow {...baseProps} />)
    await user.dblClick(screen.getByText('test-document.pdf'))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledTimes(1)
    })
    expect(mockWindowOpen).not.toHaveBeenCalled()
  })

  // (d) Clicking the star does not call getSignedUrl or window.open.
  // The star is a sibling of the name-cell div, not a child, so its click
  // cannot reach the name-cell's onDoubleClick handler regardless of propagation.
  it('clicking the star does not call getSignedUrl or window.open', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatDocRow {...baseProps} isFavorited={false} />)
    await user.click(findStarButton(container))
    const { documentsApi: mockDocsApi } = await import('@/lib/api/documents') as any
    await waitFor(() => {
      expect(documentFavoritesApi.add).toHaveBeenCalledTimes(1)
    })
    expect(mockDocsApi.getSignedUrl).not.toHaveBeenCalled()
    expect(mockWindowOpen).not.toHaveBeenCalled()
  })

  // (e) Opening the three-dot menu and clicking "Add to Favorites" does not call
  // getSignedUrl or window.open -- menu interactions are isolated from the open handler.
  it('clicking "Add to Favorites" in the menu does not call getSignedUrl or window.open', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatDocRow {...baseProps} isFavorited={false} />)
    await user.click(findMenuButton(container))
    await user.click(await screen.findByText('Add to Favorites'))
    const { documentsApi: mockDocsApi } = await import('@/lib/api/documents') as any
    await waitFor(() => {
      expect(documentFavoritesApi.add).toHaveBeenCalledTimes(1)
    })
    expect(mockDocsApi.getSignedUrl).not.toHaveBeenCalled()
    expect(mockWindowOpen).not.toHaveBeenCalled()
  })
})


describe('FlatDocRow isFinalized gates', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(documentFavoritesApi.add).mockResolvedValue(undefined)
  })

  it('Move to Folder button is disabled when isFinalized is true', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatDocRow {...baseProps} isFinalized={true} />)
    await user.click(findMenuButton(container))
    const btn = await screen.findByText('Move to Folder')
    expect(btn).toBeDisabled()
  })

  it('Delete button is disabled when isFinalized is true', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatDocRow {...baseProps} isFinalized={true} />)
    await user.click(findMenuButton(container))
    const btn = await screen.findByText('Delete')
    expect(btn).toBeDisabled()
  })
})
