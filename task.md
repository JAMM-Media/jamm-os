═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend changes only.

═══════════════════════════════════════════════════════════════
TASK: Staff login redirect + auto My Tasks filter
═══════════════════════════════════════════════════════════════

TWO files to edit. Do both before committing.

─────────────────────────────────────────────────────────────
CHANGE 1 — frontend/src/app/login/page.tsx
─────────────────────────────────────────────────────────────

The login page currently has two places that push to '/dashboard'
regardless of role. Update both to redirect staff to '/tasks'
instead.

Step 1: The useAuth import line already exists. Add user to the
destructured values:
  BEFORE: const { login, isAuthenticated } = useAuth()
  AFTER:  const { login, isAuthenticated, user } = useAuth()

Step 2: The useEffect that fires when isAuthenticated changes:
  BEFORE:
    useEffect(() => {
      if (isAuthenticated) {
        router.push('/dashboard')
      }
    }, [isAuthenticated, router])

  AFTER:
    useEffect(() => {
      if (isAuthenticated) {
        if (user?.role === 'staff') {
          router.push('/tasks')
        } else {
          router.push('/dashboard')
        }
      }
    }, [isAuthenticated, user, router])

Step 3: Inside handleSubmit, after result.success:
  BEFORE:
    if (result.success) {
      router.push('/dashboard')
    }

  AFTER:
    if (result.success) {
      if (result.role === 'staff') {
        router.push('/tasks')
      } else {
        router.push('/dashboard')
      }
    }

NOTE: result.role may not be available — if it isn't, the
useEffect in Step 2 will catch it anyway since isAuthenticated
flips after login. Step 3 is a best-effort fast path. Do not
break anything trying to force result.role — just apply it
if the field is clearly present in the result object.

─────────────────────────────────────────────────────────────
CHANGE 2 — frontend/src/app/(dashboard)/tasks/page.tsx
─────────────────────────────────────────────────────────────

The tasks page has this state initialization:
  const [myTasksOnly, setMyTasksOnly] = useState(false)

And it already imports useAuth and has access to user.

Change the initialization so staff users start with the
My Tasks filter pre-enabled:

  BEFORE:
    const [myTasksOnly, setMyTasksOnly] = useState(false)

  AFTER:
    const { user } = useAuth()
    const [myTasksOnly, setMyTasksOnly] = useState(false)

  Then add a useEffect directly below:
    useEffect(() => {
      if (user?.role === 'staff') {
        setMyTasksOnly(true)
      }
    }, [user?.role])

IMPORTANT: Check if useAuth is already imported and if user is
already destructured on the tasks page before adding them —
do not duplicate imports or variable declarations. Only add
what is missing.

─────────────────────────────────────────────────────────────
AFTER BOTH CHANGES
─────────────────────────────────────────────────────────────
Confirm both files were modified and report the exact lines
changed in each file. Do not run any backend commands.