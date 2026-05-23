═══════════════════════════════════════════════════════════════
STANDING RULES — READ BEFORE DOING ANYTHING
═══════════════════════════════════════════════════════════════
- Backend lives at /var/www/jammpx
- Frontend lives at /var/www/jammpx/frontend
- Always activate the virtual environment before running any
  backend command: source .venv/bin/activate
- Never use && to chain commands — run them one at a time
- All migrations follow this exact sequence:
    1. alembic current — confirm starting state
    2. alembic revision --autogenerate -m "description"
    3. Read the generated file in full before running it
    4. If it touches anything beyond the target table,
       delete it and write a clean manual migration
    5. alembic upgrade head
    6. alembic current — confirm at head
- After any backend change: systemctl restart jammpx.service
- After any frontend change: push to GitHub — Vercel
  auto-deploys
- Never modify alembic env.py imports unless adding a new model
- Never chain commands with &&

═══════════════════════════════════════════════════════════════
MIGRATION PROCEDURE
═══════════════════════════════════════════════════════════════
Current head: 0033_add_document_expiries_table
Next migrations: 0034 and 0035

═══════════════════════════════════════════════════════════════
TASK: Internal QC Checklists
═══════════════════════════════════════════════════════════════

WHAT WE ARE BUILDING
Two new models:
- QcChecklistTemplate — firm-level template tied to an
  engagement type, contains a list of item titles
- QcChecklistItem — per-engagement checklist items,
  auto-populated from the template when an engagement is
  created, plus free-form items staff can add manually

Templates are managed in the Templates page under a new
QC Checklists sub-tab. The Deleted sub-tab gets a fourth
internal sub-tab for deleted QC templates.

Each engagement gets a QC Checklist tab between Tasks and
Documents. Staff check off items before marking complete.
A soft warning fires if unchecked items remain when staff
try to mark the engagement complete.

═══════════════════════════════════════════════════════════════
STEP 1 — Create QcChecklistTemplate model
═══════════════════════════════════════════════════════════════

Create new file: app/models/qc_checklist.py

Two models in one file:

MODEL 1 — QcChecklistTemplate

    __tablename__ = "qc_checklist_templates"

    id: UUID primary key, default uuid4
    firm_id: UUID FK to firms.id CASCADE, indexed
    name: String(200) nullable=False
    engagement_type: String(50) nullable=True
        — if set, auto-applies to that engagement type
        — if null, manual-apply only
    items: JSON nullable=False default=list
        — list of strings, each is a checklist item title
        — example: ["Verify prior year carryforward",
                    "Confirm bank account for direct deposit"]
    is_active: Boolean default=True nullable=False
    created_at: DateTime timezone=True server_default now
    updated_at: DateTime timezone=True onupdate now

    Relationships:
        firm: relationship("Firm")

MODEL 2 — QcChecklistItem

    __tablename__ = "qc_checklist_items"

    id: UUID primary key, default uuid4
    firm_id: UUID FK to firms.id CASCADE, indexed
    engagement_id: UUID FK to engagements.id CASCADE,
        indexed
    title: String(500) nullable=False
    is_checked: Boolean default=False nullable=False
    checked_by_id: UUID FK to users.id SET NULL nullable
    checked_at: DateTime timezone=True nullable=True
    is_from_template: Boolean default=False nullable=False
        — True if auto-populated from a template
        — False if manually added by staff
    order: Integer default=0 nullable=False
    created_at: DateTime timezone=True server_default now

    Relationships:
        firm: relationship("Firm")
        engagement: relationship("Engagement")
        checked_by: relationship("User",
            foreign_keys=[checked_by_id])

═══════════════════════════════════════════════════════════════
STEP 2 — Register models
═══════════════════════════════════════════════════════════════

File: migrations/env.py
Add:
    from app.models.qc_checklist import (
        QcChecklistTemplate, QcChecklistItem
    )

File: app/models/__init__.py
Add:
    from app.models.qc_checklist import (
        QcChecklistTemplate, QcChecklistItem
    )

═══════════════════════════════════════════════════════════════
STEP 3 — Create Pydantic schemas
═══════════════════════════════════════════════════════════════

