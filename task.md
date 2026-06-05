# ============================================================
# STANDING RULES — NEVER OVERRIDE
# ============================================================
# - All models use SQLAlchemy 2.0 Mapped[] syntax only
# - All schemas use Pydantic v2 (model_dump, field_validator)
# - Every router is thin — no business logic ever
# - Tenant isolation on every query via firm_id
# - UUID primary keys on all models
# - Never use --autogenerate blindly — always read migration before applying
# - Every generated file starts with a path comment
# - Never use native_enum=True for enums with dots or special characters
# - Background tasks create their own SessionLocal() in try/finally
# - Behavioral event log writes are fire-and-forget, never block main operation

# ============================================================
# MIGRATION PROCEDURE — FOLLOW EVERY TIME
# ============================================================
# 1. alembic current
# 2. alembic revision --autogenerate -m "description"
# 3. Read the generated file in full before applying
# 4. alembic upgrade head
# 5. alembic current — confirm at head

# ============================================================
# PHASE INSTRUCTIONS
# ============================================================

Edit this file only:
frontend/src/app/settings/page.tsx

Make exactly three changes:

1. Find:
   const [inviteRole, setInviteRole] = useState<'staff' | 'manager'>('staff')

   Replace with:
   const [inviteRole, setInviteRole] = useState<'staff' | 'manager' | 'firm_owner'>('staff')

2. Find:
   onChange={(e) => setInviteRole(e.target.value as 'staff' | 'manager')}

   Replace with:
   onChange={(e) => setInviteRole(e.target.value as 'staff' | 'manager' | 'firm_owner')}

3. Find the role select dropdown. It contains:
   <option value="staff">Staff</option>
   <option value="manager">Manager</option>

   Add one option above Staff so it reads:
   <option value="firm_owner">Partner</option>
   <option value="staff">Staff</option>
   <option value="manager">Manager</option>

No backend changes. No migration. No other files touched.