// frontend/src/test/integrations.address.guard.test.ts
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const WRONG = '/api' + '/v1/integrations'

const thisFile = fileURLToPath(import.meta.url)
const srcDir = join(dirname(thisFile), '..')

function walk(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '.next') continue
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      files.push(...walk(full))
    } else if (full.endsWith('.ts') || full.endsWith('.tsx')) {
      files.push(full)
    }
  }
  return files
}

describe('integrations address guard', () => {
  it('no file in frontend/src uses /api/v1/integrations', () => {
    const offenders = walk(srcDir).filter(
      (f) => f !== thisFile && readFileSync(f, 'utf8').includes(WRONG)
    )
    expect(offenders, `wrong address found in: ${offenders.join(', ')}`).toEqual([])
  })
})