Create new file: app/schemas/qc_checklist.py

    from datetime import datetime
    from typing import Optional, List
    import uuid
    from pydantic import BaseModel, ConfigDict

    class QcChecklistTemplateBase(BaseModel):
        name: str
        engagement_type: Optional[str] = None
        items: List[str] = []

    class QcChecklistTemplateCreate(QcChecklistTemplateBase):
        pass

    class QcChecklistTemplateUpdate(BaseModel):
        name: Optional[str] = None
        engagement_type: Optional[str] = None
        items: Optional[List[str]] = None
        is_active: Optional[bool] = None

    class QcChecklistTemplateOut(QcChecklistTemplateBase):
        id: uuid.UUID
        firm_id: uuid.UUID
        is_active: bool
        created_at: datetime
        updated_at: datetime
        model_config = ConfigDict(from_attributes=True)

    class QcChecklistItemBase(BaseModel):
        title: str
        order: int = 0

    class QcChecklistItemCreate(QcChecklistItemBase):
        engagement_id: uuid.UUID
        is_from_template: bool = False

    class QcChecklistItemUpdate(BaseModel):
        title: Optional[str] = None
        is_checked: Optional[bool] = None
        order: Optional[int] = None

    class QcChecklistItemOut(QcChecklistItemBase):
        id: uuid.UUID
        firm_id: uuid.UUID
        engagement_id: uuid.UUID
        is_checked: bool
        checked_by_id: Optional[uuid.UUID] = None
        checked_at: Optional[datetime] = None
        is_from_template: bool
        created_at: datetime
        model_config = ConfigDict(from_attributes=True)

═══════════════════════════════════════════════════════════════
STEP 4 — Create CRUD functions
═══════════════════════════════════════════════════════════════

