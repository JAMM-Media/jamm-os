# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK
cd /home/corby/jamm-os
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

---

# POST-TASK — run after task completes
find /home/corby/jamm-os/app/api/concierge/ -name "*.py" | sort
ls /home/corby/jamm-os/migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Feature: Automatic opening message on panel first open

Task: Replace hardcoded starter chips and canned responses with a model-generated opening
message that fires automatically when the panel opens for the first time. The model reads
firm_type from context and generates the appropriate greeting.

Three changes. Do them in order.

---

## Change 1: prompts.py -- add __OPEN__ sentinel handling

Task: Add an instruction telling the model how to handle the silent opening trigger.

VERIFY BEFORE ACT:
grep -n "EMPTY STATE" /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

Find the EMPTY STATE block and add this line at the very top of the block, before the
firm_type branching logic:

OLD:
EMPTY STATE — FIRST OPEN
When the messages array is empty and this is the firm's first interaction, check firm_type in the live firm context.

NEW:
EMPTY STATE — FIRST OPEN
If the user's message is exactly "__OPEN__", this is the automatic panel-open trigger. Do not treat it as a real question. Generate the appropriate opening message based on firm_type in the live firm context and do not echo or reference the trigger word. Strip __OPEN__ from all displayed output.

When the messages array is empty and this is the firm's first interaction, check firm_type in the live firm context.

Do not change anything else.

VERIFY AFTER ACT:
grep -n "__OPEN__" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm one result.

---

## Change 2: ConciergePanel.tsx -- fire opening message on first open

Task: Fire the __OPEN__ sentinel when the panel opens for the first time with no messages.
Remove STARTER_PROMPTS, HARDCODED_RESPONSES, STARTER_PROMPT_INSTRUCTIONS, and the
showStarters UI block.

VERIFY BEFORE ACT:
sed -n '32,50p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "showStarters\|STARTER_PROMPTS\|HARDCODED_RESPONSES" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -20

Paste before touching anything.

Make exactly four changes:

Change 2a -- remove the three constant blocks at the top of the file:
OLD:
const STARTER_PROMPTS = [
  'What should I set up first after signing up?',
  'How do I import my existing clients?',
  'How does the client portal work?',
]
const STARTER_PROMPT_INSTRUCTIONS: Record<string, string> = {
  'How do I import my existing clients?': 'Answer using a numbered markdown list. Each step on its own numbered line.',
  'How does the client portal work?': 'Answer using a numbered markdown list. Each step on its own numbered line.',
}
const HARDCODED_RESPONSES: Record<string, string> = {

Find the closing } of HARDCODED_RESPONSES and remove the entire block including all its content.
This block ends before the export function ConciergePanel line. Remove everything from
const STARTER_PROMPTS to the closing } of HARDCODED_RESPONSES.

Change 2b -- fire __OPEN__ on first panel open when no messages exist:
OLD:
  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      api.post('/concierge/trigger-check').then(() => fetchNotifications()).catch(() => fetchNotifications())
    }
  }, [isOpen, sendMessages, fetchNotifications])

NEW:
  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
      if (messages.length === 0) {
        sendMessages([{ role: 'user', content: '__OPEN__' }])
      }
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      api.post('/concierge/trigger-check').then(() => fetchNotifications()).catch(() => fetchNotifications())
    }
  }, [isOpen, sendMessages, fetchNotifications])

Change 2c -- remove the showStarters UI block:
OLD:
          {showStarters && messages.length === 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-[12px] text-[#6B7280] leading-[1.5]">
                Ask me anything about JAMM PX. Here are a few places to start:
              </p>
              {STARTER_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(prompt)}
                  className="text-left text-[13px] text-[#1F3148] dark:text-[#EDEEF0] bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[8px] px-3 py-2.5 hover:border-[#4A7FA5] hover:bg-[#F0F4F8] dark:hover:bg-[#333333] transition-colors leading-[1.5]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

NEW:
          {/* Opening message fires automatically via __OPEN__ sentinel on first open */}

Change 2d -- remove the hardcoded response check in handleSend:
Find this block inside handleSend:
OLD:
    const hardcoded = text ? HARDCODED_RESPONSES[text] : undefined

Find the full hardcoded response logic and remove it. The handleSend function should send
every message to the API without any hardcoded bypass.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "STARTER_PROMPTS\|HARDCODED_RESPONSES\|showStarters\|hardcoded" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
   Confirm zero results.
2. grep -n "__OPEN__" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
   Confirm one result in the useEffect.
3. cd /home/corby/jamm-os/frontend
4. npm run build -- zero TypeScript errors.
5. Restart the backend.
6. Browser test: open the Concierge panel. Confirm the model generates an opening message
   automatically. Confirm the firm type intake question appears since firm_type is null.