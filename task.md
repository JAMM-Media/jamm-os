STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix @mention bold rendering in firm chat messages

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM: renderBody tries to find @UUID in the message body, but the
body contains @Name (e.g. "@Sarah Chen"). The mentions array now contains
UUID strings, so indexOf never matches and mentions are never highlighted.

FIX — Two changes:

CHANGE 1: Update renderBody to accept an optional name lookup map so
it can match by name when UUIDs are stored.

Replace the entire renderBody function with:

function renderBody(body: string, mentions: string[], staffMap?: Map<string, string>): ReactNode {
  if (!body) return <>{body}</>
  // Build a list of name patterns to highlight
  // If staffMap provided, map UUIDs to names; otherwise use mentions as-is
  const namePatterns: string[] = mentions
    .map((m) => staffMap?.get(m) ?? m)
    .filter(Boolean)
  if (namePatterns.length === 0) {
    // Fallback: highlight any @word patterns in the body directly
    const parts: ReactNode[] = []
    const regex = /@(\S+)/g
    let last = 0
    let match
    let found = false
    while ((match = regex.exec(body)) !== null) {
      found = true
      if (match.index > last) parts.push(<span key={last}>{body.slice(last, match.index)}</span>)
      parts.push(
        <span key={match.index} className="bg-status-blue text-status-blue-text rounded px-1 font-medium">
          {match[0]}
        </span>
      )
      last = match.index + match[0].length
    }
    if (last < body.length) parts.push(<span key={last}>{body.slice(last)}</span>)
    return found ? <>{parts}</> : <>{body}</>
  }
  const parts: ReactNode[] = []
  let remaining = body
  let key = 0
  let foundAny = false
  for (const name of namePatterns) {
    const pattern = `@${name}`
    const idx = remaining.indexOf(pattern)
    if (idx === -1) continue
    foundAny = true
    if (idx > 0) parts.push(<span key={key++}>{remaining.slice(0, idx)}</span>)
    parts.push(
      <span
        key={key++}
        className="bg-status-blue text-status-blue-text rounded px-1 font-medium"
      >
        {pattern}
      </span>
    )
    remaining = remaining.slice(idx + pattern.length)
  }
  if (remaining.length > 0) parts.push(<span key={key++}>{remaining}</span>)
  if (!foundAny) return <>{body}</>
  return <>{parts}<>
}

CHANGE 2: Build a staffMap from staffList and pass it to renderBody.

Find where staffList is used — there is a useMemo or direct reference.
Add this after the senderIndexMap useMemo:

  const staffMap = useMemo(() => {
    const map = new Map<string, string>()
    staffList.forEach((s) => map.set(s.id, s.name))
    return map
  }, [staffList])

CHANGE 3: Update both renderBody call sites to pass staffMap.

Find the two places renderBody is called:
  {renderBody(msg.body, msg.mentions)}

Change both to:
  {renderBody(msg.body, msg.mentions, staffMap)}

After making changes show the updated renderBody function signature
and both call sites.