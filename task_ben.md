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

# Task: Add smooth word-by-word reveal animation to streaming Concierge responses

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "const \[streaming, setStreaming\]\|setMessages((prev) => \[...prev, { role: 'concierge'" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the streaming state declaration and the exact point where a new empty concierge message is pushed onto the messages array at the start of sendMessages, before any content streams in.

grep -n "const partial = assembleSSELines" -A 12 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the existing incremental setMessages call inside the while loop (added in commit f9f7def) that updates the last concierge message's content as each complete line arrives. This already correctly produces clean, complete lines with no mid-sentence corruption. This task only changes how that content is visually revealed, not how or when it arrives.

## WHAT IS WRONG

Confirmed via live testing: streaming responses currently update visually in large, instant jumps whenever a new complete line arrives from the backend, since each line can take a real, sometimes uneven amount of time to generate (especially for bullet-heavy content like the morning briefing, where each item is a separate line). The result feels staggered and unpolished, described as looking like "stepping stones" rather than a smooth, continuous reveal. The underlying text itself is correct and clean (already fixed in prior streaming work), this is purely a presentation-layer issue: content should appear to flow continuously even though it physically arrives from the network in irregular bursts.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Add new state to track how much of the streaming message's content has been visually revealed so far, separate from the actual backend-received content:

  const [revealedWordCount, setRevealedWordCount] = useState(0)
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

When a new concierge message is started at the beginning of sendMessages (the setMessages((prev) => [...prev, { role: 'concierge', content: '' }]) call), also reset the reveal state:

  setRevealedWordCount(0)

Add a useEffect that drives the reveal animation. It should watch the last message's content (the actual target text received so far) and animate revealedWordCount toward the target word count, one word at a time, on a short fixed interval, never exceeding the actual available word count, and stopping cleanly when streaming becomes false or the component unmounts:

  useEffect(() => {
    if (!streaming) return
    const lastMsg = messages[messages.length - 1]
    if (!lastMsg || lastMsg.role !== 'concierge') return
    const targetWordCount = lastMsg.content.split(/\s+/).filter(Boolean).length

    function tick() {
      setRevealedWordCount((prev) => {
        if (prev >= targetWordCount) return prev
        return prev + 1
      })
      revealTimerRef.current = setTimeout(tick, 35)
    }
    revealTimerRef.current = setTimeout(tick, 35)

    return () => {
      if (revealTimerRef.current) clearTimeout(revealTimerRef.current)
    }
  }, [streaming, messages])

When streaming ends (the post-loop block runs and sets the final authoritative message), also snap revealedWordCount to the full final word count so the rest of the message appears immediately rather than continuing to trickle in after the response is actually complete:

  setRevealedWordCount(Number.MAX_SAFE_INTEGER)

Add this line in the same place the final setMessages call happens after the while loop, right after parsedDraft and cleanContent are computed.

In the message rendering section (where ReactMarkdown currently renders msg.content directly), for the specific case of the last message while streaming is true, render only the revealed portion instead of the full content:

  {msg.content ? (
    <div className={...}>
      <ReactMarkdown ...>
        {streaming && i === messages.length - 1
          ? msg.content.split(/\s+/).filter(Boolean).slice(0, revealedWordCount).join(' ')
          : msg.content}
      </ReactMarkdown>
    </div>
  ) : ...}

This ensures only the currently-streaming message is affected by the word-level reveal, every other message (already complete, or from earlier in the conversation) renders its full content immediately and normally, with no animation delay.

Do not change assembleSSELines, the backend line-buffering logic, or anything in route.py. This is a frontend-only presentation change on top of content that is already correct. Do not reveal character-by-character; word-level reveal is required specifically to avoid rendering broken markdown tokens like an unclosed ** bold marker mid-reveal.

## VERIFY AFTER ACT

grep -n "revealedWordCount\|revealTimerRef" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: state, ref, the driving useEffect, the snap-to-end on stream completion, and the conditional slice in the render section are all present.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask a question that produces a bullet-heavy, multi-line response (e.g. the morning briefing, or any stalled-engagements-style list).
3. Confirm the response now appears to flow word by word continuously, rather than snapping in whole lines with visible pauses between them.
4. Confirm bold markdown (e.g. **Stalled engagements:**) never renders as literal broken asterisks mid-reveal, only ever appearing once the whole bolded phrase is revealed together.
5. Confirm once streaming finishes, any remaining unrevealed words appear immediately rather than continuing to trickle in after the response is actually done.
6. Regression check: scroll up to an earlier, already-completed message in the same conversation and confirm it renders fully and instantly, with no reveal animation applied to historical messages.

Report what you observe at steps 3 and 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: streaming Concierge responses now reveal word by word with a smooth animated pace instead of snapping in whole lines as they arrive from the network, while keeping the underlying content delivery and markdown safety unchanged"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.s