// frontend/src/test/timezone.pin.test.ts
// Proves that vitest.globalSetup.ts pins the timezone to America/New_York for
// all test workers, making date tests deterministic across machines and in CI.
// If either test fails, the pin is not reaching workers and vitest.config.ts
// or vitest.globalSetup.ts must be updated.
import { describe, it, expect } from 'vitest'
import { localDateStr } from '@/lib/utils'

describe('timezone pin', () => {
  it('test worker runs in America/New_York', () => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    expect(tz).toBe('America/New_York')
  })

  it('localDateStr returns Sep 27 for a UTC instant that is already Sep 28 in UTC', () => {
    // 2026-09-28T01:00:00Z = 9:00 PM Sep 27 in America/New_York (UTC-4 EDT).
    // In UTC or any UTC+ zone this would be Sep 28.
    // The hardcoded expectation '2026-09-27' is only reachable if the worker
    // is running in a UTC-behind American timezone.
    const result = localDateStr(new Date('2026-09-28T01:00:00.000Z'))
    expect(result).toBe('2026-09-27')
  })
})
