STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Fix task auto in_progress — useEffect not firing correctly

FILE TO EDIT: frontend/src/app/tasks/[id]/page.tsx

PROBLEM: The useEffect dependency array is [task?.id, user?.id]. When
the component mounts, task is null so the effect fires but exits early.
When task loads, neither task.id nor user.id changed so the effect
doesn't re-fire.

FIX: Change the dependency array to include task?.status so the effect
re-runs when task data arrives:

Find:
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

Change to:
  useEffect(() => {
    if (!task || !user) return
    if (
      task.status === 'todo' &&
      task.assignedTo === user.id
    ) {
      tasksApi.update(task.id, { status: 'in_progress' }).then(() => refetch())
    }
  }, [task?.id, task?.status, user?.id])

Show the updated useEffect after the change.