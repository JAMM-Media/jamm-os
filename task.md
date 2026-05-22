== STANDING RULES — ENFORCE ALWAYS ==

Project: JAMM PX
Backend: FastAPI + PostgreSQL on DigitalOcean droplet, Uvicorn + Gunicorn
Frontend: Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui
All backend files start with a path comment.
All frontend files start with a path comment.
Never use && to chain commands — run them sequentially.
Never modify the database schema without following the migration
procedure exactly.
Tenant isolation is absolute — every query scoped to firm_id.
Routers are thin — no business logic in routers ever.
Never use native_enum=True for enums — always use
sa.Enum(MyEnum, native_enum=False).

== MIGRATION PROCEDURE — FOLLOW EVERY TIME ==

1. alembic current
2. alembic revision --autogenerate -m "description"
3. Read the generated migration file in full
4. If it contains tables beyond what was just added, delete it
   and write a clean manual migration
5. alembic upgrade head
6. alembic current — confirm at head

== TASK: Automation Rule Editing — Edit Modal + Reset to Default ==

Allow firm owners and managers to edit the configurable fields
of any automation rule directly from the Settings > Automations
tab. Changes persist until edited again. A Reset to Default
button restores the original preset values. All 15 presets must
be covered.

Work through all steps in order. Do not skip ahead.

== STEP 1 — BACKEND: ADD default_actions COLUMN ==

The AutomationRule model needs one new column to store the
original preset values so Reset to Default always works.

File: app/models/automation_rule.py

Add this field to the AutomationRule class after the actions
field:

    default_actions: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )

File: app/services/automation_presets.py

In the _get_preset_rules() function, every preset dict already
has an "actions" key. For every preset, add a "default_actions"
key that is an exact copy of the "actions" value. This is the
snapshot of the original preset that never gets modified.

Example pattern for every preset:
    "actions": [ ... ],
    "default_actions": [ ... ],  # exact copy of actions above

Do this for all 15 presets.

Run the migration procedure now:
1. alembic current
2. alembic revision --autogenerate -m "add default_actions to
   automation_rules"
3. Read the generated file — confirm it only adds the
   default_actions column, nothing else
4. alembic upgrade head
5. alembic current — confirm at head

Then backfill existing rows so existing firms are not broken.
Run this SQL directly via psql or via a Python script using
SessionLocal — whichever is cleaner:

    UPDATE automation_rules
    SET default_actions = actions
    WHERE default_actions = '[]'::jsonb
    OR default_actions IS NULL;

== STEP 2 — BACKEND: ADD RESET ENDPOINT ==

File: app/api/automation_rules.py

Add one new endpoint after the existing toggle endpoint:

POST /automation-rules/{rule_id}/reset-to-default
- Requires manager_or_above role
- Tenant isolation: verify rule belongs to current_user.firm_id
- Logic: copy rule.default_actions into rule.actions, commit
- Returns the updated AutomationRuleOut
- If rule not found or wrong firm: 404
- If rule.default_actions is empty list: return 400 with detail
  "No default actions stored for this rule"

The existing PATCH /automation-rules/{rule_id} endpoint already
handles saving edits — confirm it accepts partial updates to the
actions field via the AutomationRuleUpdate schema. If
AutomationRuleUpdate does not include an actions field, add it
as Optional[list] = None.

File: app/schemas/automation_rule.py

Check AutomationRuleUpdate. If it does not have:
    actions: Optional[list] = None

Add it. Also add:
    default_actions: Optional[list] = None

to AutomationRuleOut so the frontend can read the defaults.

== STEP 3 — FRONTEND: EDIT MODAL COMPONENT ==

Create a new file:
frontend/src/components/settings/AutomationEditModal.tsx

This modal opens when the user clicks the Edit button on any
automation rule row in the Automations tab. It renders the
correct editable fields based on what that specific rule
contains in its actions JSON. It does not show fields that do
not apply to that rule.

MODAL STRUCTURE:
- Standard modal overlay: rgba(0,0,0,0.35)
- Modal background: #EDEEF0 light / #383838 dark
- Border-radius 10px, border 0.5px solid #C8CDD6
- Header: rule name (13px weight 500) left, X close button right
  Border-bottom 0.5px
- Body: scrollable, padding 14px 16px, max-height 60vh
- Footer: right-aligned buttons with 8px gap
  Left side of footer: "Reset to default" button — ghost style,
  #991B1B text color, on click calls the reset endpoint then
  closes modal and refreshes the rule list
  Right side: Cancel button (ghost) then Save button (#1F3148 bg
  white text)

FIELD RENDERING LOGIC:

The modal inspects rule.actions (array of action objects) and
renders editable fields based on what it finds. Render fields
in this order if present:

1. DELAY DAYS — render if any action in the actions array has
   config.delay_days defined
   - One number input per action that has delay_days
   - Label: "Reminder delay (days)" for send_email actions,
     "Escalation delay (days)" for send_notification actions
   - Min: 1, Max: 90
   - For Preset 12 (Invoice Overdue Escalating Sequence) there
     are three actions with delay_days — render all three with
     clear labels: "First reminder (days)", "Follow-up reminder
     (days)", "Owner escalation (days)"

