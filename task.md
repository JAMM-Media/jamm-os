═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend changes only.

═══════════════════════════════════════════════════════════════
TASK: Fix TypeScript build error in login page
═══════════════════════════════════════════════════════════════

File: frontend/src/app/(auth)/login/page.tsx

The result object returned by login() does not have a role
field. Remove the role check from handleSubmit — the useEffect
already handles the role-based redirect reliably.

Find this block:
    if (result.success) {
      if (result.role === 'staff') {
        router.push('/tasks')
      } else {
        router.push('/dashboard')
      }
    }

Replace it with:
    if (result.success) {
      router.push('/dashboard')
    }

The useEffect watching isAuthenticated and user.role will
immediately redirect staff to /tasks after login resolves.
No role check needed here.

Do not touch any other file.