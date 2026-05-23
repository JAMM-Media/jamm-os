== STANDING RULES — ENFORCE ALWAYS ==

Project: JAMM PX
Backend: FastAPI + PostgreSQL on DigitalOcean droplet
Frontend: Next.js 14+ App Router, TypeScript, Tailwind CSS
All files start with a path comment.
All frontend files start with a path comment.
Never use && to chain commands — run them sequentially.
Tenant isolation is absolute — every query scoped to firm_id.
Routers are thin — no business logic in routers ever.
Never use native_enum=True for enums — always use
sa.Enum(MyEnum, native_enum=False).
TypeScript must pass clean before committing.

== TASK: Engagement Templates — Full Feature Build ==

Allow firms to save any engagement as a reusable template
and create new engagements from a template with one click.
Templates pre-populate engagement type, tasks, document
checklist, and assigned staff. This is a base product
feature — not an upsell.

Read these files before writing any code:
- app/models/engagement.py
- app/models/task.py
- app/schemas/engagement.py
- app/api/engagements.py
- frontend/src/app/(dashboard)/engagements/page.tsx
- frontend/src/app/clients/[id]/page.tsx

Report what fields exist on Engagement and Task models
before writing any code.

== PHASE 1 — BACKEND: ENGAGEMENT TEMPLATE MODEL ==

Read the Engagement model first. Then create a new model:

File: app/models/engagement_template.py

class EngagementTemplate(Base):
    __tablename__ = "engagement_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    engagement_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    estimated_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    # JSON array of task template objects:
    # [{ title, description, order }]
    task_templates: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    # JSON array of document request item strings:
    # ["W-2", "1099-INT", ...]
    document_checklist: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    # Internal notes shown to staff when using template
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    use_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    firm: Mapped["Firm"] = relationship(
        "Firm", back_populates="engagement_templates"
    )

Add to app/models/firm.py:
    engagement_templates: Mapped[list["EngagementTemplate"]] =
        relationship("EngagementTemplate",
        back_populates="firm",
        cascade="all, delete-orphan")

Add the import to app/models/__init__.py or wherever
models are imported for alembic to detect them.

Write the migration manually — chain from 0029:
File: migrations/versions/0030_add_engagement_templates.py

Do NOT run alembic upgrade head locally.

== PHASE 2 — BACKEND: SCHEMAS ==

File: app/schemas/engagement_template.py

class TaskTemplateItem(BaseModel):
    title: str
    description: Optional[str] = None
    order: int = 0

class EngagementTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    engagement_type: Optional[str] = None
    estimated_hours: Optional[float] = None
    task_templates: list[TaskTemplateItem] = []
    document_checklist: list[str] = []
    notes: Optional[str] = None

class EngagementTemplateCreate(EngagementTemplateBase):
    pass

class EngagementTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    engagement_type: Optional[str] = None
    estimated_hours: Optional[float] = None
    task_templates: Optional[list[TaskTemplateItem]] = None
    document_checklist: Optional[list[str]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class EngagementTemplateOut(EngagementTemplateBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    is_active: bool
    use_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

== PHASE 3 — BACKEND: CRUD ==

File: app/crud/engagement_template.py

Functions needed:
- list_templates(db, firm_id, active_only=True)
  Returns all templates for firm ordered by use_count
  desc then name asc
- get_template(db, template_id, firm_id)
  Returns single template or None
- create_template(db, template_in, firm_id)
  Creates and returns template
- update_template(db, template, payload)
  Updates and returns template
- delete_template(db, template)
  Soft delete — sets is_active=False
- increment_use_count(db, template_id, firm_id)
  Increments use_count by 1

== PHASE 4 — BACKEND: API ROUTER ==

File: app/api/engagement_templates.py

router = APIRouter(
    prefix="/engagement-templates",
    tags=["Engagement Templates"]
)

Endpoints:

GET / — list all active templates for firm
  require_staff_or_above
  Returns list[EngagementTemplateOut]

POST / — create a new template
  require_manager_or_above
  Body: EngagementTemplateCreate
  Returns EngagementTemplateOut, 201

GET /{template_id} — get single template
  require_staff_or_above
  Returns EngagementTemplateOut

PATCH /{template_id} — update template
  require_manager_or_above
  Body: EngagementTemplateUpdate
  Returns EngagementTemplateOut

DELETE /{template_id} — soft delete
  require_manager_or_above
  Sets is_active=False
  Returns { message: "Template deleted" }

POST /{template_id}/use — create engagement from template
  require_staff_or_above
  Body: {
    client_id: UUID,
    engagement_name: Optional[str],  # overrides template name
    assigned_staff_id: Optional[UUID],
    tax_year: Optional[int]
  }
  Logic:
  1. Get template, verify belongs to firm
  2. Create engagement using template fields:
     - name: payload.engagement_name or template.name
     - engagement_type: template.engagement_type
     - client_id: payload.client_id
     - assigned_staff_id: payload.assigned_staff_id
     - Use existing engagement creation logic
  3. For each item in template.task_templates:
     Create a Task linked to the engagement with:
     - title: task_template.title
     - description: task_template.description
     - client_id: engagement.client_id
     - engagement_id: engagement.id
     - firm_id: firm_id
     - order: task_template.order
  4. If template.document_checklist is not empty:
     Create a DocumentRequest linked to the engagement
     with items from template.document_checklist
     Use the existing document request creation pattern
  5. Increment template use_count
  6. Return { engagement_id, tasks_created, doc_request_created }

Register the router in app/main.py:
  from app.api.engagement_templates import router as
    engagement_templates_router
  app.include_router(engagement_templates_router,
    prefix="/api/v1")

== PHASE 5 — FRONTEND: TEMPLATES PAGE ==

Create: frontend/src/app/(dashboard)/templates/page.tsx

This is a new top-level page. Add it to the sidebar
between Engagements and Tasks.

File: frontend/src/components/layout/Sidebar.tsx
Add between Engagements and Tasks:
  { href: '/templates', label: 'Templates',
    icon: LayoutTemplate }
Import LayoutTemplate from lucide-react.

TEMPLATES PAGE LAYOUT:

Header row:
- Left: "Engagement Templates" — 20px weight 500
- Right: "+ New Template" button — manager+ only

Two sections:

SECTION 1 — TEMPLATE LIST:
Fetch from GET /engagement-templates/
Each template card:
- Template name — 13px weight 500
- Description — 12px muted, truncated to 2 lines
- Engagement type badge if set — small pill
- Task count — "X tasks" — 11px muted
- Doc checklist count — "X documents" — 11px muted
- Use count — "Used X times" — 11px muted
- Two action buttons (manager+ only):
  Edit (pencil icon) — opens edit modal
  Delete (trash icon) — confirm then soft delete
- "Use Template" button — available to all staff
  Opens the Use Template modal

EMPTY STATE:
"No templates yet. Create your first template to speed
up engagement creation."

SECTION 2 — CREATE/EDIT TEMPLATE MODAL:

Modal opens when "+ New Template" or Edit is clicked.

Fields:
1. Template name — required, text input
2. Description — optional, textarea 2 rows
3. Engagement type — dropdown with existing engagement
   types from the codebase enums
4. Estimated hours — optional, number input
5. Tasks section:
   - Label: "Default Tasks"
   - List of task title inputs with drag handle and
     remove button
   - "+ Add Task" button appends a new empty task row
   - Minimum 0 tasks
6. Document checklist section:
   - Label: "Document Checklist"
   - List of document name text inputs with remove button
   - "+ Add Document" button appends new empty row
   - Placeholder examples: "W-2", "1099-INT", "Prior year return"
7. Internal notes — optional, textarea 2 rows
   Helper text: "Only visible to staff, not clients"

Save button: POST / for new, PATCH /{id} for edit
On success: refresh template list, close modal

USE TEMPLATE MODAL:

Opens when "Use Template" is clicked on any template card.
Shows a preview of what will be created:
- Template name and description
- Engagement type
- List of tasks that will be created
- Document checklist items

Form fields:
1. Client — required, searchable dropdown
   GET /clients/?limit=100
   Search filters by name
2. Engagement name — optional, defaults to template name
   Text input, editable
3. Assign to staff — optional, dropdown
   GET /users/?limit=100, filter to staff roles
4. Tax year — optional, number input

"Create Engagement" button:
POST /engagement-templates/{id}/use
On success: show toast "Engagement created successfully"
with a "View Engagement" link that navigates to
/engagements/{engagement_id}
Close modal after 2 seconds or on link click.

== PHASE 6 — FRONTEND: SAVE AS TEMPLATE FROM EXISTING
ENGAGEMENT ==

File: frontend/src/app/(dashboard)/engagements/page.tsx
or the engagement detail page — read first to find the
right location.

Add a "Save as Template" option to each engagement row's
action menu (the ... menu or equivalent).

When clicked: open a modal pre-populated with:
- Template name: engagement name
- Engagement type: engagement's type
- Tasks: fetched from GET /tasks/?engagement_id={id}
  Pre-populate task titles from existing tasks
- Document checklist: fetched from document requests
  linked to this engagement if any

Staff can review and edit before saving. Then POST to
/engagement-templates/ to create the template.

Show toast "Template saved" on success.

== PHASE 7 — TYPESCRIPT AND GIT ==

Run: npx tsc --noEmit from the frontend directory.
Fix all TypeScript errors before committing.

Then:
git add .
git commit -m "add engagement templates — full feature build"
git push

== PHASE 8 — VERIFY ==

1. List every file created or modified
2. Confirm migration file chains from 0029
3. Confirm all 6 endpoints exist in the router
4. Confirm the sidebar shows Templates between
   Engagements and Tasks
5. Confirm Use Template modal creates engagement + tasks
   + document request
6. Confirm Save as Template works from engagement view
7. TypeScript passes clean
8. List what Andrew needs to run on the droplet