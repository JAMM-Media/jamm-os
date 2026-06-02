// frontend/src/lib/mock/dashboard.ts

import { mockTasks } from './tasks'
import { mockEngagements } from './engagements'

export interface DashboardItem {
  id: string
  type: 'task' | 'engagement'
  title: string
  clientName: string
  clientId: string
  status: string
  dueDate: string
  assignedTo: string
  href: string
}

export function getOverdueItems(): DashboardItem[] {
  const tasks = mockTasks
    .filter((t) => t.status === 'overdue')
    .map((t) => ({
      id: t.id,
      type: 'task' as const,
      title: t.title,
      clientName: t.clientName,
      clientId: t.clientId,
      status: t.status,
      dueDate: t.dueDate,
      assignedTo: t.assignedTo,
      href: `/tasks/${t.id}`,
    }))

  const engagements = mockEngagements
    .filter((e) => e.status === 'overdue')
    .map((e) => ({
      id: e.id,
      type: 'engagement' as const,
      title: e.title,
      clientName: e.clientName,
      clientId: e.clientId,
      status: e.status,
      dueDate: e.dueDate,
      assignedTo: e.assignedTo,
      href: `/engagements/${e.id}`,
    }))

  return [...tasks, ...engagements].sort(
    (a, b) => new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime()
  )
}

export function getAwaitingDocsItems(): DashboardItem[] {
  return mockEngagements
    .filter((e) => e.status === 'awaiting-docs')
    .map((e) => ({
      id: e.id,
      type: 'engagement' as const,
      title: e.title,
      clientName: e.clientName,
      clientId: e.clientId,
      status: e.status,
      dueDate: e.dueDate,
      assignedTo: e.assignedTo,
      href: `/engagements/${e.id}`,
    }))
}

export function getUpcomingItems(): DashboardItem[] {
  const today = new Date('2024-08-01')
  const cutoff = new Date('2024-09-30')

  const tasks = mockTasks
    .filter((t) => {
      const d = new Date(t.dueDate)
      return (
        (t.status === 'not-started' || t.status === 'in-progress') &&
        d >= today &&
        d <= cutoff
      )
    })
    .map((t) => ({
      id: t.id,
      type: 'task' as const,
      title: t.title,
      clientName: t.clientName,
      clientId: t.clientId,
      status: t.status,
      dueDate: t.dueDate,
      assignedTo: t.assignedTo,
      href: `/tasks/${t.id}`,
    }))

  const engagements = mockEngagements
    .filter((e) => {
      const d = new Date(e.dueDate)
      return (
        (e.status === 'not-started' || e.status === 'in-progress') &&
        d >= today &&
        d <= cutoff
      )
    })
    .map((e) => ({
      id: e.id,
      type: 'engagement' as const,
      title: e.title,
      clientName: e.clientName,
      clientId: e.clientId,
      status: e.status,
      dueDate: e.dueDate,
      assignedTo: e.assignedTo,
      href: `/engagements/${e.id}`,
    }))

  return [...tasks, ...engagements].sort(
    (a, b) => new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime()
  )
}

export function getSummaryStats() {
  const { mockClients } = require('./clients')
  return {
    totalClients: mockClients.length,
    activeEngagements: mockEngagements.filter(
      (e) => e.status === 'in-progress' || e.status === 'awaiting-docs'
    ).length,
    overdue: getOverdueItems().length,
    awaitingDocs: getAwaitingDocsItems().length,
  }
}
