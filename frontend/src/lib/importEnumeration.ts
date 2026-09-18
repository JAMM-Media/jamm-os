// frontend/src/lib/importEnumeration.ts

import type { ImportItemCreate } from '@/lib/api/importBatches'

/**
 * Enumerate a FileList produced by a webkitdirectory <input> and return the
 * flat array of item descriptors the backend's ImportBatchCreate.items expects.
 *
 * webkitdirectory returns a flat FileList; each File carries webkitRelativePath
 * (e.g. "FolderName/Subfolder/file.pdf"). Empty folders are not represented
 * because there are no File objects for them -- accepted browser limitation.
 */
export function enumerateFolder(files: FileList): ImportItemCreate[] {
  const items: ImportItemCreate[] = []
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    items.push({
      relative_path: file.webkitRelativePath || file.name,
      filename: file.name,
      expected_bytes: file.size,
      mime_type: file.type || null,
    })
  }
  return items
}
