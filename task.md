STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Fix TypeScript error — refetch not in scope on tasks page

FILE TO EDIT: frontend/src/app/tasks/page.tsx

Find:
  const { data, isLoading, error } = useFetch(() => tasksApi.list(0, 100), [])

Change to:
  const { data, isLoading, error, refetch } = useFetch(() => tasksApi.list(0, 100), [])

Show the updated line after the change.