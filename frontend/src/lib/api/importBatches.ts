// frontend/src/lib/api/importBatches.ts
import api from '@/lib/api'

// ---------------------------------------------------------------------------
// Response interfaces -- camelCase, mapped from backend snake_case fields.
// Follows the mapDocument / mapTask convention used throughout this codebase:
// manual field-by-field mapping, no automatic snake_case->camelCase middleware.
// ---------------------------------------------------------------------------

export interface ImportItemOut {
  id: string
  importBatchId: string
  firmId: string
  ordinal: number
  relativePath: string
  normalizedRelativePath: string
  filename: string
  expectedBytes: number
  mimeType: string | null
  conflictOverride: string | null
  status: string
  attemptCount: number
  availableAt: string
  stagingS3Key: string | null
  finalDocumentId: string | null
  finalFolderId: string | null
  errorCode: string | null
  errorDetail: string | null
  createdAt: string
  completedAt: string | null
}

export interface ImportBatchOut {
  id: string
  firmId: string
  createdByUserId: string | null
  scope: string
  clientId: string | null
  engagementId: string | null
  destinationFolderId: string | null
  conflictPolicy: string
  status: string
  totalFiles: number
  totalBytes: number
  completedFiles: number
  failedFiles: number
  skippedFiles: number
  lastError: string | null
  createdAt: string
  confirmedAt: string | null
  finishedAt: string | null
  items: ImportItemOut[]
}

// ---------------------------------------------------------------------------
// Request payload -- backend expects snake_case in the request body.
// ---------------------------------------------------------------------------

export interface ImportItemCreate {
  relative_path: string
  filename: string
  expected_bytes: number
  mime_type: string | null
}

export interface CreateImportBatchPayload {
  scope: string
  client_id?: string
  engagement_id?: string
  destination_folder_id?: string
  conflict_policy: string
  items: ImportItemCreate[]
}

// ---------------------------------------------------------------------------
// Mapping helpers
// ---------------------------------------------------------------------------

function mapItem(raw: Record<string, unknown>): ImportItemOut {
  return {
    id: String(raw.id),
    importBatchId: String(raw.import_batch_id),
    firmId: String(raw.firm_id),
    ordinal: Number(raw.ordinal),
    relativePath: String(raw.relative_path),
    normalizedRelativePath: String(raw.normalized_relative_path),
    filename: String(raw.filename),
    expectedBytes: Number(raw.expected_bytes),
    mimeType: raw.mime_type ? String(raw.mime_type) : null,
    conflictOverride: raw.conflict_override ? String(raw.conflict_override) : null,
    status: String(raw.status),
    attemptCount: Number(raw.attempt_count),
    availableAt: String(raw.available_at),
    stagingS3Key: raw.staging_s3_key ? String(raw.staging_s3_key) : null,
    finalDocumentId: raw.final_document_id ? String(raw.final_document_id) : null,
    finalFolderId: raw.final_folder_id ? String(raw.final_folder_id) : null,
    errorCode: raw.error_code ? String(raw.error_code) : null,
    errorDetail: raw.error_detail ? String(raw.error_detail) : null,
    createdAt: String(raw.created_at),
    completedAt: raw.completed_at ? String(raw.completed_at) : null,
  }
}

function mapBatch(raw: Record<string, unknown>): ImportBatchOut {
  return {
    id: String(raw.id),
    firmId: String(raw.firm_id),
    createdByUserId: raw.created_by_user_id ? String(raw.created_by_user_id) : null,
    scope: String(raw.scope),
    clientId: raw.client_id ? String(raw.client_id) : null,
    engagementId: raw.engagement_id ? String(raw.engagement_id) : null,
    destinationFolderId: raw.destination_folder_id ? String(raw.destination_folder_id) : null,
    conflictPolicy: String(raw.conflict_policy),
    status: String(raw.status),
    totalFiles: Number(raw.total_files),
    totalBytes: Number(raw.total_bytes),
    completedFiles: Number(raw.completed_files),
    failedFiles: Number(raw.failed_files),
    skippedFiles: Number(raw.skipped_files),
    lastError: raw.last_error ? String(raw.last_error) : null,
    createdAt: String(raw.created_at),
    confirmedAt: raw.confirmed_at ? String(raw.confirmed_at) : null,
    finishedAt: raw.finished_at ? String(raw.finished_at) : null,
    items: Array.isArray(raw.items)
      ? (raw.items as Record<string, unknown>[]).map(mapItem)
      : [],
  }
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Preview interfaces
// ---------------------------------------------------------------------------

export interface ImportItemPreview {
  itemId: string
  resolved: boolean
  hasConflict: boolean
  existingDocumentId: string | null
  existingDocumentFilename: string | null
  pathWouldExceedDepth: boolean
}

export interface ImportBatchPreview {
  batchId: string
  items: ImportItemPreview[]
}

function mapItemPreview(raw: Record<string, unknown>): ImportItemPreview {
  return {
    itemId: String(raw.item_id),
    resolved: Boolean(raw.resolved),
    hasConflict: Boolean(raw.has_conflict),
    existingDocumentId: raw.existing_document_id ? String(raw.existing_document_id) : null,
    existingDocumentFilename: raw.existing_document_filename ? String(raw.existing_document_filename) : null,
    pathWouldExceedDepth: Boolean(raw.path_would_exceed_depth),
  }
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export const importBatchesApi = {
  create: async (payload: CreateImportBatchPayload): Promise<ImportBatchOut> => {
    const { data } = await api.post('/import-batches/', payload)
    return mapBatch(data as Record<string, unknown>)
  },

  get: async (batchId: string): Promise<ImportBatchOut> => {
    const { data } = await api.get(`/import-batches/${batchId}`)
    return mapBatch(data as Record<string, unknown>)
  },

  confirm: async (batchId: string): Promise<ImportBatchOut> => {
    const { data } = await api.post(`/import-batches/${batchId}/confirm`)
    return mapBatch(data as Record<string, unknown>)
  },

  preview: async (batchId: string): Promise<ImportBatchPreview> => {
    const { data } = await api.get(`/import-batches/${batchId}/preview`)
    const raw = data as Record<string, unknown>
    return {
      batchId: String(raw.batch_id),
      items: Array.isArray(raw.items)
        ? (raw.items as Record<string, unknown>[]).map(mapItemPreview)
        : [],
    }
  },

  updateConflictPolicy: async (batchId: string, conflictPolicy: string): Promise<ImportBatchOut> => {
    const { data } = await api.patch(`/import-batches/${batchId}`, { conflict_policy: conflictPolicy })
    return mapBatch(data as Record<string, unknown>)
  },
}
