STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix @mention rendering — scan body directly for @Name patterns

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM: renderBody relies on msg.mentions (UUID array) to find and
highlight @names. But if the server returns empty mentions, or the
staffMap lookup fails, nothing gets highlighted.

The body text already contains the @Name text directly (e.g. "@Sarah Chen").
The most reliable approach is to scan the body for @Name patterns that
match any staff member name, regardless of the mentions array.

CHANGE 1: Update renderBody to always scan the body for staff name
patterns when staffMap is provided, ignoring the mentions array entirely:

Replace the entire renderBody function with:

function renderBody(body: string, _mentions: string[], staffMap?: Map<string, string>): ReactNode {
  if (!body) return <>{body}</>

  // Build set of known staff names for matching
  const staffNames = staffMap ? Array.from(staffMap.values()) : []

  // Find all @Name occurrences in the body that match a staff name
  // Sort by length descending so "Sarah Chen" matches before "Sarah"
  const sortedNames = [...staffNames].sort((a, b) => b.length - a.length)

  if (sortedNames.length === 0) {
    // Fallback: highlight any @word in body
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

  // Build regex that matches @Name for any known staff name
  const escaped = sortedNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`@(${escaped.join('|')})(?=\\s|$|[^\\w])`, 'gi')

  const parts: ReactNode[] = []
  let last = 0
  let match
  let found = false
  while ((match = pattern.exec(body)) !== null) {
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

Note: the _mentions parameter is kept for API compatibility but ignored.
The staffMap drives all matching.

After making the change show the updated renderBody function signature.