// path: frontend/src/app/(app)/notifications/deleteRequestWiring.test.ts
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

describe('notifications page: delete request actions wiring', () => {
  const src = readSrc(PAGE)

  it('imports DeleteRequestActions from the notifications components folder', () => {
    expect(src).toContain(
      "import { DeleteRequestActions } from '@/components/notifications/DeleteRequestActions'",
    )
  })

  it('imports useAuth and the row predicate', () => {
    expect(src).toContain("import { useAuth } from '@/lib/hooks/useAuth'")
    expect(src).toContain("import { isDeleteRequestRow } from '@/lib/deleteRequestState'")
    expect(src).toContain('const { user } = useAuth()')
  })

  it('renders DeleteRequestActions only for delete-request rows', () => {
    expect(src).toContain(
      'isDeleteRequestRow(n.title, n.related_entity_type, n.related_entity_id) && (',
    )
    expect(src).toContain('<DeleteRequestActions')
  })

  it('passes the viewer role and the page mark-read function', () => {
    expect(src).toContain('role={user?.role}')
    expect(src).toContain('onMarkRead={handleMarkRead}')
  })

  it('keeps the row link and the existing mark-read path', () => {
    expect(src).toContain('onClick={() => handleRowClick(n)}')
    expect(src).toContain("await api.patch(`/api/v1/notifications/${id}/read`)")
  })

  it('has no em dash', () => {
    expect(src).not.toContain(String.fromCharCode(0x2014))
  })
})
