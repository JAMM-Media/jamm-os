// path: frontend/src/components/shared/EntityChip.tsx
'use client'

import { useRouter } from 'next/navigation'
import { Users, Briefcase, CheckSquare, FileText, X } from 'lucide-react'
import type { EntityLink } from './EntityLinkPicker'

interface EntityChipProps {
  link: EntityLink
  onRemove?: () => void
}

const ICON_MAP: Record<EntityLink['entityType'], React.ReactNode> = {
  client: <Users size={10} />,
  engagement: <Briefcase size={10} />,
  task: <CheckSquare size={10} />,
  document: <FileText size={10} />,
}

export function EntityChip({ link, onRemove }: EntityChipProps) {
  const router = useRouter()

  const handleClick = () => {
    if (!onRemove) {
      router.push(link.href)
    }
  }

  return (
    <span
      onClick={onRemove ? undefined : handleClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
        background: 'var(--chip-bg)',
        color: 'var(--chip-text)',
        borderRadius: 4,
        padding: '2px 6px',
        fontSize: 11,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        maxWidth: 200,
        cursor: onRemove ? 'default' : 'pointer',
        flexShrink: 0,
      }}
      className={[
        '[--chip-bg:#DBEAFE] [--chip-text:#1E40AF]',
        'dark:[--chip-bg:#1E3A5F] dark:[--chip-text:#93C5FD]',
      ].join(' ')}
      title={link.label}
    >
      <span className="flex-shrink-0">{ICON_MAP[link.entityType]}</span>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{link.label}</span>
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          style={{
            fontSize: 10,
            color: 'var(--chip-text)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          <X size={10} />
        </button>
      )}
    </span>
  )
}
