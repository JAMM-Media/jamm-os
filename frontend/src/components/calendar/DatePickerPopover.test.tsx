// path: frontend/src/components/calendar/DatePickerPopover.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import React from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import { DatePickerPopover } from './DatePickerPopover'

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

let container: HTMLDivElement
let root: ReturnType<typeof createRoot>

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
})

afterEach(async () => {
  await act(async () => { root?.unmount() })
  document.body.removeChild(container)
})

async function render(props: React.ComponentProps<typeof DatePickerPopover>): Promise<void> {
  await act(async () => {
    root = createRoot(container)
    root.render(React.createElement(DatePickerPopover, props))
  })
}

function getDialog(): HTMLDivElement {
  return container.querySelector('[role="dialog"]') as HTMLDivElement
}

async function keyDown(key: string): Promise<void> {
  await act(async () => {
    const target = container.querySelector<HTMLButtonElement>('[data-date][tabindex="0"]') ?? getDialog()
    target.dispatchEvent(
      new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
    )
  })
}

async function keyDownOn(btn: HTMLButtonElement, key: string): Promise<KeyboardEvent> {
  let ev!: KeyboardEvent
  await act(async () => {
    ev = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
    btn.dispatchEvent(ev)
  })
  return ev
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DatePickerPopover', () => {
  it('has role="dialog" and aria-label="Choose a date"', async () => {
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick: vi.fn(), onClose: vi.fn() })
    const dialog = getDialog()
    expect(dialog).not.toBeNull()
    expect(dialog.getAttribute('aria-label')).toBe('Choose a date')
  })

  it('opens on the month of valueDateStr', async () => {
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick: vi.fn(), onClose: vi.fn() })
    expect(container.textContent).toContain('October 2026')
  })

  it('the selected day has bg-brand class', async () => {
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick: vi.fn(), onClose: vi.fn() })
    const selected = container.querySelector('[data-date="2026-10-15"]') as HTMLButtonElement
    expect(selected?.className).toContain('bg-brand')
  })

  it('clicking Next month shows the next month title and onPick is called 0 times', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Next month"]') as HTMLButtonElement).click()
    })
    expect(container.textContent).toContain('November 2026')
    expect(onPick).toHaveBeenCalledTimes(0)
  })

  it('clicking Previous month shows the previous month title and onPick is called 0 times', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Previous month"]') as HTMLButtonElement).click()
    })
    expect(container.textContent).toContain('September 2026')
    expect(onPick).toHaveBeenCalledTimes(0)
  })

  it('clicking a day calls onPick once with that dateStr', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[data-date="2026-10-20"]') as HTMLButtonElement).click()
    })
    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('2026-10-20')
  })

  it('clicking a muted day from the next month calls onPick with that date', async () => {
    const onPick = vi.fn()
    // October 2026 grid has trailing cells from November
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      // Nov 1 appears as an out-of-month cell in the October grid
      ;(container.querySelector('[data-date="2026-11-01"]') as HTMLButtonElement).click()
    })
    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('2026-11-01')
  })

  it('ArrowRight then Enter picks the next day', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await keyDown('ArrowRight')
    await keyDown('Enter')
    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('2026-10-16')
  })

  it('ArrowDown moves 7 days forward', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await keyDown('ArrowDown')
    await keyDown('Enter')
    expect(onPick).toHaveBeenCalledWith('2026-10-22')
  })

  it('PageDown from 2026-01-31 moves to 2026-02-28 (clamped) and shows February', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-01-31', todayDateStr: '2026-01-15', onPick, onClose: vi.fn() })
    await keyDown('PageDown')
    expect(container.textContent).toContain('February 2026')
    const focused = container.querySelector('[tabindex="0"]') as HTMLButtonElement
    expect(focused?.getAttribute('data-date')).toBe('2026-02-28')
    expect(onPick).not.toHaveBeenCalled()
  })

  it('Escape calls onClose and not onPick', async () => {
    const onPick = vi.fn()
    const onClose = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose })
    await keyDown('Escape')
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onPick).not.toHaveBeenCalled()
  })

  it('arrow keys alone never call onPick', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await keyDown('ArrowLeft')
    await keyDown('ArrowRight')
    await keyDown('ArrowUp')
    await keyDown('ArrowDown')
    expect(onPick).not.toHaveBeenCalled()
  })

  // ---------------------------------------------------------------------------
  // New tests for keyboard fix
  // ---------------------------------------------------------------------------

  it('Enter on Next month button: onPick called 0 times and defaultPrevented is false', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    const btn = container.querySelector('[aria-label="Next month"]') as HTMLButtonElement
    const ev = await keyDownOn(btn, 'Enter')
    expect(onPick).toHaveBeenCalledTimes(0)
    expect(ev.defaultPrevented).toBe(false)
  })

  it('Space on Next month button: onPick called 0 times', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    const btn = container.querySelector('[aria-label="Next month"]') as HTMLButtonElement
    await keyDownOn(btn, ' ')
    expect(onPick).toHaveBeenCalledTimes(0)
  })

  it('Enter on Previous month button: onPick called 0 times', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    const btn = container.querySelector('[aria-label="Previous month"]') as HTMLButtonElement
    await keyDownOn(btn, 'Enter')
    expect(onPick).toHaveBeenCalledTimes(0)
  })

  it('ArrowRight on Next month button does not change focused day and onPick is 0', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    const btn = container.querySelector('[aria-label="Next month"]') as HTMLButtonElement
    await keyDownOn(btn, 'ArrowRight')
    const dayButtons = Array.from(container.querySelectorAll('[data-date]')) as HTMLButtonElement[]
    const withTabIndex0 = dayButtons.filter((b) => b.tabIndex === 0)
    expect(withTabIndex0[0]?.getAttribute('data-date')).toBe('2026-10-15')
    expect(onPick).toHaveBeenCalledTimes(0)
  })

  it('Escape on Next month button calls onClose once', async () => {
    const onClose = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick: vi.fn(), onClose })
    const btn = container.querySelector('[aria-label="Next month"]') as HTMLButtonElement
    await keyDownOn(btn, 'Escape')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('click Next month: activeElement is the Next month button, not a day button', async () => {
    // Sep 30 is a leading cell in October 2026 (Oct 1 is Thursday); if handleNextMonth
    // set shouldFocusRef, the useEffect would steal focus to that day button.
    await render({ valueDateStr: '2026-09-30', todayDateStr: '2026-10-08', onPick: vi.fn(), onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Next month"]') as HTMLButtonElement).click()
    })
    expect(document.activeElement).toBe(
      container.querySelector('[aria-label="Next month"]'),
    )
  })

  it('click Previous month: activeElement is the Previous month button, not a day button', async () => {
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick: vi.fn(), onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Previous month"]') as HTMLButtonElement).click()
    })
    expect(document.activeElement).toBe(
      container.querySelector('[aria-label="Previous month"]'),
    )
  })

  it('after clicking Next month, exactly one day button has tabIndex 0 and it is the first inMonth day', async () => {
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick: vi.fn(), onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Next month"]') as HTMLButtonElement).click()
    })
    const dayButtons = Array.from(container.querySelectorAll('[data-date]')) as HTMLButtonElement[]
    const withTabIndex0 = dayButtons.filter((b) => b.tabIndex === 0)
    expect(withTabIndex0).toHaveLength(1)
    // November 2026 starts on Sunday so first inMonth cell is 2026-11-01
    expect(withTabIndex0[0]!.getAttribute('data-date')).toBe('2026-11-01')
  })

  // ---------------------------------------------------------------------------
  // New tests: keyboard actions use the day that has DOM focus, not focusedStr
  // ---------------------------------------------------------------------------

  it('Enter on tabindex-0 day after Next month picks that day, not valueDateStr', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Next month"]') as HTMLButtonElement).click()
    })
    const btn = container.querySelector<HTMLButtonElement>('[data-date="2026-11-01"]')!
    await keyDownOn(btn, 'Enter')
    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith('2026-11-01')
  })

  it('ArrowRight then Enter after Next month navigates from the focused day, not valueDateStr', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Next month"]') as HTMLButtonElement).click()
    })
    const nov1 = container.querySelector<HTMLButtonElement>('[data-date="2026-11-01"]')!
    await keyDownOn(nov1, 'ArrowRight')
    const focused = container.querySelector<HTMLButtonElement>('[data-date][tabindex="0"]')!
    await keyDownOn(focused, 'Enter')
    expect(onPick).toHaveBeenCalledWith('2026-11-02')
    expect(container.textContent).toContain('November 2026')
  })

  it('PageDown on tabindex-0 day after Next month moves from that day, not valueDateStr', async () => {
    const onPick = vi.fn()
    await render({ valueDateStr: '2026-10-15', todayDateStr: '2026-10-15', onPick, onClose: vi.fn() })
    await act(async () => {
      ;(container.querySelector('[aria-label="Next month"]') as HTMLButtonElement).click()
    })
    const nov1 = container.querySelector<HTMLButtonElement>('[data-date="2026-11-01"]')!
    await keyDownOn(nov1, 'PageDown')
    expect(container.textContent).toContain('December 2026')
    const focused = container.querySelector('[tabindex="0"]') as HTMLButtonElement
    expect(focused?.getAttribute('data-date')).toBe('2026-12-01')
  })
})
