// frontend/src/lib/mock/documents.ts

export type DocumentStatus =
  | 'uploaded'
  | 'pending'
  | 'pending_signature'
  | 'signed'
  | 'rejected'

export interface MockDocument {
  id: string
  name: string
  clientId: string
  clientName: string
  engagementId: string
  engagementTitle: string
  status: DocumentStatus
  uploadedBy: string
  uploadedAt: string
  fileType: string
  fileSizeKb: number
  is_superseded?: boolean
}

export const mockDocuments: MockDocument[] = [
  {
    id: 'd1',
    name: '2023 W-2 — James Holden',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e1',
    engagementTitle: '2023 Tax Return — Corporate',
    status: 'uploaded',
    uploadedBy: 'Client',
    uploadedAt: '2024-07-01',
    fileType: 'PDF',
    fileSizeKb: 142,
  },
  {
    id: 'd2',
    name: 'Acme Corp — Bank Statement Q2',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e2',
    engagementTitle: 'Q2 2024 Bookkeeping',
    status: 'pending',
    uploadedBy: 'Client',
    uploadedAt: '2024-07-10',
    fileType: 'PDF',
    fileSizeKb: 398,
  },
  {
    id: 'd3',
    name: 'Engagement Letter — Acme Corp 2023',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e1',
    engagementTitle: '2023 Tax Return — Corporate',
    status: 'signed',
    uploadedBy: 'Staff',
    uploadedAt: '2024-01-20',
    fileType: 'PDF',
    fileSizeKb: 89,
  },
  {
    id: 'd4',
    name: '2023 1099-NEC — Bright Future LLC',
    clientId: '2',
    clientName: 'Bright Future LLC',
    engagementId: 'e4',
    engagementTitle: '2023 Tax Return — Partnership',
    status: 'uploaded',
    uploadedBy: 'Client',
    uploadedAt: '2024-07-14',
    fileType: 'PDF',
    fileSizeKb: 211,
  },
  {
    id: 'd5',
    name: 'Partnership Agreement — Bright Future',
    clientId: '2',
    clientName: 'Bright Future LLC',
    engagementId: 'e4',
    engagementTitle: '2023 Tax Return — Partnership',
    status: 'uploaded',
    uploadedBy: 'Client',
    uploadedAt: '2024-07-15',
    fileType: 'PDF',
    fileSizeKb: 504,
  },
  {
    id: 'd6',
    name: 'Engagement Letter — Goldstein 2023',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e5',
    engagementTitle: '2023 Tax Return — S-Corp',
    status: 'signed',
    uploadedBy: 'Staff',
    uploadedAt: '2024-03-12',
    fileType: 'PDF',
    fileSizeKb: 91,
  },
  {
    id: 'd7',
    name: 'Goldstein — Prior Year Return 2022',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e5',
    engagementTitle: '2023 Tax Return — S-Corp',
    status: 'pending',
    uploadedBy: 'Client',
    uploadedAt: '2024-07-18',
    fileType: 'PDF',
    fileSizeKb: 776,
  },
  {
    id: 'd8',
    name: '2023 Tax Return — LLC Draft',
    clientId: '5',
    clientName: 'Ironclad Logistics',
    engagementId: 'e7',
    engagementTitle: '2023 Tax Return — LLC',
    status: 'uploaded',
    uploadedBy: 'Staff',
    uploadedAt: '2024-07-22',
    fileType: 'PDF',
    fileSizeKb: 334,
  },
]

export function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}