Create new file: app/crud/qc_checklist.py

    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.models.qc_checklist import (
        QcChecklistTemplate, QcChecklistItem
    )
    from app.schemas.qc_checklist import (
        QcChecklistTemplateCreate, QcChecklistTemplateUpdate,
        QcChecklistItemCreate, QcChecklistItemUpdate
    )
    import uuid
    from datetime import datetime, timezone

    # --- Template CRUD ---

    def create_template(db, firm_id, data):
        obj = QcChecklistTemplate(firm_id=firm_id,
            **data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def list_templates(db, firm_id, include_inactive=False):
        stmt = select(QcChecklistTemplate).where(
            QcChecklistTemplate.firm_id == firm_id
        )
        if not include_inactive:
            stmt = stmt.where(
                QcChecklistTemplate.is_active == True
            )
        return db.execute(stmt.order_by(
            QcChecklistTemplate.name
        )).scalars().all()

    def get_template(db, firm_id, template_id):
        return db.execute(
            select(QcChecklistTemplate).where(
                QcChecklistTemplate.id == template_id,
                QcChecklistTemplate.firm_id == firm_id,
            )
        ).scalars().first()

    def update_template(db, obj, data):
        for field, value in data.model_dump(
            exclude_unset=True
        ).items():
            setattr(obj, field, value)
        db.commit()
        db.refresh(obj)
        return obj

    def soft_delete_template(db, obj):
        obj.is_active = False
        db.commit()

    def restore_template(db, obj):
        obj.is_active = True
        db.commit()

    def get_template_for_engagement_type(
        db, firm_id, engagement_type
    ):
        return db.execute(
            select(QcChecklistTemplate).where(
                QcChecklistTemplate.firm_id == firm_id,
                QcChecklistTemplate.engagement_type
                    == engagement_type,
                QcChecklistTemplate.is_active == True,
            )
        ).scalars().first()

    # --- Item CRUD ---

    def create_item(db, firm_id, data):
        obj = QcChecklistItem(firm_id=firm_id,
            **data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def list_items(db, firm_id, engagement_id):
        return db.execute(
            select(QcChecklistItem)
            .where(
                QcChecklistItem.firm_id == firm_id,
                QcChecklistItem.engagement_id
                    == engagement_id,
            )
            .order_by(
                QcChecklistItem.order,
                QcChecklistItem.created_at,
            )
        ).scalars().all()

    def get_item(db, firm_id, item_id):
        return db.execute(
            select(QcChecklistItem).where(
                QcChecklistItem.id == item_id,
                QcChecklistItem.firm_id == firm_id,
            )
        ).scalars().first()

    def check_item(db, obj, user_id):
        obj.is_checked = True
        obj.checked_by_id = user_id
        obj.checked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(obj)
        return obj

    def uncheck_item(db, obj):
        obj.is_checked = False
        obj.checked_by_id = None
        obj.checked_at = None
        db.commit()
        db.refresh(obj)
        return obj

    def update_item(db, obj, data):
        for field, value in data.model_dump(
            exclude_unset=True
        ).items():
            setattr(obj, field, value)
        db.commit()
        db.refresh(obj)
        return obj

    def delete_item(db, obj):
        db.delete(obj)
        db.commit()

    def populate_from_template(
        db, firm_id, engagement_id, engagement_type
    ):
        template = get_template_for_engagement_type(
            db, firm_id, engagement_type
        )
        if not template:
            return []
        items = []
        for i, title in enumerate(template.items):
            item = QcChecklistItem(
                firm_id=firm_id,
                engagement_id=engagement_id,
                title=title,
                order=i,
                is_from_template=True,
            )
            db.add(item)
            items.append(item)
        db.commit()
        return items

═══════════════════════════════════════════════════════════════
STEP 5 — Create API router
═══════════════════════════════════════════════════════════════

Create new file: app/api/qc_checklists.py

router prefix: /qc-checklists
tags: ["QC Checklists"]

TEMPLATE ENDPOINTS — manager or above only:

    GET /qc-checklists/templates/
    Query param: include_inactive: bool = False
    Response: list[QcChecklistTemplateOut]

    POST /qc-checklists/templates/
    Body: QcChecklistTemplateCreate
    Response: QcChecklistTemplateOut, 201

    PATCH /qc-checklists/templates/{template_id}
    Body: QcChecklistTemplateUpdate
    Response: QcChecklistTemplateOut
    404 if not found

    DELETE /qc-checklists/templates/{template_id}
    Response: 204
    Logic: soft delete — set is_active=False

    POST /qc-checklists/templates/{template_id}/restore
    Response: QcChecklistTemplateOut
    Logic: restore soft-deleted template

ITEM ENDPOINTS — staff or above:

    GET /qc-checklists/items/?engagement_id={uuid}
    Response: list[QcChecklistItemOut]
    engagement_id is required

    POST /qc-checklists/items/
    Body: QcChecklistItemCreate
    Response: QcChecklistItemOut, 201
    Logic: verify engagement belongs to firm

    PATCH /qc-checklists/items/{item_id}/check
    Response: QcChecklistItemOut
    Logic: mark checked, set checked_by to current user id,
        set checked_at to now

    PATCH /qc-checklists/items/{item_id}/uncheck
    Response: QcChecklistItemOut
    Logic: clear checked_by and checked_at

    PATCH /qc-checklists/items/{item_id}
    Body: QcChecklistItemUpdate (title and order only)
    Response: QcChecklistItemOut

    DELETE /qc-checklists/items/{item_id}
    Response: 204
    Logic: hard delete — staff can delete items they added

Register in app/main.py:
    from app.api.qc_checklists import (
        router as qc_checklists_router
    )
    app.include_router(qc_checklists_router)

═══════════════════════════════════════════════════════════════
STEP 6 — Auto-populate on engagement creation
═══════════════════════════════════════════════════════════════

File: app/api/engagements.py

Find the POST endpoint that creates a new engagement.
After the engagement is created and committed, add:

    from app.crud.qc_checklist import populate_from_template

    if engagement.engagement_type:
        populate_from_template(
            db=db,
            firm_id=current_firm.id,
            engagement_id=engagement.id,
            engagement_type=engagement.engagement_type,
        )

This must run after db.commit() on the engagement creation
so the engagement.id exists. Do not wrap in try/except —
if population fails the engagement still exists, the checklist
just starts empty.

Also find the endpoint or service that creates engagements
from templates (UseTemplate flow). Apply the same
populate_from_template call there too, after the engagement
is committed.

═══════════════════════════════════════════════════════════════
STEP 7 — Migration
═══════════════════════════════════════════════════════════════

Do NOT use autogenerate — write a clean manual migration.

Create file:
migrations/versions/0034_add_qc_checklist_tables.py

    revision = '0034_add_qc_checklist_tables'
    down_revision = '0033_add_document_expiries_table'

    def upgrade():
        op.create_table(
            'qc_checklist_templates',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('firm_id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(200),
                nullable=False),
            sa.Column('engagement_type', sa.String(50),
                nullable=True),
            sa.Column('items', sa.JSON(), nullable=False,
                server_default='[]'),
            sa.Column('is_active', sa.Boolean(),
                nullable=False, server_default='true'),
            sa.Column('created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False),
            sa.Column('updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False),
            sa.ForeignKeyConstraint(['firm_id'],
                ['firms.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_qc_checklist_templates_firm_id',
            'qc_checklist_templates', ['firm_id']
        )

        op.create_table(
            'qc_checklist_items',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('firm_id', sa.UUID(), nullable=False),
            sa.Column('engagement_id', sa.UUID(),
                nullable=False),
            sa.Column('title', sa.String(500),
                nullable=False),
            sa.Column('is_checked', sa.Boolean(),
                nullable=False, server_default='false'),
            sa.Column('checked_by_id', sa.UUID(),
                nullable=True),
            sa.Column('checked_at',
                sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_from_template', sa.Boolean(),
                nullable=False, server_default='false'),
            sa.Column('order', sa.Integer(),
                nullable=False, server_default='0'),
            sa.Column('created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False),
            sa.ForeignKeyConstraint(['firm_id'],
                ['firms.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['engagement_id'],
                ['engagements.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['checked_by_id'],
                ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_qc_checklist_items_firm_id',
            'qc_checklist_items', ['firm_id']
        )
        op.create_index(
            'ix_qc_checklist_items_engagement_id',
            'qc_checklist_items', ['engagement_id']
        )

    def downgrade():
        op.drop_index('ix_qc_checklist_items_engagement_id',
            table_name='qc_checklist_items')
        op.drop_index('ix_qc_checklist_items_firm_id',
            table_name='qc_checklist_items')
        op.drop_table('qc_checklist_items')
        op.drop_index(
            'ix_qc_checklist_templates_firm_id',
            table_name='qc_checklist_templates')
        op.drop_table('qc_checklist_templates')

Then run:
    alembic upgrade head
    alembic current — confirm 0034 at head

═══════════════════════════════════════════════════════════════
STEP 8 — Frontend: QC Checklists tab in Templates page
═══════════════════════════════════════════════════════════════

File: frontend/src/app/(dashboard)/templates/page.tsx

1. Add 'qc_checklists' to the SUB_TABS array, before
   'deleted':
       { key: 'qc_checklists', label: 'QC Checklists' }

2. Add the render block alongside the others:
       {activeTab === 'qc_checklists' && (
           <QcChecklistTemplatesTab />
       )}

3. Import the new component:
       import QcChecklistTemplatesTab from
           '@/components/templates/QcChecklistTemplatesTab'

Create new file:
frontend/src/components/templates/QcChecklistTemplatesTab.tsx

This component manages QC checklist templates. Follow the
exact same visual pattern as the Engagement Templates tab.

LAYOUT:
- Toolbar: search input left, "+ New QC Checklist" button
  right (manager+ only)
- Template list: each template as a card row showing:
    name — 13px weight 500 brand color
    engagement_type — formatted label or "All engagement
      types" if null — 12px muted
    item count — "N items" — 11px muted
    Edit button and Delete button on hover (manager+ only)
- Empty state: "No QC checklist templates yet. Create one
  to standardize your review process."

CREATE/EDIT MODAL:
Fields:
- Template name — text input, required
- Engagement type — dropdown, same ENGAGEMENT_TYPES
  constant used in the engagement templates tab, plus
  an "All engagement types (manual only)" option that
  sets engagement_type to null
- Checklist items — dynamic list:
    Each item is a text input with a drag handle and
    a remove button
    "+ Add item" button appends a new empty input
    Items are stored as a JSON array of strings
- Save calls POST /qc-checklists/templates/ for create
  or PATCH /qc-checklists/templates/{id} for edit

DELETE:
- Soft delete — calls DELETE /qc-checklists/templates/{id}
- Confirmation modal before deleting
- Deleted templates move to the Deleted tab

Data fetching:
- On mount: GET /qc-checklists/templates/
- After create/edit/delete: invalidate and refetch

═══════════════════════════════════════════════════════════════
STEP 9 — Frontend: Deleted tab QC sub-tab
═══════════════════════════════════════════════════════════════

File: frontend/src/components/templates/DeletedTemplates.tsx

The Deleted tab currently has three internal sub-tabs:
Engagement Templates, Letter Templates, Tax Organizers.

Add a fourth internal sub-tab: QC Checklists

The QC Checklists deleted sub-tab:
- Fetches GET /qc-checklists/templates/?include_inactive=true
- Filters client-side to show only is_active=false templates
- Shows each deleted template with name, engagement_type,
  item count
- Restore button calls POST
  /qc-checklists/templates/{id}/restore
- Same visual pattern as the other deleted sub-tabs

═══════════════════════════════════════════════════════════════
STEP 10 — Frontend: QC Checklist tab on engagement detail
═══════════════════════════════════════════════════════════════

File: frontend/src/app/engagements/[id]/page.tsx

1. Add 'checklist' to the TABS array between tasks and
   documents:
       { key: 'checklist', label: 'QC Checklist' }

2. Add render block:
       {activeTab === 'checklist' && (
           <QcChecklistTab
               engagementId={engagementId}
               engagementStatus={engagement.status}
               onStatusChange={refetchEngagement}
           />
       )}

3. Import:
       import { QcChecklistTab } from
           '@/components/engagements/QcChecklistTab'

Create new file:
frontend/src/components/engagements/QcChecklistTab.tsx

LAYOUT:
- Section header "QC Checklist" with item count badge
  showing "N of M complete"
- Checklist items list:
    Each item row:
    - Checkbox left — clicking calls check/uncheck endpoint
    - Title text — strikethrough when checked, muted color
    - "Added from template" pill (10px, muted) if
      is_from_template is true
    - Checked by name + timestamp (11px muted) when checked
    - Delete button on hover for manually added items only
      (staff+ can delete their own, manager+ can delete any)
- Below the list: "+ Add item" text input inline
    Pressing Enter or clicking Add calls POST
    /qc-checklists/items/ with is_from_template=false
- Empty state: "No checklist items. Add one below or
  create a QC template for this engagement type in
  Templates."

SOFT WARNING on engagement completion:
The engagement detail page has a status dropdown or
complete button. Find where status is changed to
'completed' or 'complete'. Before the API call fires,
check if there are any unchecked items:

    const uncheckedCount = items.filter(
        i => !i.is_checked
    ).length

    if (uncheckedCount > 0) {
        const confirmed = window.confirm(
            `${uncheckedCount} checklist item${
                uncheckedCount > 1 ? 's are' : ' is'
            } not checked. Mark engagement as complete
            anyway?`
        )
        if (!confirmed) return
    }

If the engagement status change lives in a component
outside QcChecklistTab, pass the unchecked count up via
a callback or store it in a ref the parent can read.
Use whichever approach fits the existing pattern in
the engagement detail page.

Data fetching:
- On mount: GET /qc-checklists/items/?engagement_id={id}
- After check/uncheck/add/delete: optimistic UI where
  possible, refetch on error

═══════════════════════════════════════════════════════════════
STEP 11 — Restart and verify
═══════════════════════════════════════════════════════════════

On the server:
    git pull origin main
    alembic upgrade head
    alembic current — confirm 0034
    systemctl restart jammpx.service
    systemctl status jammpx.service
    journalctl -u jammpx.service -n 20 --no-pager