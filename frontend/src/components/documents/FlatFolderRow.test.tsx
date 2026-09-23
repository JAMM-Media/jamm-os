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

describe('FlatFolderRow click and double-click handlers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(documentFavoritesApi.add).mockResolvedValue(undefined)
    vi.mocked(documentFavoritesApi.remove).mockResolvedValue(undefined)
    vi.mocked(engagementsApi.addPin).mockResolvedValue(undefined)
    vi.mocked(engagementsApi.removePin).mockResolvedValue(undefined)
  })

  // (a) Single click calls onTarget exactly once and does NOT call onNavigate.
  it('single click calls onTarget once and does not call onNavigate', async () => {
    const user = userEvent.setup()
    const onTarget = vi.fn()
    const onNavigate = vi.fn()
    render(<FlatFolderRow {...baseProps} onTarget={onTarget} onNavigate={onNavigate} />)
    await user.click(screen.getByText('Test Folder'))
    expect(onTarget).toHaveBeenCalledTimes(1)
    expect(onNavigate).not.toHaveBeenCalled()
  })

  // (b) Double-click calls onNavigate exactly once.
  // The browser's real dblclick event sequence is: click -> click -> dblclick.
  // userEvent.dblClick faithfully simulates this sequence, meaning onClick fires
  // twice (onTarget called twice) and onDoubleClick fires once (onNavigate called once).
  // The onTarget call count below is empirically observed from the real event dispatch,
  // not assumed: two click events precede every dblclick in the DOM event spec.
  it('double-click calls onNavigate once; onTarget is called twice (once per click in the dblclick sequence)', async () => {
    const user = userEvent.setup()
    const onTarget = vi.fn()
    const onNavigate = vi.fn()
    render(<FlatFolderRow {...baseProps} onTarget={onTarget} onNavigate={onNavigate} />)
    await user.dblClick(screen.getByText('Test Folder'))
    expect(onNavigate).toHaveBeenCalledTimes(1)
    // Empirically observed: userEvent.dblClick fires click+click+dblclick.
    // onTarget (onClick) fires for each click event, so exactly 2 calls.
    // Two calls to the real toggle-based onTarget cancel out (set then unset),
    // leaving the targeted state unchanged -- the reasoning proven by assertion.
    expect(onTarget).toHaveBeenCalledTimes(2)
  })

  // (c) Clicking the chevron/expand button does NOT call onTarget or onNavigate.
  // The chevron is inside the name-cell div; e.stopPropagation() on the chevron's
  // onClick is the real, load-bearing guard preventing the click from reaching
  // the name-cell div's onClick={onTarget} handler.
  it('clicking the chevron expand button does not call onTarget or onNavigate', async () => {
    const user = userEvent.setup()
    const onTarget = vi.fn()
    const onNavigate = vi.fn()
    const onToggle = vi.fn()
    render(
      <FlatFolderRow
        {...baseProps}
        hasChildren={true}
        isExpanded={false}
        onToggle={onToggle}
        onTarget={onTarget}
        onNavigate={onNavigate}
      />
    )
    // The chevron button has neither polygon (star) nor circle (MoreVertical).
    const buttons = Array.from(document.querySelectorAll('button'))
    const chevronBtn = buttons.find(b => !b.querySelector('polygon') && !b.querySelector('circle'))
    expect(chevronBtn).not.toBeNull()
    await user.click(chevronBtn as HTMLElement)
    expect(onToggle).toHaveBeenCalledTimes(1)
    expect(onTarget).not.toHaveBeenCalled()
    expect(onNavigate).not.toHaveBeenCalled()
  })

  // (d) Clicking the star button does NOT call onTarget or onNavigate.
  // The star is a sibling of the name-cell div (not a child), so its click
  // cannot reach the name-cell div's onClick by bubbling. e.stopPropagation()
  // on the star additionally prevents the event from reaching any ancestor.
  it('clicking the star button does not call onTarget or onNavigate', async () => {
    const user = userEvent.setup()
    const onTarget = vi.fn()
    const onNavigate = vi.fn()
    const { container } = render(
      <FlatFolderRow {...baseProps} isFavorited={false} onTarget={onTarget} onNavigate={onNavigate} />
    )
    await user.click(findStarButton(container))
    expect(onTarget).not.toHaveBeenCalled()
    expect(onNavigate).not.toHaveBeenCalled()
  })
})

// Note on pin icon: the inline pin SVG (fill="#1F3148") is inside the name-cell div
// and has no onClick handler or stopPropagation. Clicking it DOES call onTarget via
// bubbling -- this is correct and expected behavior (clicking anywhere on the folder
// row area naturally selects the folder as the Upload/New Folder destination).
