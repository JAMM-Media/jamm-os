# JAMM PX — Fix Document Status Display

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## TASK 1 — Backend: include envelope status in document list response

**File to edit:** `app/api/documents.py`

The GET /documents endpoint returns documents but doesn't include any envelope information. We need to enrich the response with the envelope status for documents that are linked to a signature envelope via `signed_document_id`.

Find the document list endpoint (GET /documents). Read how it queries and returns documents. After fetching the documents, do a single query to find all signature envelopes where `signed_document_id` is in the set of document IDs, then attach the envelope status to each document in the response.

Look at the existing `DocumentOut` schema — check if it has a `status` or `envelope_status` field. If not, the simplest approach is to add an `envelope_status: Optional[str] = None` field to `DocumentOut`.

Also check the `GET /documents/{id}` single document endpoint and apply the same enrichment.

Read the files carefully before writing any code. The goal is:
- If a document has a corresponding envelope (envelope.signed_document_id == document.id), return the envelope's status as the document's status
- If no envelope, return `"uploaded"` as the status (not None or "other")

**Do not change the Document model or run any migrations.** Only change the API response enrichment and schema.

---

## TASK 2 — Frontend: fix mapDocument status fallback

**File to edit:** `frontend/src/lib/api/documents.ts`

In the `mapDocument` function, line:
```typescript
status: (raw.status as Document['status']) ?? 'pending',
```

Change the fallback from `'pending'` to `'uploaded'`:
```typescript
status: (raw.status as Document['status']) ?? 'uploaded',
```

Also update the `Document` interface to include `'pending_signature'` as a valid status value since that's what the StatusBadge uses:
```typescript
status: 'uploaded' | 'pending' | 'pending_signature' | 'signed' | 'rejected'
```

---

## EXECUTION ORDER

1. Task 1 — backend: read documents.py carefully, enrich response with envelope status
2. Task 2 — frontend: fix mapDocument fallback

After all tasks: report every file modified.