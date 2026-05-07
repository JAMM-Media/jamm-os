STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Fix TypeScript error — add assigned_to to tasksApi.create payload type

FILE TO EDIT: frontend/src/lib/api/tasks.ts
(or wherever tasksApi is defined — search for the create function
that has payload: { title: string; client_id: string; engagement_id: string; due_date?: string })

Find:
  create: async (payload: {
    title: string
    client_id: string
    engagement_id: string
    due_date?: string
  }): Promise<Task> => {

Change to:
  create: async (payload: {
    title: string
    client_id: string
    engagement_id: string
    due_date?: string
    assigned_to?: string
  }): Promise<Task> => {

Show the updated function signature after the change.