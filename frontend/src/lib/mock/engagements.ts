// frontend/src/lib/mock/engagements.ts

export type EngagementStatus =
  | 'in-progress'
  | 'awaiting-docs'
  | 'complete'
  | 'overdue'
  | 'not-started'

export interface MockEngagement {
  id: string
  title: string
  clientId: string
  clientName: string
  status: EngagementStatus
  dueDate: string
  assignedTo: string
  type: string
}

export const mockEngagements: MockEngagement[] = [
  {
    id: 'e1',
    title: '2023 Tax Return — Corporate',
    clientId: '1',
    clientName: 'Acme Corp',
    status: 'in-progress',
    dueDate: '2024-09-15',
    assignedTo: 'Sarah K.',
    type: 'Tax Return',
  },
  {
    id: 'e2',
    title: 'Q2 2024 Bookkeeping',
    clientId: '1',
    clientName: 'Acme Corp',
    status: 'awaiting-docs',
    dueDate: '2024-07-31',
    assignedTo: 'Mark T.',
    type: 'Bookkeeping',
  },
  {
    id: 'e3',
    title: '2022 Tax Return — Corporate',
    clientId: '1',
    clientName: 'Acme Corp',
    status: 'complete',
    dueDate: '2023-09-15',
    assignedTo: 'Sarah K.',
    type: 'Tax Return',
  },
  {
    id: 'e4',
    title: '2023 Tax Return — Partnership',
    clientId: '2',
    clientName: 'Bright Future LLC',
    status: 'in-progress',
    dueDate: '2024-09-15',
    assignedTo: 'Mark T.',
    type: 'Tax Return',
  },
  {
    id: 'e5',
    title: '2023 Tax Return — S-Corp',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    status: 'awaiting-docs',
    dueDate: '2024-09-15',
    assignedTo: 'Sarah K.',
    type: 'Tax Return',
  },
  {
    id: 'e6',
    title: 'Q1 2024 Bookkeeping',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    status: 'awaiting-docs',
    dueDate: '2024-04-30',
    assignedTo: 'Mark T.',
    type: 'Bookkeeping',
  },
  {
    id: 'e7',
    title: '2023 Tax Return — LLC',
    clientId: '5',
    clientName: 'Ironclad Logistics',
    status: 'in-progress',
    dueDate: '2024-09-15',
    assignedTo: 'Sarah K.',
    type: 'Tax Return',
  },
  {
    id: 'e8',
    title: 'Q3 2024 Bookkeeping',
    clientId: '2',
    clientName: 'Bright Future LLC',
    status: 'not-started',
    dueDate: '2024-10-31',
    assignedTo: 'Mark T.',
    type: 'Bookkeeping',
  },
]
