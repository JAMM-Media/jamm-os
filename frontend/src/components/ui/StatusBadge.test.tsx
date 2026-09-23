// frontend/src/components/ui/StatusBadge.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders the default label for the complete variant', () => {
    render(<StatusBadge variant="complete" />)
    expect(screen.getByText('Complete')).toBeInTheDocument()
  })

  it('renders a custom label instead of the default', () => {
    render(<StatusBadge variant="complete" label="Done" />)
    expect(screen.getByText('Done')).toBeInTheDocument()
    expect(screen.queryByText('Complete')).not.toBeInTheDocument()
  })

  it('renders the default label for the overdue variant', () => {
    render(<StatusBadge variant="overdue" />)
    expect(screen.getByText('Overdue')).toBeInTheDocument()
  })

  it('falls back gracefully for an unknown variant', () => {
    // @ts-expect-error intentionally passing unknown variant to test fallback
    render(<StatusBadge variant="nonexistent_variant" />)
    expect(screen.getByText('Unknown')).toBeInTheDocument()
  })
})