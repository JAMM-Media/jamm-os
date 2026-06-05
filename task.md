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

# Section 3 - The task

TASK: Polish endpoint for grammar and artifact correction

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before polish endpoint"

VERIFY BEFORE ACT:
grep -n "def concierge_chat\|guard_api_key\|filter_output" /home/corby/jamm-os/app/api/concierge/route.py | head -10
grep -n "filterOutput\|normalizeText\|filteredAssembled" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -10
Paste both before touching anything.

---

Change 1: Add POST /concierge/polish endpoint to route.py

Find exactly:
@router.get("/clients/resolve")

Add this block immediately before it:

class PolishRequest(BaseModel):
    text: str

@router.post("/polish")
def polish_text(
    body: PolishRequest,
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    if not body.text or not body.text.strip():
        return {"text": body.text}

    settings = get_settings()
    polish_api_key = settings.ANTHROPIC_API_KEY
    if not polish_api_key:
        return {"text": body.text}

    try:
        polish_client = anthropic.Anthropic(api_key=polish_api_key)
        response = polish_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system="""You are a text cleanup utility for a software assistant.
Your only job is to fix mechanical text artifacts in the input.

Fix these specific issues:
- Spaces before punctuation: "word ." becomes "word."
- Split compound words: "magic -link" becomes "magic-link", "book keeping" becomes "bookkeeping", "Quick Books" becomes "QuickBooks", "on boarding" becomes "onboarding", "Auto pilot" becomes "Autopilot"
- Split IRS form numbers: "8 821" becomes "8821", "2 848" becomes "2848", "1 040" becomes "1040", "1 120" becomes "1120", "1 065" becomes "1065", "W -2" becomes "W-2", "W -9" becomes "W-9"
- Double spaces anywhere in the text
- Rogue markdown artifacts like "** " or " **" with spaces inside

Do not change any words, meaning, structure, or formatting.
Do not add or remove sentences.
Do not change capitalization except to fix clearly broken cases.
Return only the corrected text. No explanation. No preamble. No commentary.""",
            messages=[{"role": "user", "content": body.text}],
        )
        cleaned = response.content[0].text.strip()
        return {"text": cleaned}
    except Exception as e:
        logger.warning(f"Polish endpoint failed for firm {current_firm.id}: {e}")
        return {"text": body.text}

---

Change 2: Call polish endpoint from ConciergePanel.tsx after streaming completes

The polish call replaces the normalizeText function entirely.
normalizeText was a regex workaround -- the polish endpoint is the system fix.

Find exactly:
        const filteredAssembled = filterOutput(assembled)

Replace with:
        let polishedAssembled = assembled
        try {
          const polishRes = await api.post('/concierge/polish', { text: assembled })
          if (polishRes.data?.text) {
            polishedAssembled = polishRes.data.text
          }
        } catch {
          // non-fatal -- fall back to raw assembled text
        }
        const filteredAssembled = filterOutput(polishedAssembled)

Then remove the normalizeText function and its call inside filterOutput entirely.

Find exactly:
  function filterOutput(text: string): string {
    // Normalize streaming artifacts before any other checks
    text = normalizeText(text)

    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g

Replace with:
  function filterOutput(text: string): string {
    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g

Then find and delete the entire normalizeText function -- from the line:
  function normalizeText(text: string): string {
to its closing brace.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "polish\|normalizeText\|polishedAssembled" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
   Confirm polish and polishedAssembled appear.
   Confirm normalizeText does NOT appear -- zero results.
2. grep -n "def polish_text\|PolishRequest\|polish_api_key" /home/corby/jamm-os/app/api/concierge/route.py
   Confirm all three appear.
3. python3 -c "from app.api.concierge.route import router; print('OK')"
   Must pass.
4. cd /home/corby/jamm-os/frontend
5. npm run build
   Zero TypeScript errors required before stopping.
6. Restart the backend.

Browser tests:
Test 1 -- Form numbers:
  Type: "what is the difference between an 8821 and a 2848"
  Confirm 8821 and 2848 with no spaces.

Test 2 -- Compound terms:
  Type: "how do I send a magic-link to a client"
  Confirm "magic-link" and "Magic-Link" appear correctly.

Test 3 -- Punctuation:
  Type: "how do I create an engagement"
  Confirm no spaces before periods or commas anywhere in the response.

Test 4 -- Normal flow:
  Type: "how do I add a client"
  Confirm clean response, no artifacts.