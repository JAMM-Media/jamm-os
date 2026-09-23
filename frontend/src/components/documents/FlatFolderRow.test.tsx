// frontend/src/components/documents/FlatFolderRow.test.tsx
// .tsx because this test renders real JSX via @testing-library/react.
// Colocated with FolderBrowser.tsx per this codebase's established convention.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
}))

vi.mock('@/lib/api/documents', () => ({
  documentsApi: {
    getSignedUrl: vi.fn().mockResolvedValue('https://example.com/file.pdf'),
    deleteDocument: vi.fn().mockResolvedValue(undefined),
  },
  documentFoldersApi: {
    moveDocument: vi.fn().mockResolvedValue(undefined),
    deleteFolder: vi.fn().mockResolvedValue(undefined),
  },
  documentFavoritesApi: {
    add: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('@/lib/api/engagements', () => ({
  engagementsApi: {
    addPin: vi.fn().mockResolvedValue(undefined),
    removePin: vi.fn().mockResolvedValue(undefined),
    listPins: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { FlatFolderRow } from './FolderBrowser'
import { documentFavoritesApi } from '@/lib/api/documents'
import { engagementsApi } from '@/lib/api/engagements'

// useConfirm runs for real: it uses only React state, ConfirmDialog is null
// until confirm() is called, and no test triggers the Delete flow.

const mockFolder = {
  id: 'folder-xyz-456',
  name: 'Test Folder',
  parent_folder_id: null,
  updated_at: '2026-09-01T10:00:00Z',
}

const baseProps = {
  folder: mockFolder,
  depth: 0,
  hasChildren: false,   // keeps DOM simple: no expand/collapse button
  isExpanded: false,
  onToggle: vi.fn(),
  isTargeted: false,
  onTarget: vi.fn(),
  onNavigate: vi.fn(),
  folders: [],
  childrenOf: {},
  onDropDoc: vi.fn(),
  onFolderChanged: vi.fn(),
  isFinalized: false,
  isPinned: false,
  isFavorited: false,
  canPin: true,
  engagementId: 'eng-123',
  onPinsChanged: vi.fn(),
  onFavoritesChanged: vi.fn(),
}

// Finds the star button (polygon element is unique to the star SVG).
function findStarButton(container: HTMLElement): HTMLButtonElement {
  const buttons = Array.from(container.querySelectorAll('button'))
  const btn = buttons.find(b => b.querySelector('polygon'))
  if (!btn) throw new Error('Star button (polygon) not found')
  return btn as HTMLButtonElement
}

// Finds the three-dot menu button (MoreVertical renders circles).
function findMenuButton(container: HTMLElement): HTMLButtonElement {
  const buttons = Array.from(container.querySelectorAll('button'))
  const btn = buttons.find(b => b.querySelector('circle'))
  if (!btn) throw new Error('Three-dot button (circle) not found')
  return btn as HTMLButtonElement
}

describe('FlatFolderRow pins', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(engagementsApi.addPin).mockResolvedValue(undefined)
    vi.mocked(engagementsApi.removePin).mockResolvedValue(undefined)
    vi.mocked(documentFavoritesApi.add).mockResolvedValue(undefined)
    vi.mocked(documentFavoritesApi.remove).mockResolvedValue(undefined)
  })

  // (a) isPinned:false -- no inline pin icon; "Pin to engagement" in menu.
  // The inline pin icon uses fill="#1F3148" (literal hex); dropdown pin button uses
  // fill="currentColor", so svg[fill="#1F3148"] uniquely identifies the inline icon.
  it('does not render the inline pin icon when isPinned is false, and shows "Pin to engagement" in the menu', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatFolderRow {...baseProps} isPinned={false} />)
    expect(container.querySelector('svg[fill="#1F3148"]')).toBeNull()
    await user.click(findMenuButton(container))
    expect(await screen.findByText('Pin to engagement')).toBeInTheDocument()
  })

  // (b) Click "Pin to engagement" -> engagementsApi.addPin called with correct args.
  it('calls engagementsApi.addPin with correct args when "Pin to engagement" is clicked', async () => {
    const user = userEvent.setup()
    const onPinsChanged = vi.fn()
    const { container } = render(
      <FlatFolderRow {...baseProps} isPinned={false} onPinsChanged={onPinsChanged} />
    )
    await user.click(findMenuButton(container))
    await user.click(await screen.findByText('Pin to engagement'))
    await waitFor(() => {
      expect(engagementsApi.addPin).toHaveBeenCalledTimes(1)
      expect(engagementsApi.addPin).toHaveBeenCalledWith('eng-123', 'folder', 'folder-xyz-456')
      expect(onPinsChanged).toHaveBeenCalledTimes(1)
    })
    expect(engagementsApi.removePin).not.toHaveBeenCalled()
  })

  // (c) isPinned:true -- inline pin icon present; clicking "Remove pin" calls removePin.
  // Pin icon selector: svg[fill="#1F3148"] -- literal hex used only by the inline icon,
  // not by the dropdown button which uses fill="currentColor".
  it('renders the inline pin icon when isPinned is true, and "Remove pin" calls removePin', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatFolderRow {...baseProps} isPinned={true} />)
    expect(container.querySelector('svg[fill="#1F3148"]')).not.toBeNull()
    await user.click(findMenuButton(container))
    await user.click(await screen.findByText('Remove pin'))
    await waitFor(() => {
      expect(engagementsApi.removePin).toHaveBeenCalledTimes(1)
      expect(engagementsApi.removePin).toHaveBeenCalledWith('eng-123', 'folder', 'folder-xyz-456')
    })
    expect(engagementsApi.addPin).not.toHaveBeenCalled()
  })

  // (d) canPin:false -- pin menu item absent; favorite item still present.
  // Tests the hide-not-disable pattern: the pin item is removed from the DOM entirely
  // (not disabled or hidden via opacity) when canPin is false.
  it('omits the pin menu item when canPin is false, while keeping "Add to Favorites"', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <FlatFolderRow {...baseProps} canPin={false} engagementId="eng-123" />
    )
    await user.click(findMenuButton(container))
    expect(screen.queryByText('Pin to engagement')).toBeNull()
    expect(screen.queryByText('Remove pin')).toBeNull()
    expect(await screen.findByText('Add to Favorites')).toBeInTheDocument()
  })

  // (e) canPin:true but engagementId:undefined -- pin menu item absent for a distinct
  // reason: the render condition is {canPin && engagementId && (...)}, so a missing
  // engagementId suppresses the item independently of canPin's value.
  // This is meaningfully different from (d): canPin is still true here; only the
  // engagementId is absent.
  it('omits pin menu item when engagementId is undefined even though canPin is true', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <FlatFolderRow {...baseProps} canPin={true} engagementId={undefined} />
    )
    await user.click(findMenuButton(container))
    expect(screen.queryByText('Pin to engagement')).toBeNull()
    expect(screen.queryByText('Remove pin')).toBeNull()
    // Favorites still present -- confirms item absence is pin-specific, not a full menu failure.
    expect(await screen.findByText('Add to Favorites')).toBeInTheDocument()
  })

  // (f) Star calls documentFavoritesApi.add with 'folder' item_type -- confirming the
  // correct item_type string, the one meaningful difference from FlatDocRow's behavior.
  it('calls documentFavoritesApi.add with item_type "folder" when the star is clicked', async () => {
    const user = userEvent.setup()
    const { container } = render(<FlatFolderRow {...baseProps} isFavorited={false} />)
    await user.click(findStarButton(container))
    await waitFor(() => {
      expect(documentFavoritesApi.add).toHaveBeenCalledTimes(1)
      expect(documentFavoritesApi.add).toHaveBeenCalledWith('folder', 'folder-xyz-456')
    })
  })
})