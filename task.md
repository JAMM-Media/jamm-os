STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix NewClientModal — actually save client to database via API

FILE TO EDIT: frontend/src/components/clients/NewClientModal.tsx

PROBLEM: handleSubmit creates a fake client object with id: String(Date.now())
and calls onAdd() without ever making an API call. The client is never
saved to the database so it disappears on navigation.

FIX: Replace the fake client creation with a real API call to
clientsApi.create(), then pass the real server response to onAdd().

STEP 1: Import clientsApi and toast at the top of the file.

Add these imports:
  import { clientsApi, type Client } from '@/lib/api'
  import { toast } from 'sonner'

Note: type Client is already imported so just add clientsApi to that
import line.

STEP 2: Replace the entire handleSubmit function.

Find:
  function handleSubmit() {
    const validation = validate(form)
    if (Object.keys(validation).length > 0) {
      setErrors(validation)
      return
    }

    setSubmitting(true)

    const newClient: Client = {
      id: String(Date.now()),
      name: form.name.trim(),
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      companyName: null,
      addressLine1: null,
      addressLine2: null,
      city: null,
      state: null,
      postalCode: null,
      country: null,
      isActive: true,
      entityType: form.entity_type || null,
      tags: [],
      notes: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }

    onAdd(newClient)
    setSubmitting(false)
    handleClose()
  }

Replace with:
  async function handleSubmit() {
    const validation = validate(form)
    if (Object.keys(validation).length > 0) {
      setErrors(validation)
      return
    }

    setSubmitting(true)
    try {
      const newClient = await clientsApi.create({
        name: form.name.trim(),
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        entity_type: form.entity_type || null,
      })
      onAdd(newClient)
      handleClose()
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Failed to create client'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

Also change the handleSubmit button onClick to not need to be async-safe —
the button already has disabled={submitting} so no change needed there.

After making changes show the updated handleSubmit function.