// path: frontend/src/lib/entityLinkParser.tsx
import React from 'react'
import { EntityChip } from '@/components/shared/EntityChip'
import type { EntityLink } from '@/components/shared/EntityLinkPicker'

export type MessagePart = string | EntityLink

const ENTITY_PATTERN = /\[\[entity:([^:]+):([^:]+):([^\]]+)\]\]/g

export function serializeLinks(parts: MessagePart[]): string {
  return parts
    .map((part) => {
      if (typeof part === 'string') return part
      return `[[entity:${part.entityType}:${part.entityId}:${part.label}]]`
    })
    .join('')
}

export function parseMessage(body: string): React.ReactNode {
  if (!body) return body

  // Check for any entity tokens; if none, return plain string
  if (!body.includes('[[entity:')) return body

  const nodes: React.ReactNode[] = []
  let last = 0
  let match: RegExpExecArray | null

  // Reset regex state
  ENTITY_PATTERN.lastIndex = 0

  while ((match = ENTITY_PATTERN.exec(body)) !== null) {
    if (match.index > last) {
      nodes.push(<span key={last}>{body.slice(last, match.index)}</span>)
    }
    const [, entityType, entityId, label] = match
    const validTypes = ['client', 'engagement', 'task', 'document'] as const
    type ValidType = typeof validTypes[number]
    const type = validTypes.includes(entityType as ValidType)
      ? (entityType as ValidType)
      : 'client'

    const link: EntityLink = {
      entityType: type,
      entityId,
      label,
      href: `/${type === 'client' ? 'clients' : type === 'engagement' ? 'engagements' : type === 'task' ? 'tasks' : 'documents'}/${entityId}`,
    }
    nodes.push(<EntityChip key={match.index} link={link} />)
    last = match.index + match[0].length
  }

  if (last < body.length) {
    nodes.push(<span key={last}>{body.slice(last)}</span>)
  }

  return <>{nodes}</>
}
