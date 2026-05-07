STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Refetch task list after bulk reassign so names update immediately

FILE TO EDIT: frontend/src/app/(dashboard)/tasks/page.tsx
(or wherever handleBulkReassign is defined)

Find:
  async function handleBulkReassign(userId: string) {
    setReassignDropOpen(false)
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    try {
      await tasksApi.bulkUpdate(ids, { assigned_to: userId })
      setSelectedIds(new Set())
      toast.success(`Reassigned ${ids.length} task${ids.length !== 1 ? 's' : ''}`)
    } catch {
      toast.error('Reassign failed')
    } finally {
      setBulkLoading(false)
    }
  }

Change to:
  async function handleBulkReassign(userId: string) {
    setReassignDropOpen(false)
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    try {
      await tasksApi.bulkUpdate(ids, { assigned_to: userId })
      setSelectedIds(new Set())
      toast.success(`Reassigned ${ids.length} task${ids.length !== 1 ? 's' : ''}`)
      refetch()
    } catch {
      toast.error('Reassign failed')
    } finally {
      setBulkLoading(false)
    }
  }

Show the updated function after the change.