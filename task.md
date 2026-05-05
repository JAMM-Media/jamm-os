TASK: Make automation description expandable in AutomationsTab

FILE: frontend/src/components/settings/AutomationsTab.tsx

The RuleCard component truncates descriptions at 80 chars with 
no way to expand. Add an expand/collapse toggle.

CHANGE 1 — Add expanded state to RuleCard and make description 
toggleable.

Find:
function RuleCard({
  rule,
  section,
  isPending,
  onToggle,
}: {
  rule: AutomationRule
  section: 'active' | 'available'
  isPending: boolean
  onToggle: (rule: AutomationRule) => void
}) {
  const showBadge =
    section === 'active' && rule.is_enabled && DEFAULT_ON_PRESETS.has(rule.name)
  const truncated =
    rule.description.length > 80 ? rule.description.slice(0, 80) + '…' : rule.description
  const lastRun = rule.last_executed_at

Replace with:
function RuleCard({
  rule,
  section,
  isPending,
  onToggle,
}: {
  rule: AutomationRule
  section: 'active' | 'available'
  isPending: boolean
  onToggle: (rule: AutomationRule) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const showBadge =
    section === 'active' && rule.is_enabled && DEFAULT_ON_PRESETS.has(rule.name)
  const needsTruncation = rule.description.length > 80
  const truncated = needsTruncation && !expanded
    ? rule.description.slice(0, 80) + '…'
    : rule.description
  const lastRun = rule.last_executed_at

CHANGE 2 — Add useState to the imports at the top of the file.

Find:
  import { useState, useEffect, useCallback } from 'react'

This already exists — no change needed.

CHANGE 3 — Replace the static description span with a 
clickable one that expands when there is more content.

Find:
        <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">{truncated}</span>

Replace with:
        <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
          {truncated}
          {needsTruncation && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="ml-1 text-[11px] text-brand-light hover:underline focus:outline-none"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </span>

No other files need to be changed.