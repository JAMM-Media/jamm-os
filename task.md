== STANDING RULES — ENFORCE ALWAYS ==

Project: JAMM PX
Backend: FastAPI + PostgreSQL on DigitalOcean droplet, Uvicorn + Gunicorn
Frontend: Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui
All backend files start with a path comment.
All frontend files start with a path comment.
Never use && to chain commands — run them sequentially.
No backend changes in this task — frontend only.
Tenant isolation is absolute — every query scoped to firm_id.

== TASK: Entity Linking in Firm Chat and Client Messages ==

Allow staff to link directly to any client, engagement, task,
or document from within any message compose box in the app.
Typing # or clicking a toolbar button opens a two-level
dropdown. Selecting a record inserts a clickable chip into
the message. Recipients click the chip and navigate directly
to that record.

This is a frontend-only build. All API endpoints needed
already exist. No backend changes, no migration, no restart.

Read these files in full before writing any code:

- frontend/src/components/firm-chat/MessageCompose.tsx
  (or wherever the firm chat compose box lives)
- frontend/src/components/firm-chat/ (list all files)
- frontend/src/app/firm-chat/ (list all files)
- Any client messaging compose component if separate from
  firm chat

== STEP 1 — AUDIT EXISTING COMPOSE BOXES ==

List every compose box in the application that sends messages:
1. Firm Chat channel message compose
2. Client messaging compose (staff side on client detail page)
3. Any other compose surfaces

For each one, identify:
- The file path
- Whether it uses a textarea or a contenteditable div
- How it currently handles submission
- Whether it already has a toolbar row below or above the
  textarea

Report findings before writing any code.

== STEP 2 — BUILD THE ENTITY LINK PICKER COMPONENT ==

Create a new file:
frontend/src/components/shared/EntityLinkPicker.tsx

This is a self-contained dropdown component used by any
compose box. It handles the full two-level selection flow
and calls back with the selected entity.

PROPS:
  interface EntityLinkPickerProps {
    anchorRef: React.RefObject<HTMLElement>
    onSelect: (link: EntityLink) => void
    onClose: () => void
  }

  interface EntityLink {
    entityType: 'client' | 'engagement' | 'task' | 'document'
    entityId: string
    label: string
    href: string
  }

BEHAVIOR:
- Renders as a floating dropdown positioned above the
  anchorRef element (above the toolbar, not below it —
  so it does not get clipped by the bottom of the viewport)
- First level: entity type selection
  Four rows: Clients, Engagements, Tasks, Documents
  Each row has an icon (Users, Briefcase, CheckSquare,
  FileText from lucide-react) and a label
  Clicking a row loads the second level for that type
- Second level: record selection within the chosen type
  Shows a search input at the top (autofocused)
  Below search: scrollable list of matching records
  Each row shows the record name and a subtle secondary
  label (client name for engagements and tasks, engagement
  name for tasks)
  Searching filters the list client-side after initial load
  Back arrow at top left returns to the first level

API CALLS — use the existing endpoints with these patterns:
  Clients:     GET /api/v1/clients/?limit=50
               display: client.display_name or client.name
               href: /clients/{id}
  Engagements: GET /api/v1/engagements/?limit=50
               display: engagement.name
               secondary: client name if available
               href: /engagements/{id}
  Tasks:       GET /api/v1/tasks/?limit=50
               display: task.title
               secondary: client name if available
               href: /tasks/{id}
  Documents:   GET /api/v1/documents/?limit=50
               display: document.name or file_name
               href: /documents/{id}

Load the list when the user selects an entity type (not
before). Show a small inline spinner while loading. Cache
the result for the lifetime of the picker so switching
back and forth does not re-fetch.

SEARCH:
- Filter client-side on the already-loaded list
- Match against the display label case-insensitively
- If the list is empty after filtering show:
  "No results for '[query]'"

DROPDOWN STYLING — match the existing Firm Chat patterns:
- Background: #EDEEF0 light / #383838 dark
- Border: 0.5px solid #C8CDD6 light / #484848 dark
- Border-radius: 8px
- Width: 280px fixed
- Max-height: 320px, overflow-y auto on the list
- Box-shadow: 0 4px 12px rgba(0,0,0,0.12)
- z-index: 100 (above everything)
- First level rows: 36px height, 12px 14px padding
  Icon 14px in #6B7280, label 13px #1F3148 dark/#EDEEF0
  Hover: #D5D8DE light / #2D2D2D dark background
- Second level header: back arrow + entity type label
  12px weight 500, 10px 14px padding, border-bottom 0.5px
- Search input: full width, 11px, 8px 12px padding
  border-bottom 0.5px, no border-radius, bg transparent
  placeholder "Search [entity type]..."
- Record rows: 36px min-height, 12px 14px padding
  Primary label 12px weight 500 #1F3148 / #EDEEF0
  Secondary label 11px #6B7280 / #9CA3AF, truncated
  Hover: same as first level rows
- Close on: Escape key, click outside the dropdown

== STEP 3 — BUILD THE ENTITY CHIP ==

Create a new file:
frontend/src/components/shared/EntityChip.tsx

This is the clickable chip that appears inside the message
after a link is selected.

