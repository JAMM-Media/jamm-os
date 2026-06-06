STANDING RULES — PERMANENT — DO NOT SKIP
[full standing rules block]

MIGRATION PROCEDURE — FOLLOW EVERY TIME
[full migration block]

PHASE INSTRUCTIONS — FIX NEWCLIENTMODAL TYPESCRIPT ERROR

No backend changes. No migrations. One file only: frontend/src/components/clients/NewClientModal.tsx

Read the file first.

The NewClientModalProps interface currently has:
  open: boolean
  onClose: () => void
  onAdd: (client: Client) => void
  initialName?: string

clients/page.tsx is passing four prefill props that do not exist in the interface:
  initialEmail, initialPhone, initialEntityType, and initialName (already exists)

Add the missing props to NewClientModalProps:
  initialEmail?: string
  initialPhone?: string
  initialEntityType?: string

Update the destructured function signature to include the new props:
  function NewClientModal({ open, onClose, onAdd, initialName, initialEmail, initialPhone, initialEntityType })

In the useEffect that watches [open, initialName], also set email, phone, and entity_type from the new props when they are provided:
  if (open) {
    if (initialName) setForm((prev) => ({ ...prev, name: initialName }))
    if (initialEmail) setForm((prev) => ({ ...prev, email: initialEmail }))
    if (initialPhone) setForm((prev) => ({ ...prev, phone: initialPhone }))
    if (initialEntityType) setForm((prev) => ({ ...prev, entity_type: initialEntityType }))
  }

Update the useEffect dependency array to include all four: [open, initialName, initialEmail, initialPhone, initialEntityType]

DO NOT run migrations. No backend changes. One file only.