// frontend/src/lib/mock/clients.ts

export type ClientStatus = 'active' | 'inactive'

export interface MockClient {
  id: string
  name: string
  primaryContact: string
  email: string
  phone: string
  industry: string
  status: ClientStatus
  activeEngagements: number
  awaitingDocs: number
  createdAt: string
}

export const mockClients: MockClient[] = [
  {
    id: '1',
    name: 'Acme Corp',
    primaryContact: 'James Holden',
    email: 'james@acmecorp.com',
    phone: '(212) 555-0101',
    industry: 'Manufacturing',
    status: 'active',
    activeEngagements: 3,
    awaitingDocs: 1,
    createdAt: '2024-01-15',
  },
  {
    id: '2',
    name: 'Bright Future LLC',
    primaryContact: 'Naomi Nagata',
    email: 'naomi@brightfuture.com',
    phone: '(212) 555-0102',
    industry: 'Technology',
    status: 'active',
    activeEngagements: 1,
    awaitingDocs: 0,
    createdAt: '2024-02-03',
  },
  {
    id: '3',
    name: 'Goldstein & Partners',
    primaryContact: 'Amos Burton',
    email: 'amos@goldsteinpartners.com',
    phone: '(212) 555-0103',
    industry: 'Legal',
    status: 'active',
    activeEngagements: 2,
    awaitingDocs: 2,
    createdAt: '2024-03-10',
  },
  {
    id: '4',
    name: 'Harvest Moon Farms',
    primaryContact: 'Bobbie Draper',
    email: 'bobbie@harvestmoon.com',
    phone: '(212) 555-0104',
    industry: 'Agriculture',
    status: 'inactive',
    activeEngagements: 0,
    awaitingDocs: 0,
    createdAt: '2023-11-20',
  },
  {
    id: '5',
    name: 'Ironclad Logistics',
    primaryContact: 'Alex Kamal',
    email: 'alex@ironclad.com',
    phone: '(212) 555-0105',
    industry: 'Transportation',
    status: 'active',
    activeEngagements: 1,
    awaitingDocs: 0,
    createdAt: '2024-04-01',
  },
]

export interface MockEngagementSummary {
  id: string
  title: string
  status: 'in-progress' | 'awaiting-docs' | 'complete' | 'overdue' | 'not-started'
  dueDate: string
  assignedTo: string
}

export interface MockClientDetail extends MockClient {
  address: string
  city: string
  state: string
  zip: string
  engagements: MockEngagementSummary[]
}

export const mockClientDetails: Record<string, MockClientDetail> = {
  '1': {
    id: '1',
    name: 'Acme Corp',
    primaryContact: 'James Holden',
    email: 'james@acmecorp.com',
    phone: '(212) 555-0101',
    industry: 'Manufacturing',
    status: 'active',
    activeEngagements: 3,
    awaitingDocs: 1,
    createdAt: '2024-01-15',
    address: '123 Main Street',
    city: 'New York',
    state: 'NY',
    zip: '10001',
    engagements: [
      {
        id: 'e1',
        title: '2023 Tax Return — Corporate',
        status: 'in-progress',
        dueDate: '2024-09-15',
        assignedTo: 'Sarah K.',
      },
      {
        id: 'e2',
        title: 'Q2 2024 Bookkeeping',
        status: 'awaiting-docs',
        dueDate: '2024-07-31',
        assignedTo: 'Mark T.',
      },
      {
        id: 'e3',
        title: '2022 Tax Return — Corporate',
        status: 'complete',
        dueDate: '2023-09-15',
        assignedTo: 'Sarah K.',
      },
    ],
  },
  '2': {
    id: '2',
    name: 'Bright Future LLC',
    primaryContact: 'Naomi Nagata',
    email: 'naomi@brightfuture.com',
    phone: '(212) 555-0102',
    industry: 'Technology',
    status: 'active',
    activeEngagements: 1,
    awaitingDocs: 0,
    createdAt: '2024-02-03',
    address: '456 Oak Avenue',
    city: 'Brooklyn',
    state: 'NY',
    zip: '11201',
    engagements: [
      {
        id: 'e4',
        title: '2023 Tax Return — Partnership',
        status: 'in-progress',
        dueDate: '2024-09-15',
        assignedTo: 'Mark T.',
      },
    ],
  },
  '3': {
    id: '3',
    name: 'Goldstein & Partners',
    primaryContact: 'Amos Burton',
    email: 'amos@goldsteinpartners.com',
    phone: '(212) 555-0103',
    industry: 'Legal',
    status: 'active',
    activeEngagements: 2,
    awaitingDocs: 2,
    createdAt: '2024-03-10',
    address: '789 Park Boulevard',
    city: 'Manhattan',
    state: 'NY',
    zip: '10022',
    engagements: [
      {
        id: 'e5',
        title: '2023 Tax Return — S-Corp',
        status: 'awaiting-docs',
        dueDate: '2024-09-15',
        assignedTo: 'Sarah K.',
      },
      {
        id: 'e6',
        title: 'Q1 2024 Bookkeeping',
        status: 'awaiting-docs',
        dueDate: '2024-04-30',
        assignedTo: 'Mark T.',
      },
    ],
  },
  '4': {
    id: '4',
    name: 'Harvest Moon Farms',
    primaryContact: 'Bobbie Draper',
    email: 'bobbie@harvestmoon.com',
    phone: '(212) 555-0104',
    industry: 'Agriculture',
    status: 'inactive',
    activeEngagements: 0,
    awaitingDocs: 0,
    createdAt: '2023-11-20',
    address: '12 Rural Route 4',
    city: 'Albany',
    state: 'NY',
    zip: '12201',
    engagements: [],
  },
  '5': {
    id: '5',
    name: 'Ironclad Logistics',
    primaryContact: 'Alex Kamal',
    email: 'alex@ironclad.com',
    phone: '(212) 555-0105',
    industry: 'Transportation',
    status: 'active',
    activeEngagements: 1,
    awaitingDocs: 0,
    createdAt: '2024-04-01',
    address: '55 Harbor Drive',
    city: 'Queens',
    state: 'NY',
    zip: '11101',
    engagements: [
      {
        id: 'e7',
        title: '2023 Tax Return — LLC',
        status: 'in-progress',
        dueDate: '2024-09-15',
        assignedTo: 'Sarah K.',
      },
    ],
  },
}

export function getClientDetail(id: string): MockClientDetail | null {
  return mockClientDetails[id] ?? null
}
