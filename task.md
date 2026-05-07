STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Add Assign To field to NewTaskModal + auto in_progress on task open

═══════════════════════════════════════════════════════════
CHANGE 1 — Add Assign To field to NewTaskModal
═══════════════════════════════════════════════════════════

FILE: frontend/src/components/tasks/NewTaskModal.tsx

Add assignedTo to FormState:
  interface FormState {
    title: string
    clientId: string
    engagementId: string
    dueDate: string
    assignedTo: string
  }

Add to initial state:
  const [form, setForm] = useState<FormState>({
    title: '',
    clientId: '',
    engagementId: '',
    dueDate: '',
    assignedTo: '',
  })

Add staff list state after engagements state:
  const [staff, setStaff] = useState<Array<{ value: string; label: string }>>([])
  const [staffLoading, setStaffLoading] = useState(false)

Add a useEffect to load staff when modal opens (add after the
engagements useEffect):
  useEffect(() => {
    if (!open) return
    setStaffLoading(true)
    import('@/lib/api').then(({ default: api }) =>
      api.get('/users/').then((res) => {
        const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
        setStaff(items.map((u: Record<string, unknown>) => ({
          value: String(u.id),
          label: String(u.full_name ?? u.name ?? ''),
        })))
      }).catch(() => setStaff([]))
        .finally(() => setStaffLoading(false))
    )
  }, [open])

Note: api is already imported as a named import from @/lib/api —
check if default api client is available. If not, use:
  import api from '@/lib/api'
  at the top and call api.get directly in the useEffect without dynamic import.

Add assigned_to to the handleSubmit API call:
  const task = await tasksApi.create({
    title: form.title.trim(),
    client_id: form.clientId,
    engagement_id: form.engagementId,
    due_date: form.dueDate || undefined,
    assigned_to: form.assignedTo || undefined,
  })

Add the Assign To select field to the form UI, after the due date field:
  <FormField label="Assign To">
    <SelectInput
      value={form.assignedTo}
      onChange={(e) => handleChange('assignedTo', e.target.value)}
      disabled={staffLoading}
      options={[
        { value: '', label: staffLoading ? 'Loading...' : 'Unassigned' },
        ...staff,
      ]}
    />
  </FormField>

Also update handleClose to reset assignedTo:
  setForm({ title: '', clientId: '', engagementId: '', dueDate: '', assignedTo: '' })

═══════════════════════════════════════════════════════════
CHANGE 2 — Auto-switch to in_progress when assigned user opens task
═══════════════════════════════════════════════════════════

FILE: frontend/src/app/tasks/[id]/page.tsx

Add useEffect and useAuth imports:
  import { useState, useEffect } from 'react'
  import { useAuth } from '@/lib/hooks/useAuth'

Add inside the component after the existing state declarations:
  const { user } = useAuth()

Add a useEffect that fires after task loads:
  useEffect(() => {
    if (!task || !user) return
    // Auto-switch to in_progress when the assigned user first opens the task
    if (
      task.status === 'todo' &&
      task.assignedTo === user.id
    ) {
      tasksApi.update(task.id, { status: 'in_progress' }).then(() => refetch())
    }
  }, [task?.id, user?.id])

After making changes show:
1. The updated FormState interface
2. The Assign To select field JSX
3. The useEffect in task detail page