2. EMAIL SUBJECT — render if any action has config.subject
   defined
   - One text input per action that has a subject
   - Label: "Email subject"
   - Max length 150 characters

3. EMAIL BODY — render if any action has config.body defined
   - One textarea per action that has a body
   - Label: "Email message"
   - Rows: 4, max length 1000 characters
   - Note: most existing presets use config.template not
     config.body — for these, render a textarea that writes
     to config.body as a custom override. Label it "Custom
     email message (overrides default template)" with helper
     text: "Leave blank to use the default template"

4. NOTIFICATION MESSAGE — render if any action has
   config.message defined
   - One text input per action that has a message
   - Label: "Notification message"
   - Max length 300 characters

5. TASK TITLES — render if any action has type create_task
   - Render an editable list: one text input per create_task
     action showing config.title
   - Label above the list: "Auto-created tasks"
   - Each row: text input (flex-1) + a red trash icon button
     to remove that action from the array entirely
   - Below the list: "+ Add task" button (ghost, brand blue)
     that appends a new create_task action object to the local
     state with an empty title:
     { type: "create_task", config: { title: "" }, order: N }
     where N is the current array length
   - Minimum 1 task must remain — disable the trash button
     when only 1 task action remains

6. INVOICE DEFAULTS — render if any action has type
   create_invoice
   - "Default line item description" — text input,
     config.line_items[0].description, max 200 chars
   - "Default unit price ($)" — number input,
     config.line_items[0].unit_price, min 0, step 0.01
   - "Days until invoice due" — number input,
     config.due_days_from_now, min 1, max 365
   - Only render these if config.line_items exists — Preset 14
     uses source: "time_entries" and has no line_items, so
     skip invoice defaults for that preset

7. ACKNOWLEDGMENT WINDOW — render if any action has
   config.acknowledgment_days defined
   - Number input, label "Acknowledgment window (days)"
   - Min 1, max 30

FORM STATE:
- On modal open: deep clone rule.actions into local state
- All edits mutate the local clone only — never the original
  until Save is clicked
- On Save: call PATCH /automation-rules/{rule.id} with body
  { actions: localActionsState }
  On success: show success toast "Automation updated", close
  modal, refresh the automations list
  On error: show error toast "Could not save — please try again"
  Do not close modal on error
- On Reset to Default: call POST
  /automation-rules/{rule.id}/reset-to-default
  On success: show success toast "Reset to default settings",
  close modal, refresh the automations list
  On error: show error toast "Could not reset — please try again"
- On Cancel or X: discard local state, close modal, no API call

FIELD STYLING — match existing Settings tab patterns:
- Label: 11px weight 500 #1F3148 light / #EDEEF0 dark
- Input/textarea: bg #F7F7F8 light / #2D2D2D dark
  border 0.5px solid #C8CDD6, focus border #4A7FA5
  border-radius 6px, height 36px single-line, auto textarea
- Helper text: 11px #6B7280, 4px below input
- Section divider between field groups: 0.5px solid #C8CDD6
  with 12px vertical margin

== STEP 4 — FRONTEND: WIRE EDIT BUTTON INTO AUTOMATIONS TAB ==

File: frontend/src/components/settings/AutomationsTab.tsx

Read this file first before making any changes.

Add the following to the existing AutomationsTab component:

1. Import AutomationEditModal from ./AutomationEditModal

2. Add state:
   const [editingRule, setEditingRule] =
     useState<AutomationRule | null>(null)

3. On each automation rule row, add an Edit button to the right
   of the toggle:
   - Ghost button, 12px, brand color text, "Edit" label
   - On click: setEditingRule(rule)
   - Only visible to firm_owner and manager roles — check the
     existing role pattern used in this file

4. Below the rule list, render:
   {editingRule && (
     <AutomationEditModal
       rule={editingRule}
       onClose={() => setEditingRule(null)}
       onSaved={() => {
         setEditingRule(null)
         queryClient.invalidateQueries({
           queryKey: ['automation-rules']
         })
       }}
     />
   )}

5. The AutomationEditModal receives these props:
   - rule: AutomationRuleOut
   - onClose: () => void
   - onSaved: () => void

== STEP 5 — VERIFY ==

1. List every file created or modified and what changed
2. Confirm the migration ran and alembic is at head
3. Confirm the reset endpoint exists in the router
4. Confirm AutomationRuleUpdate includes actions: Optional[list]
5. Confirm AutomationRuleOut includes default_actions
6. Confirm AutomationEditModal renders correctly for at least
   three different preset types:
   - A delay-days + email preset (Preset 1)
   - A task-list preset (Preset 9)
   - A multi-action escalating preset (Preset 12)
7. Print every file path modified

Do not restart services — Andrew will handle deployment.