PROPS:
  interface EntityChipProps {
    link: EntityLink
    onRemove?: () => void  // only shown in compose, not
                           // in rendered messages
  }

VISUAL SPEC:
- Inline-flex element, sits within the message text flow
- Background: #DBEAFE light / #1E3A5F dark
- Text: #1E40AF light / #93C5FD dark
- Border-radius: 4px
- Padding: 2px 6px
- Font: 11px weight 500
- Icon: 10px icon matching entity type, 3px gap before label
  client → Users icon
  engagement → Briefcase icon
  task → CheckSquare icon
  document → FileText icon
- In compose mode (onRemove provided): show a small × button
  on the right, 10px, same text color, on click calls
  onRemove
- In message display mode (no onRemove): entire chip is
  clickable, onClick calls router.push(link.href)
- Never wraps — white-space: nowrap, overflow: hidden,
  text-overflow: ellipsis, max-width: 200px

== STEP 4 — MESSAGE FORMAT AND STORAGE ==

Entity links need to survive being sent and re-rendered from
the database. The message body is stored as a plain string.

Use a simple inline syntax for encoding links in the stored
message body:

  [[entity:client:uuid:Display Name]]

Pattern: [[entity:{type}:{id}:{label}]]

When rendering a received message, parse this pattern with
a regex and replace each match with an EntityChip component
in display mode.

Create a new file:
frontend/src/lib/entityLinkParser.tsx

Export two functions:

1. serializeLinks(parts: MessagePart[]): string
   Takes an array of text strings and EntityLink objects
   and serializes to a single string with the [[entity:...]]
   syntax for storage.

   type MessagePart = string | EntityLink

2. parseMessage(body: string): React.ReactNode
   Takes a stored message string, finds all [[entity:...]]
   patterns, and returns a React node with EntityChip
   components for each link and plain text spans for
   everything else.

== STEP 5 — WIRE INTO COMPOSE BOXES ==

For each compose box identified in Step 1, make these
changes:

STATE CHANGES:
Add to the compose component:
  const [parts, setParts] = useState<MessagePart[]>([''])
  const [showPicker, setShowPicker] = useState(false)
  const toolbarRef = useRef<HTMLDivElement>(null)

The parts array is the source of truth for the message
content. It is an array alternating between strings and
EntityLink objects. The textarea displays the text-only
version for editing; chips are rendered as overlays or
inline in a contenteditable. Given that all existing
compose boxes use textarea elements, use the following
simpler approach:

SIMPLIFIED COMPOSE APPROACH FOR TEXTAREA:
Rather than converting to contenteditable (complex, risky),
keep the textarea for text input and render entity chips
as a visual preview row between the toolbar and the
textarea label. When an entity is selected:
- Append a placeholder token to the textarea value:
  [@client:Display Name] — visible in the textarea as text
- Store the full EntityLink separately in a links[] array
  keyed by the placeholder token
- On send: replace each placeholder token with the full
  [[entity:...]] syntax before submitting to the API
- In the preview row above the textarea: render EntityChip
  components for each linked entity so the sender can see
  what they linked and remove chips before sending

TOOLBAR ADDITION:
In the toolbar row of each compose box, add a link button:
- Position: left side of the toolbar, before any existing
  buttons
- Icon: Link icon from lucide-react, 14px, #6B7280
- Label: "Link record" — 11px text next to the icon
- On click: setShowPicker(true)
- Button style: flex items-center gap-1 px-2 py-1 rounded
  text-[11px] text-[#6B7280] hover:bg-[#D5D8DE]
  dark:hover:bg-[#2D2D2D] transition-colors

Also trigger the picker when the user types # in the
textarea:
- Add an onChange handler that detects a standalone #
  character (preceded by a space or at the start of input)
- When detected: remove the # from the textarea value and
  open the picker
- This is the power-user shortcut; the button is the
  primary discovery path

SUBMISSION:
Before calling the send API, serialize the message:
  const body = serializeLinks(parts)
  // or for the simplified textarea approach:
  // replace placeholder tokens with [[entity:...]] syntax

== STEP 6 — WIRE INTO MESSAGE RENDERING ==

For each place where received messages are rendered, import
parseMessage from entityLinkParser and wrap the message
body:

Instead of:
  <p>{message.body}</p>

Use:
  <p>{parseMessage(message.body)}</p>

Find all message rendering locations in:
- frontend/src/components/firm-chat/ (message feed)
- frontend/src/app/(app)/clients/[id]/ (client messages tab
  if it exists)

== STEP 7 — VERIFY ==

1. List every file created or modified
2. Confirm EntityLinkPicker renders two levels correctly
3. Confirm EntityChip renders in both compose and display
   modes
4. Confirm entityLinkParser serializes and parses the
   [[entity:...]] format correctly with a simple inline
   test — call serializeLinks and parseMessage with a
   sample and log the output
5. Confirm the # trigger works in the onChange handler
6. Confirm the Link record button appears in the toolbar
   of every compose box
7. Flag anything that requires manual testing in the browser
   that cannot be verified from code alone

No backend changes. No migration. No restart needed.
Push to git when complete — Vercel handles frontend deploy.