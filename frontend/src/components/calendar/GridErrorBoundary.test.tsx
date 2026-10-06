// path: frontend/src/components/calendar/GridErrorBoundary.test.tsx
import { describe, it, expect, vi } from 'vitest'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import { GridErrorBoundary } from './GridErrorBoundary'

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

const ALERT_MESSAGE = 'The time grid could not be displayed. Switch to Month or Agenda, or reload the page.'

// ---------------------------------------------------------------------------
// Static method
// ---------------------------------------------------------------------------

describe('GridErrorBoundary.getDerivedStateFromError', () => {
  it('returns { hasError: true }', () => {
    expect(GridErrorBoundary.getDerivedStateFromError()).toEqual({ hasError: true })
  })
})

// ---------------------------------------------------------------------------
// render
// ---------------------------------------------------------------------------

describe('GridErrorBoundary render', () => {
  it('returns children when hasError is false; returns alert when hasError is true', () => {
    const child = React.createElement('span', null, 'child content')
    const instance = new GridErrorBoundary({ children: child, resetKey: 'k' })

    instance.state = { hasError: false }
    const okHtml = renderToStaticMarkup(instance.render() as React.ReactElement)
    expect(okHtml).toContain('child content')

    instance.state = { hasError: true }
    const errHtml = renderToStaticMarkup(instance.render() as React.ReactElement)
    expect(errHtml).toContain('role="alert"')
    expect(errHtml).toContain(ALERT_MESSAGE)
    expect(errHtml).not.toContain('child content')
  })
})

// ---------------------------------------------------------------------------
// componentDidUpdate
// ---------------------------------------------------------------------------

describe('GridErrorBoundary componentDidUpdate', () => {
  it('resets hasError when resetKey changes; does not reset otherwise', () => {
    const props = { children: React.createElement('span'), resetKey: 'key-a' }
    const instance = new GridErrorBoundary(props)
    const mockSetState = vi.fn()
    instance.setState = mockSetState

    // changed resetKey while hasError is true: must reset
    instance.state = { hasError: true }
    instance.componentDidUpdate({ children: React.createElement('span'), resetKey: 'key-b' })
    expect(mockSetState).toHaveBeenCalledWith({ hasError: false })

    // same resetKey while hasError is true: must not reset
    mockSetState.mockClear()
    instance.state = { hasError: true }
    instance.componentDidUpdate({ children: React.createElement('span'), resetKey: 'key-a' })
    expect(mockSetState).not.toHaveBeenCalled()

    // changed resetKey but hasError is false: must not reset
    mockSetState.mockClear()
    instance.state = { hasError: false }
    instance.componentDidUpdate({ children: React.createElement('span'), resetKey: 'key-b' })
    expect(mockSetState).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Real catch test
// ---------------------------------------------------------------------------

describe('GridErrorBoundary real catch', () => {
  it('catches a thrown child and shows the alert; sibling rendered outside the boundary is still present', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const container = document.createElement('div')
    document.body.appendChild(container)

    function Thrower(): React.ReactNode {
      throw new Error('intentional render error')
    }

    let root: ReturnType<typeof createRoot>
    await act(async () => {
      root = createRoot(container)
      root.render(
        React.createElement(React.Fragment, null,
          React.createElement(GridErrorBoundary, { resetKey: 'k' },
            React.createElement(Thrower)
          ),
          React.createElement('div', { id: 'sibling' }, 'sibling-content')
        )
      )
    })

    expect(container.textContent).toContain(ALERT_MESSAGE)
    expect(container.textContent).toContain('sibling-content')

    await act(async () => { root!.unmount() })
    document.body.removeChild(container)
    spy.mockRestore()
  })
})

// ---------------------------------------------------------------------------
// Reset test
// ---------------------------------------------------------------------------

describe('GridErrorBoundary reset', () => {
  it('shows children again after resetKey changes and child no longer throws', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    let shouldThrow = true
    function MaybeThrow(): React.ReactNode {
      if (shouldThrow) throw new Error('intentional')
      return React.createElement('span', null, 'recovered-content')
    }

    const container = document.createElement('div')
    document.body.appendChild(container)

    let root: ReturnType<typeof createRoot>
    await act(async () => {
      root = createRoot(container)
      root.render(
        React.createElement(GridErrorBoundary, { resetKey: 'key-1' },
          React.createElement(MaybeThrow)
        )
      )
    })

    expect(container.textContent).toContain(ALERT_MESSAGE)

    shouldThrow = false
    await act(async () => {
      root!.render(
        React.createElement(GridErrorBoundary, { resetKey: 'key-2' },
          React.createElement(MaybeThrow)
        )
      )
    })

    expect(container.textContent).toContain('recovered-content')

    await act(async () => { root!.unmount() })
    document.body.removeChild(container)
    spy.mockRestore()
  })
})
