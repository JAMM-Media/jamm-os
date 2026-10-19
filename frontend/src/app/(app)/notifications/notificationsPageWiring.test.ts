// path: frontend/src/app/(app)/notifications/notificationsPageWiring.test.ts
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const cwd = process.cwd()
if (!existsSync(join(cwd, 'package.json'))) {
  throw new Error('vitest must run from the frontend folder; cwd is ' + cwd)
}

function readSrc(relPath: string): string {
  return readFileSync(join(cwd, 'src', relPath), 'utf8').replace(/\r\n/g, '\n')
}

const PAGE = 'app/(app)/notifications/page.tsx'

describe('notifications page: source guards', () => {
  const src = readSrc(PAGE)

  it('starts with its real path comment', () => {
    expect(src.split('\n')[0]).toBe('// path: frontend/src/app/(app)/notifications/page.tsx')
  })

  it('imports its display helpers from notificationDisplay', () => {
    expect(src).toContain("from '@/lib/notificationDisplay'")
  })

  it('passes skip to the notifications request', () => {
    expect(src).toContain('/api/v1/notifications/?limit=${PAGE_SIZE}&skip=${pageParam}')
  })

  it('renders a Load more control', () => {
    expect(src).toContain('Load more')
    expect(src).toContain('fetchNextPage()')
  })

  it('no longer contains the old dotted label map keys', () => {
    for (const oldKey of [
      "'task.assigned'",
      "'engagement.deadline_approaching'",
      "'firm_chat.message'",
      "'automation.fired'",
      "'irs_authorization.expiry_approaching'",
    ]) {
      expect(src).not.toContain(oldKey)
    }
  })

  it('no longer truncates the message body', () => {
    expect(src).not.toContain('truncate')
  })

  it('still invalidates notifications-unread-count', () => {
    expect(src).toContain("queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })")
  })
})
