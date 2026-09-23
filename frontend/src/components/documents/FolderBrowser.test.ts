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