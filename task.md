# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment