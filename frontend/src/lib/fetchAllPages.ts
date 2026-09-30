// frontend/src/lib/fetchAllPages.ts
export const PAGE_SIZE = 100
export const MAX_PAGES = 50

export async function fetchAllPages<T>(
  fetchPage: (offset: number, limit: number) => Promise<{ items: T[]; total: number }>
): Promise<T[]> {
  const collected: T[] = []
  let offset = 0
  let pages = 0

  while (true) {
    const { items, total } = await fetchPage(offset, PAGE_SIZE)
    collected.push(...items)
    pages++

    if (items.length === 0 || items.length < PAGE_SIZE || collected.length >= total) {
      return collected
    }

    if (pages >= MAX_PAGES) {
      throw new Error('too many pages')
    }

    offset += PAGE_SIZE
  }
}
