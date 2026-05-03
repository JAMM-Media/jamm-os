// frontend/src/lib/mock/tasks.ts

export type TaskStatus =
  | 'not-started'
  | 'in-progress'
  | 'complete'
  | 'overdue'

export interface MockTask {
  id: string
  title: string
  clientId: string
  clientName: string
  engagementId: string
  engagementTitle: string
  assignedTo: string
  dueDate: string
  status: TaskStatus
}

export const mockTasks: MockTask[] = [
  {
    id: 't1',
    title: 'Prepare depreciation schedule',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e1',
    engagementTitle: '2023 Tax Return — Corporate',
    assignedTo: 'Sarah K.',
    dueDate: '2024-08-01',
    status: 'in-progress',
  },
  {
    id: 't2',
    title: 'Request prior year returns from client',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e1',
    engagementTitle: '2023 Tax Return — Corporate',
    assignedTo: 'Mark T.',
    dueDate: '2024-07-15',
    status: 'overdue',
  },
  {
    id: 't3',
    title: 'Reconcile bank statements — Q2',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e2',
    engagementTitle: 'Q2 2024 Bookkeeping',
    assignedTo: 'Mark T.',
    dueDate: '2024-07-31',
    status: 'not-started',
  },
  {
    id: 't4',
    title: 'Review partnership agreement',
    clientId: '2',
    clientName: 'Bright Future LLC',
    engagementId: 'e4',
    engagementTitle: '2023 Tax Return — Partnership',
    assignedTo: 'Mark T.',
    dueDate: '2024-08-15',
    status: 'not-started',
  },
  {
    id: 't5',
    title: 'Gather W-2s and 1099s',
    clientId: '2',
    clientName: 'Bright Future LLC',
    engagementId: 'e4',
    engagementTitle: '2023 Tax Return — Partnership',
    assignedTo: 'Sarah K.',
    dueDate: '2024-07-20',
    status: 'overdue',
  },
  {
    id: 't6',
    title: 'Prepare S-Corp basis calculation',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e5',
    engagementTitle: '2023 Tax Return — S-Corp',
    assignedTo: 'Sarah K.',
    dueDate: '2024-08-30',
    status: 'in-progress',
  },
  {
    id: 't7',
    title: 'Send document request checklist',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e5',
    engagementTitle: '2023 Tax Return — S-Corp',
    assignedTo: 'Mark T.',
    dueDate: '2024-07-10',
    status: 'complete',
  },
  {
    id: 't8',
    title: 'Categorize expenses — Q1',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e6',
    engagementTitle: 'Q1 2024 Bookkeeping',
    assignedTo: 'Mark T.',
    dueDate: '2024-04-30',
    status: 'complete',
  },
  {
    id: 't9',
    title: 'Prepare LLC return draft',
    clientId: '5',
    clientName: 'Ironclad Logistics',
    engagementId: 'e7',
    engagementTitle: '2023 Tax Return — LLC',
    assignedTo: 'Sarah K.',
    dueDate: '2024-09-01',
    status: 'not-started',
  },
]
