// frontend/src/components/documents/FolderBrowser.test.ts
// .ts (not .tsx) because getDescendantFolderIds is a pure function with no JSX.
import { describe, it, expect } from 'vitest'
import { getDescendantFolderIds } from './FolderBrowser'

// Minimal folder objects satisfying BrowserFolder's required fields.
// The function only reads child.id, but the type requires id, name, parent_folder_id.
function f(id: string, parent: string | null = null) {
  return { id, name: `Folder ${id}`, parent_folder_id: parent }
}

describe('getDescendantFolderIds', () => {
  // (a) A folder with no children returns an empty set.
  it('returns an empty set for a folder with no children', () => {
    const childrenOf = {}
    const result = getDescendantFolderIds('root', childrenOf)
    expect(result.size).toBe(0)
  })

  // (b) Direct children only -- Set membership and size, not order.
  it('returns exactly the direct children ids for a leaf parent', () => {
    const childrenOf = {
      root: [f('child1', 'root'), f('child2', 'root'), f('child3', 'root')],
    }
    const result = getDescendantFolderIds('root', childrenOf)
    expect(result.size).toBe(3)
    expect(result.has('child1')).toBe(true)
    expect(result.has('child2')).toBe(true)
    expect(result.has('child3')).toBe(true)
    // Confirms the root folder itself is not in the set.
    expect(result.has('root')).toBe(false)
  })

  // (c) Three-level tree -- confirms traversal recurses past one level.
  it('returns all descendants at every depth in a 3-level tree', () => {
    // Tree: root -> [A, B], A -> [A1, A2], A1 -> [A1a]
    const childrenOf = {
      root: [f('A', 'root'), f('B', 'root')],
      A: [f('A1', 'A'), f('A2', 'A')],
      A1: [f('A1a', 'A1')],
    }
    const result = getDescendantFolderIds('root', childrenOf)
    expect(result.size).toBe(5)
    expect(result.has('A')).toBe(true)
    expect(result.has('B')).toBe(true)
    expect(result.has('A1')).toBe(true)
    expect(result.has('A2')).toBe(true)
    expect(result.has('A1a')).toBe(true)
    expect(result.has('root')).toBe(false)
  })

  // (d) The starting folder is never in its own descendant set.
  // The function has no explicit self-exclusion guard; the natural traversal
  // never adds the starting folderId to result (it starts in the queue but
  // only children are added to result). A childrenOf entry where a folder
  // is its own child is not tested here because it would create an infinite
  // loop -- no guard exists against malformed self-referential trees.
  it('never includes the starting folder id in the result', () => {
    const childrenOf = {
      me: [f('child1', 'me'), f('child2', 'me')],
      child1: [f('grandchild', 'child1')],
    }
    const result = getDescendantFolderIds('me', childrenOf)
    expect(result.has('me')).toBe(false)
    expect(result.has('child1')).toBe(true)
    expect(result.has('child2')).toBe(true)
    expect(result.has('grandchild')).toBe(true)
  })

  // (e) Siblings of the starting folder are never included.
  it('does not include sibling branches in the result', () => {
    // Tree: parent -> [target, sibling], sibling -> [nephew]
    const childrenOf = {
      parent: [f('target', 'parent'), f('sibling', 'parent')],
      sibling: [f('nephew', 'sibling')],
      target: [f('child_of_target', 'target')],
    }
    const result = getDescendantFolderIds('target', childrenOf)
    expect(result.has('child_of_target')).toBe(true)
    // sibling and its descendants must not appear
    expect(result.has('sibling')).toBe(false)
    expect(result.has('nephew')).toBe(false)
    // parent must not appear either
    expect(result.has('parent')).toBe(false)
  })

  // (f) A folder id not present in childrenOf returns an empty set without throwing.
  it('returns an empty set for a folder id not in childrenOf', () => {
    const childrenOf = {
      some_other_folder: [f('irrelevant', 'some_other_folder')],
    }
    const result = getDescendantFolderIds('nonexistent', childrenOf)
    expect(result.size).toBe(0)
  })
})

import { sortedSiblings } from './FolderBrowser'
import type { SiblingItem } from './FolderBrowser'

// Helpers for building SiblingItem fixtures without repeating required fields.
function folder(id: string): SiblingItem {
  return { kind: 'folder', folder: { id, name: `F-${id}`, parent_folder_id: null } }
}
function doc(id: string): SiblingItem {
  return { kind: 'doc', doc: { id, filename: `d-${id}.pdf`, folder_id: null, content_type: 'application/pdf', size_bytes: 0, created_at: '', is_superseded: false } }
}

describe('sortedSiblings', () => {
  // (a) No pinned items: original relative order is preserved exactly.
  it('preserves original order when nothing is pinned', () => {
    const items: SiblingItem[] = [folder('A'), doc('B'), folder('C'), doc('D')]
    const result = sortedSiblings(items, new Set())
    expect(result.map(i => i.kind === 'folder' ? i.folder.id : i.doc.id)).toEqual(['A', 'B', 'C', 'D'])
  })

  // (b) A single pinned item moves to the front; unpinned items keep relative order.
  it('moves a single pinned item to the front', () => {
    const items: SiblingItem[] = [folder('A'), doc('B'), folder('C')]
    const result = sortedSiblings(items, new Set(['B']))
    const ids = result.map(i => i.kind === 'folder' ? i.folder.id : i.doc.id)
    expect(ids[0]).toBe('B')
    expect(ids.slice(1)).toEqual(['A', 'C'])
  })

  // (c) Multiple pinned items move to the front and keep their original relative
  //     order among themselves -- this would fail if the sort were unstable.
  it('moves multiple pinned items to the front preserving their mutual order', () => {
    // C and E are pinned. Original order: A B C D E F.
    // Expected: C E A B D F (pinned in original order, then unpinned in original order).
    const items: SiblingItem[] = [folder('A'), doc('B'), folder('C'), doc('D'), folder('E'), doc('F')]
    const result = sortedSiblings(items, new Set(['C', 'E']))
    const ids = result.map(i => i.kind === 'folder' ? i.folder.id : i.doc.id)
    expect(ids[0]).toBe('C')
    expect(ids[1]).toBe('E')
    expect(ids.slice(2)).toEqual(['A', 'B', 'D', 'F'])
  })

  // (d) Folders and docs are sorted as one list: a pinned doc can precede an
  //     unpinned folder, and vice versa -- no kind-based separation.
  it('treats folders and docs as one list: pinned doc precedes unpinned folder', () => {
    const items: SiblingItem[] = [folder('F1'), folder('F2'), doc('D1')]
    const result = sortedSiblings(items, new Set(['D1']))
    const ids = result.map(i => i.kind === 'folder' ? i.folder.id : i.doc.id)
    expect(ids[0]).toBe('D1')
    expect(ids.slice(1)).toEqual(['F1', 'F2'])
  })

  it('treats folders and docs as one list: pinned folder precedes unpinned docs', () => {
    const items: SiblingItem[] = [doc('D1'), doc('D2'), folder('F1')]
    const result = sortedSiblings(items, new Set(['F1']))
    const ids = result.map(i => i.kind === 'folder' ? i.folder.id : i.doc.id)
    expect(ids[0]).toBe('F1')
    expect(ids.slice(1)).toEqual(['D1', 'D2'])
  })

  // (e) Empty array returns empty array without throwing.
  it('returns an empty array for empty input', () => {
    const result = sortedSiblings([], new Set(['anything']))
    expect(result).toEqual([])
  })
})
