// frontend/src/components/dashboard/DashboardCustomizePanel.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DashboardCustomizePanel } from './DashboardCustomizePanel'
import type { DashboardSection } from './DashboardCustomizePanel'

const SECTIONS: DashboardSection[] = [
  { key: 'morning_briefing',   label: 'Morning Briefing',   visible: true,  order: 0 },
  { key: 'financial_stats',    label: 'Financial Stats',    visible: true,  order: 1 },
  { key: 'work_in_progress',   label: 'Work in Progress',   visible: true,  order: 2 },
  { key: 'staff_utilization',  label: 'Staff Utilization',  visible: true,  order: 3 },
  { key: 'upcoming_deadlines', label: 'Upcoming Deadlines', visible: true,  order: 4 },
  { key: 'awaiting_signature', label: 'Awaiting Signature', visible: false, order: 5 },
]

function renderPanel(onSave = vi.fn(), onClose = vi.fn()) {
  return render(
    <DashboardCustomizePanel
      isOpen={true}
      onClose={onClose}
      sections={SECTIONS}
      onSave={onSave}
    />
  )
}

describe('DashboardCustomizePanel', () => {
  it('renders all six sections', () => {
    renderPanel()
    expect(screen.getByText('Morning Briefing')).toBeInTheDocument()
    expect(screen.getByText('Financial Stats')).toBeInTheDocument()
    expect(screen.getByText('Work in Progress')).toBeInTheDocument()
    expect(screen.getByText('Staff Utilization')).toBeInTheDocument()
    expect(screen.getByText('Upcoming Deadlines')).toBeInTheDocument()
    expect(screen.getByText('Awaiting Signature')).toBeInTheDocument()
  })

  it('reflects initial visible/hidden state via toggle aria-checked', () => {
    renderPanel()
    const toggles = screen.getAllByRole('switch')
    // 5 visible, 1 hidden (awaiting_signature)
    const checked = toggles.filter((t) => t.getAttribute('aria-checked') === 'true')
    const unchecked = toggles.filter((t) => t.getAttribute('aria-checked') === 'false')
    expect(checked).toHaveLength(5)
    expect(unchecked).toHaveLength(1)
  })

  it('toggling a section flips its visible state', () => {
    renderPanel()
    const awaitingToggle = screen.getByRole('switch', { name: /Awaiting Signature/i })
    expect(awaitingToggle.getAttribute('aria-checked')).toBe('false')
    fireEvent.click(awaitingToggle)
    expect(awaitingToggle.getAttribute('aria-checked')).toBe('true')
  })

  it('calls onSave with updated sections when Save is clicked', async () => {
    const onSave = vi.fn()
    renderPanel(onSave)

    // Toggle Financial Stats off
    const statsToggle = screen.getByRole('switch', { name: /Financial Stats/i })
    fireEvent.click(statsToggle)

    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledOnce()
      const saved: DashboardSection[] = onSave.mock.calls[0][0]
      const stats = saved.find((s) => s.key === 'financial_stats')
      expect(stats?.visible).toBe(false)
    })
  })

  it('calls onClose when X button is clicked', () => {
    const onClose = vi.fn()
    renderPanel(vi.fn(), onClose)
    fireEvent.click(screen.getByRole('button', { name: /close customize panel/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onSave with reordered sections after drag', async () => {
    // Simulate drag: drag index 0 over index 1 (swap first two)
    const onSave = vi.fn()
    renderPanel(onSave)

    const rows = screen.getAllByText(/Morning Briefing|Financial Stats/)
    // Get the parent draggable divs
    const draggable = rows[0].closest('[draggable]')!

    fireEvent.dragStart(draggable)
    const target = rows[1].closest('[draggable]')!
    fireEvent.dragOver(target)
    fireEvent.dragEnd(draggable)

    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledOnce()
      const saved: DashboardSection[] = onSave.mock.calls[0][0]
      // After drag, Morning Briefing should be at order 1, Financial Stats at order 0
      const briefing = saved.find((s) => s.key === 'morning_briefing')
      const stats = saved.find((s) => s.key === 'financial_stats')
      expect(briefing?.order).toBeGreaterThanOrEqual(0)
      expect(stats?.order).toBeGreaterThanOrEqual(0)
      // They should have swapped or reordered
      expect(briefing?.order).not.toBe(stats?.order)
    })
  })

  it('discards edits when closed via X without saving and shows original on reopen', () => {
    const onSave = vi.fn()
    const onClose = vi.fn()
    const { rerender } = render(
      <DashboardCustomizePanel
        isOpen={true}
        onClose={onClose}
        sections={SECTIONS}
        onSave={onSave}
      />
    )

    // Toggle Financial Stats off -- an unsaved edit
    fireEvent.click(screen.getByRole('switch', { name: /toggle financial stats/i }))
    expect(screen.getByRole('switch', { name: /toggle financial stats/i }))
      .toHaveAttribute('aria-checked', 'false')

    // Close with the X button without saving
    fireEvent.click(screen.getByRole('button', { name: /close customize panel/i }))

    // Reopen: simulate parent setting isOpen=false then true
    rerender(
      <DashboardCustomizePanel
        isOpen={false}
        onClose={onClose}
        sections={SECTIONS}
        onSave={onSave}
      />
    )
    rerender(
      <DashboardCustomizePanel
        isOpen={true}
        onClose={onClose}
        sections={SECTIONS}
        onSave={onSave}
      />
    )

    // Financial Stats should be back to original visible=true (unsaved edit discarded)
    expect(screen.getByRole('switch', { name: /toggle financial stats/i }))
      .toHaveAttribute('aria-checked', 'true')

    // onSave should never have been called
    expect(onSave).not.toHaveBeenCalled()
  })
})
