STANDING RULES — PERMANENT — DO NOT SKIP

Architecture rules:
- All models use UUID primary keys, firm_id FK, created_at and updated_at (timezone-aware)
- Every module has 4 Pydantic schemas: XBase, XCreate, XUpdate, XOut
- Routers are thin — no business logic ever
- All list endpoints paginated using PaginatedResponse[T]
- RBAC enforced at every endpoint
- Tenant isolation absolute — every query scoped to firm_id without exception
- Signed URLs only for all file access — never public S3 URLs, 1 hour maximum expiry
- Audit logging on every sensitive action
- Always use string names in relationship() to avoid circular imports
- Every generated file starts with a path comment
- Background tasks that touch the database must create their own SessionLocal() in a try/finally block — never pass the request db session into a background task
- Never use native_enum=True for enums whose values contain dots or special characters — always use sa.Enum(MyEnum, native_enum=False)
- Behavioral event log: fire-and-forget only, never block the main operation, service layer only, own session, never inherit the request session
- Always use SQLAlchemy 2.0 Mapped[] syntax — never Column() style
- Always use Pydantic v2 — model_dump() and field_validator() only, never .dict() or @validator
- DATABASE_URL uses postgresql+psycopg:// dialect prefix — never plain postgresql://
- Never use && to chain commands in PowerShell — separate every command onto its own line
- Never use em dashes anywhere in any string, copy, or comment

---

MIGRATION PROCEDURE — FOLLOW EVERY TIME

1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

PHASE INSTRUCTIONS — ADD ENTITY SUBTYPE FIELD

This adds entity_subtype as an optional VARCHAR column to the clients table, with backend validation and frontend dropdowns that appear conditionally based on the selected entity_type.

---

STEP 1 — MIGRATION

Current head: 0043_user_login_lockout_fields

Run: alembic revision --autogenerate -m "add_entity_subtype_to_clients"

Read the generated file. It should only contain one change: adding entity_subtype to the clients table. If it contains anything else, delete it and write a clean manual migration instead:

from alembic import op
import sqlalchemy as sa

revision = '0044_add_entity_subtype_to_clients'
down_revision = '0043_user_login_lockout_fields'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('clients', sa.Column(
        'entity_subtype',
        sa.String(50),
        nullable=True,
        comment='sole_proprietor | partnership | llc | s_corp | c_corp | professional_corp | revocable_trust | irrevocable_trust | charitable_trust | special_needs_trust | public_charity | private_foundation | social_welfare | other_tax_exempt'
    ))

def downgrade():
    op.drop_column('clients', 'entity_subtype')

Run alembic upgrade head. Confirm at new head.

---

STEP 2 — BACKEND MODEL: app/models/client.py

After the entity_type column definition, add:

    entity_subtype: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="sole_proprietor | partnership | llc | s_corp | c_corp | professional_corp | revocable_trust | irrevocable_trust | charitable_trust | special_needs_trust | public_charity | private_foundation | social_welfare | other_tax_exempt",
    )

---

STEP 3 — BACKEND SCHEMAS: app/schemas/client.py

The valid subtypes per entity type:

Business subtypes: sole_proprietor, partnership, llc, s_corp, c_corp, professional_corp
Trust subtypes: revocable_trust, irrevocable_trust, charitable_trust, special_needs_trust
Non-profit subtypes: public_charity, private_foundation, social_welfare, other_tax_exempt
Individual: no subtypes
Estate: no subtypes

In ClientBase:
- Add field: entity_subtype: Optional[str] = None
- Add validator:

    @field_validator("entity_subtype")
    @classmethod
    def validate_entity_subtype(cls, v):
        if v is None:
            return v
        valid = {
            "sole_proprietor", "partnership", "llc", "s_corp", "c_corp", "professional_corp",
            "revocable_trust", "irrevocable_trust", "charitable_trust", "special_needs_trust",
            "public_charity", "private_foundation", "social_welfare", "other_tax_exempt",
        }
        if v not in valid:
            raise ValueError(f"entity_subtype must be one of {sorted(valid)}")
        return v

In ClientUpdate:
- Add field: entity_subtype: Optional[str] = None
- Add the same validator as above

In ClientOut: entity_subtype is inherited from ClientBase so no change needed.

Also update the non_profit entries in both existing entity_type validators -- they currently read:
  valid = {"individual", "business", "trust", "estate"}
They should already have non_profit from the previous task. If they do not, add it now:
  valid = {"individual", "business", "trust", "estate", "non_profit"}

---

STEP 4 — BACKEND CSV IMPORT: app/api/clients.py

In the CSV import endpoint, after the entity_type mapping line, add handling for entity_subtype:

entity_subtype = row.get("entity_subtype", "").strip().lower() or None

Add entity_subtype to the Client constructor in the import loop:
    entity_subtype=entity_subtype,

---

STEP 5 — FRONTEND UTILS: frontend/src/lib/utils.ts

Add a new exported utility function after formatEntityType:

