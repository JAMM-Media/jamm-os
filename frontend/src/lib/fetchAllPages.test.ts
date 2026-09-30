// frontend/src/lib/fetchAllPages.test.ts
import { describe, it, expect, vi } from 'vitest'
import { fetchAllPages, PAGE_SIZE, MAX_PAGES } from './fetchAllPages'

describe('fetchAllPages', () => {
  it('three pages of 100, 100 and 37 with total 237 return 237 items in order', async () => {
    const sizes = [100, 100, 37]
    const fetchPage = vi.fn().mockImplementation((offset: number) => {
      const pageIndex = offset / PAGE_SIZE
      const count = sizes[pageIndex]
      return Promise.resolve({
        items: Array.from({ length: count }, (_, i) => offset + i),
        total: 237,
      })
    })

    const result = await fetchAllPages(fetchPage)

    expect(result).toHaveLength(237)
    expect(result).toEqual(Array.from({ length: 237 }, (_, i) => i))
    expect(fetchPage).toHaveBeenCalledTimes(3)
    expect(fetchPage).toHaveBeenNthCalledWith(1, 0, PAGE_SIZE)
    expect(fetchPage).toHaveBeenNthCalledWith(2, 100, PAGE_SIZE)
    expect(fetchPage).toHaveBeenNthCalledWith(3, 200, PAGE_SIZE)
  })

  it('total 5 with one page of 5 returns 5 items with exactly one call', async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [1, 2, 3, 4, 5], total: 5 })
    const result = await fetchAllPages(fetchPage)
    expect(result).toHaveLength(5)
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })

  it('total 0 with an empty page returns an empty array with exactly one call', async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [], total: 0 })
    const result = await fetchAllPages(fetchPage)
    expect(result).toHaveLength(0)
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })

  it('a fetcher returning 100 items with total 999999 rejects after exactly MAX_PAGES calls', async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: Array(PAGE_SIZE).fill(0), total: 999999 })
    await expect(fetchAllPages(fetchPage)).rejects.toThrow('too many pages')
    expect(fetchPage).toHaveBeenCalledTimes(MAX_PAGES)
  })

  it('a fetcher that rejects on its second call makes the function reject with that error', async () => {
    const err = new Error('second call error')
    const fetchPage = vi.fn()
      .mockResolvedValueOnce({ items: Array(PAGE_SIZE).fill(0), total: 200 })
      .mockRejectedValueOnce(err)
    await expect(fetchAllPages(fetchPage)).rejects.toThrow('second call error')
  })
})