export function formatEntitySubtype(entitySubtype: string | null | undefined): string {
  if (!entitySubtype) return ''
  const labels: Record<string, string> = {
    sole_proprietor: 'Sole Proprietor',
    partnership: 'Partnership',
    llc: 'LLC',
    s_corp: 'S-Corp',
    c_corp: 'C-Corp',
    professional_corp: 'Professional Corp',
    revocable_trust: 'Revocable Trust',
    irrevocable_trust: 'Irrevocable Trust',
    charitable_trust: 'Charitable Trust',
    special_needs_trust: 'Special Needs Trust',
    public_charity: 'Public Charity (501c3)',
    private_foundation: 'Private Foundation (501c3)',
    social_welfare: 'Social Welfare (501c4)',
    other_tax_exempt: 'Other Tax-Exempt',
  }
  return labels[entitySubtype] ?? entitySubtype
}

---

STEP 6 — FRONTEND MODALS: EditClientModal and NewClientModal

In both frontend/src/components/clients/EditClientModal.tsx and frontend/src/components/clients/NewClientModal.tsx:

1. Add entity_subtype to the form state and interface. The form already has entity_type -- add entity_subtype: string alongside it, defaulting to ''.

2. Add a SUBTYPE_OPTIONS constant:

const SUBTYPE_OPTIONS: Record<string, { value: string; label: string }[]> = {
  business: [
    { value: 'sole_proprietor', label: 'Sole Proprietor' },
    { value: 'partnership', label: 'Partnership' },
    { value: 'llc', label: 'LLC' },
    { value: 's_corp', label: 'S-Corp' },
    { value: 'c_corp', label: 'C-Corp' },
    { value: 'professional_corp', label: 'Professional Corp' },
  ],
  trust: [
    { value: 'revocable_trust', label: 'Revocable Trust' },
    { value: 'irrevocable_trust', label: 'Irrevocable Trust' },
    { value: 'charitable_trust', label: 'Charitable Trust' },
    { value: 'special_needs_trust', label: 'Special Needs Trust' },
  ],
  non_profit: [
    { value: 'public_charity', label: 'Public Charity (501c3)' },
    { value: 'private_foundation', label: 'Private Foundation (501c3)' },
    { value: 'social_welfare', label: 'Social Welfare (501c4)' },
    { value: 'other_tax_exempt', label: 'Other Tax-Exempt' },
  ],
}

3. After the Entity Type select field in the form JSX, add a conditional subtype select that only renders when the selected entity_type has subtypes available:

{SUBTYPE_OPTIONS[form.entity_type] && (
  <SelectInput (or the same select pattern used for entity_type)
    label="Entity Subtype"
    value={form.entity_subtype}
    onChange={(e) => handleChange('entity_subtype', e.target.value)}
    options with a blank first option "-- Select subtype --" followed by SUBTYPE_OPTIONS[form.entity_type]
  />
)}

4. When entity_type changes and the new type has no subtypes (individual, estate), reset entity_subtype to ''. In the handleChange function, if the field being changed is entity_type and the new value is individual or estate, also set entity_subtype to ''.

5. Include entity_subtype in the PATCH payload (EditClientModal) and POST payload (NewClientModal). Send null when empty string.

6. In EditClientModal, populate entity_subtype from the existing client data on load, same pattern as entity_type.

---

STEP 7 — FRONTEND DISPLAY: client profile and client list

In frontend/src/app/clients/[id]/page.tsx:
- Import formatEntitySubtype from @/lib/utils
- Find where client.entityType is displayed with formatEntityType. After that span, add:
  {client.entitySubtype && (
    <span className="text-[12px] text-[#6B7280]">{formatEntitySubtype(client.entitySubtype)}</span>
  )}

The Client type interface needs entity_subtype added. Find wherever entityType is declared in the client interface/type and add entitySubtype: string | null | undefined alongside it. The API response will include it since it is on ClientOut.

In frontend/src/components/clients/ClientTable.tsx:
- The entity type column currently shows formatEntityType alone. Update to show combined label when subtype exists:
  {formatEntityType(client.entityType)}{client.entitySubtype ? ` -- ${formatEntitySubtype(client.entitySubtype)}` : ''} || '—'

Import formatEntitySubtype from @/lib/utils.

In frontend/src/components/clients/ClientCard.tsx:
- Same combined label pattern as the table:
  {formatEntityType(client.entityType)}{client.entitySubtype ? ` -- ${formatEntitySubtype(client.entitySubtype)}` : ''}

Import formatEntitySubtype from @/lib/utils.

---

MIGRATION REMINDER: This build requires a migration. Follow the migration procedure at the top exactly. Do not skip alembic current before and after.

After completing confirm:
- Migration 0044 exists and was applied
- entity_subtype column on clients table
- entity_subtype in model, both schemas, CSV import
- formatEntitySubtype in utils.ts
- Both modals show conditional subtype dropdown
- Display updated in profile, table, and card