// path: frontend/src/app/(dashboard)/firm-chat/page.tsx
'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import type { ReactNode } from 'react'
import { useChannels } from '@/components/firm-chat/useChannels'
import { useMessages } from '@/components/firm-chat/useMessages'
import { MessageSquare, MoreHorizontal, Users, X, UserMinus, Link, Paperclip, Loader2, Download } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { firmChatApi, type ChannelMember } from '@/lib/api/firmChat'
import { useAuth } from '@/lib/hooks/useAuth'
import { EntityLinkPicker, type EntityLink } from '@/components/shared/EntityLinkPicker'
import { EntityChip } from '@/components/shared/EntityChip'

// ─── Types ────────────────────────────────────────────────────────────────────

interface StaffMember {
  id: string
  name: string
  initials: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getUserRole(): string {
  if (typeof window === 'undefined') return 'staff'
  const token = localStorage.getItem('access_token')
  if (!token) return 'staff'
  try {
    const payload = JSON.parse(atob(token.split('.')[1])) as Record<string, unknown>
    return typeof payload.role === 'string' ? payload.role : 'staff'
  } catch {
    return 'staff'
  }
}

const AVATAR_COLORS = ['#1F3148', '#3A6A94', '#4A7FA5', '#7DA3C4'] as const

function getAvatarColor(index: number): string {
  return AVATAR_COLORS[index % 4]
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatDateLabel(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function isSameDay(a: string, b: string): boolean {
  return new Date(a).toDateString() === new Date(b).toDateString()
}

function isSameSenderWithin5Min(
  a: { senderId: string; createdAt: string },
  b: { senderId: string; createdAt: string }
): boolean {
  if (a.senderId !== b.senderId) return false
  return Math.abs(new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()) < 5 * 60 * 1000
}

const VALID_ENTITY_TYPES = ['client', 'engagement', 'task', 'document'] as const
type ValidEntityType = typeof VALID_ENTITY_TYPES[number]

function renderBody(body: string, _mentions: string[], staffMap?: Map<string, string>): ReactNode {
  if (!body) return <>{body}</>

  // Segment body by [[entity:...]] tokens first
  const entityRegex = /\[\[entity:([^:]+):([^:]+):([^\]]+)\]\]/g
  type Segment = { text: string } | { entityType: string; entityId: string; label: string }
  const segments: Segment[] = []
  let last = 0
  let em: RegExpExecArray | null
  entityRegex.lastIndex = 0
  while ((em = entityRegex.exec(body)) !== null) {
    if (em.index > last) segments.push({ text: body.slice(last, em.index) })
    segments.push({ entityType: em[1], entityId: em[2], label: em[3] })
    last = em.index + em[0].length
  }
  if (last < body.length) segments.push({ text: body.slice(last) })

  // Build @mention pattern from staff map
  const staffNames = staffMap ? Array.from(staffMap.values()) : []
  const sortedNames = [...staffNames].sort((a, b) => b.length - a.length)
  let mentionPattern: RegExp | null = null
  if (sortedNames.length > 0) {
    const escaped = sortedNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    mentionPattern = new RegExp(`@(${escaped.join('|')})(?=\\s|$|[^\\w])`, 'gi')
  }

  function highlightMentions(text: string, keyPrefix: string): ReactNode[] {
    const parts: ReactNode[] = []
    const regex = mentionPattern ?? /@(\S+)/g
    regex.lastIndex = 0
    let pos = 0
    let m: RegExpExecArray | null
    while ((m = regex.exec(text)) !== null) {
      if (m.index > pos) parts.push(<span key={`${keyPrefix}-${pos}`}>{text.slice(pos, m.index)}</span>)
      parts.push(
        <span key={`${keyPrefix}-m${m.index}`} className="font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
          {m[1]}
        </span>
      )
      pos = m.index + m[0].length
    }
    if (pos < text.length) parts.push(<span key={`${keyPrefix}-e${pos}`}>{text.slice(pos)}</span>)
    return parts.length > 0 ? parts : [<span key={keyPrefix}>{text}</span>]
  }

  const nodes: ReactNode[] = []
  segments.forEach((seg, i) => {
    if ('text' in seg) {
      highlightMentions(seg.text, `t${i}`).forEach((n) => nodes.push(n))
    } else {
      const type: ValidEntityType = VALID_ENTITY_TYPES.includes(seg.entityType as ValidEntityType)
        ? (seg.entityType as ValidEntityType)
        : 'client'
      const link: EntityLink = {
        entityType: type,
        entityId: seg.entityId,
        label: seg.label,
        href: `/${type === 'client' ? 'clients' : type === 'engagement' ? 'engagements' : type === 'task' ? 'tasks' : 'documents'}/${seg.entityId}`,
      }
      nodes.push(<EntityChip key={`e${i}`} link={link} />)
    }
  })

  return <>{nodes}</>
}

function getMentionQuery(value: string, cursor: number): string | null {
  const before = value.slice(0, cursor)
  const lastAt = before.lastIndexOf('@')
  if (lastAt === -1) return null
  const afterAt = before.slice(lastAt + 1)
  // Allow spaces within the query so full names like "Sarah Chen" work
  // But stop if there are two consecutive spaces or a newline
  if (/\n/.test(afterAt) || /\s{2}/.test(afterAt)) return null
  return afterAt
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function FirmChatPage() {
  const {
    channels,
    isLoading: channelsLoading,
    createChannel,
    deleteChannel,
    renameChannel,
    markChannelRead,
  } = useChannels()

  const [activeChannelId, setActiveChannelId] = useState<string>('')
  const { messages, isLoading: messagesLoading, sendMessage } = useMessages(activeChannelId)

  // User role
  const { user } = useAuth()
  const isFirmOwner = user?.role === 'firm_owner' || user?.role === 'manager'

  // Active channel object
  const activeChannel = channels.find((ch) => ch.id === activeChannelId)

  // Auto-select first channel
  useEffect(() => {
    if (!activeChannelId && channels.length > 0) {
      setActiveChannelId(channels[0].id)
    }
  }, [activeChannelId, channels])

  // ─── Channel modals ──────────────────────────────────────────────────────
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createChannelName, setCreateChannelName] = useState('')

  const [showRenameModal, setShowRenameModal] = useState(false)
  const [renameChannelId, setRenameChannelId] = useState('')
  const [renameChannelNameInput, setRenameChannelNameInput] = useState('')

  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteChannelId, setDeleteChannelId] = useState('')
  const [deleteChannelDisplayName, setDeleteChannelDisplayName] = useState('')

  // ─── Channel dropdown ────────────────────────────────────────────────────
  const [showMembersModal, setShowMembersModal] = useState(false)
  const [membersChannelId, setMembersChannelId] = useState('')
  const [channelMembers, setChannelMembers] = useState<ChannelMember[]>([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [addMemberSearch, setAddMemberSearch] = useState('')
  const [addMemberLoading, setAddMemberLoading] = useState(false)
  const [memberSearchResults, setMemberSearchResults] = useState<StaffMember[]>([])
  const [memberSearchLoading, setMemberSearchLoading] = useState(false)
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null)
  const [hoveredChannelId, setHoveredChannelId] = useState<string | null>(null)

  useEffect(() => {
    if (!openDropdownId) return
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && dropdownRef.current.contains(e.target as Node)) return
      setOpenDropdownId(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [openDropdownId])

  // ─── Compose box ─────────────────────────────────────────────────────────
  const [composeValue, setComposeValue] = useState('')
  const [composeMentions, setComposeMentions] = useState<string[]>([])
  const [composeMentionIds, setComposeMentionIds] = useState<string[]>([])
  const [linkedEntities, setLinkedEntities] = useState<Map<string, EntityLink>>(new Map())
  const [showPicker, setShowPicker] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [pendingFileKey, setPendingFileKey] = useState<string | null>(null)
  const [fileUploading, setFileUploading] = useState(false)
  const [sendHint, setSendHint] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const toolbarRef = useRef<HTMLDivElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ─── @mention popover ────────────────────────────────────────────────────
  const [showMentionPopover, setShowMentionPopover] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const [staffList, setStaffList] = useState<StaffMember[]>([])
  const [mentionIndex, setMentionIndex] = useState(0)

  useEffect(() => {
    if (staffList.length === 0) {
      api.get('/users/').then((res) => {
        const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
        setStaffList(items.map((u: Record<string, unknown>) => ({
          id: String(u.id),
          name: String(u.full_name ?? u.name ?? ''),
          initials: String(u.full_name ?? u.name ?? '')
            .split(' ')
            .map((p: string) => p[0] ?? '')
            .join('')
            .slice(0, 2)
            .toUpperCase(),
        })))
      }).catch(() => {})
    }
  }, [staffList.length])

  const filteredStaff = staffList.filter((s) =>
    s.name.toLowerCase().includes(mentionQuery.trim().toLowerCase())
  )

  // ─── Messages scroll ─────────────────────────────────────────────────────
  const messagesEndRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ─── Avatar color map ────────────────────────────────────────────────────
  const senderIndexMap = useMemo(() => {
    const map = new Map<string, number>()
    messages.forEach((msg) => {
      if (!map.has(msg.senderId)) map.set(msg.senderId, map.size)
    })
    return map
  }, [messages])

  const getSenderIndex = useCallback(
    (senderId: string) => senderIndexMap.get(senderId) ?? 0,
    [senderIndexMap]
  )

  const staffMap = useMemo(() => {
    const map = new Map<string, string>()
    staffList.forEach((s) => map.set(s.id, s.name))
    return map
  }, [staffList])

  // ─── Handlers ────────────────────────────────────────────────────────────

  const handleSelectChannel = (channelId: string) => {
    setActiveChannelId(channelId)
    markChannelRead(channelId)
    setOpenDropdownId(null)
    setComposeValue('')
    setComposeMentions([])
    setComposeMentionIds([])
    setLinkedEntities(new Map())
    setShowPicker(false)
    setShowMentionPopover(false)
    setPendingFile(null)
    setPendingFileKey(null)
  }

  const handleComposeChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    const ta = e.currentTarget
    const cursor = ta.selectionStart

    // Detect standalone # to open entity picker
    if (
      cursor > 0 &&
      value[cursor - 1] === '#' &&
      (cursor === 1 || value[cursor - 2] === ' ' || value[cursor - 2] === '\n')
    ) {
      const newValue = value.slice(0, cursor - 1) + value.slice(cursor)
      setComposeValue(newValue)
      setShowPicker(true)
      setShowMentionPopover(false)
      ta.style.height = 'auto'
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
      return
    }

    setComposeValue(value)
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
    const query = getMentionQuery(value, cursor)
    if (query !== null) {
      setMentionQuery(query)
      setShowMentionPopover(true)
      setMentionIndex(0)
    } else {
      setShowMentionPopover(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showMentionPopover && filteredStaff.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setMentionIndex((prev) => (prev + 1) % filteredStaff.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setMentionIndex((prev) => (prev - 1 + filteredStaff.length) % filteredStaff.length)
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        handleMentionSelect(filteredStaff[mentionIndex])
        return
      }
      if (e.key === 'Escape') {
        setShowMentionPopover(false)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleEntitySelect = (link: EntityLink) => {
    const token = `[@${link.entityType}:${link.entityId}:${link.label}]`
    setComposeValue((prev) => prev + token + ' ')
    setLinkedEntities((prev) => new Map(prev).set(token, link))
    setShowPicker(false)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  const handleEntityRemove = (token: string) => {
    setComposeValue((prev) => prev.replace(token, '').replace(/\s{2,}/g, ' ').trim())
    setLinkedEntities((prev) => {
      const next = new Map(prev)
      next.delete(token)
      return next
    })
  }

  const handleSend = () => {
    if (fileUploading) {
      setSendHint(true)
      setTimeout(() => setSendHint(false), 3000)
      return
    }
    if (!composeValue.trim() || !activeChannelId) return
    let body = composeValue.trim()
    linkedEntities.forEach((link, token) => {
      body = body.split(token).join(`[[entity:${link.entityType}:${link.entityId}:${link.label}]]`)
    })
    sendMessage(
      body,
      composeMentionIds,
      pendingFileKey
        ? {
            attachment_key: pendingFileKey,
            attachment_name: pendingFile?.name ?? null,
            attachment_size: pendingFile?.size ?? null,
            attachment_type: pendingFile?.type ?? null,
          }
        : undefined
    )
    setComposeValue('')
    setComposeMentions([])
    setComposeMentionIds([])
    setLinkedEntities(new Map())
    setShowPicker(false)
    setShowMentionPopover(false)
    setPendingFile(null)
    setPendingFileKey(null)
    if (textareaRef.current) textareaRef.current.style.height = '40px'
  }

  const handleMentionSelect = (staff: StaffMember) => {
    const cursor = textareaRef.current?.selectionStart ?? composeValue.length
    const beforeCursor = composeValue.slice(0, cursor)
    const lastAt = beforeCursor.lastIndexOf('@')
    if (lastAt !== -1) {
      const before = composeValue.slice(0, lastAt)
      // Skip past everything the user typed after @ (the partial query)
      const after = composeValue.slice(cursor)
      setComposeValue(`${before}@${staff.name} ${after}`)
      setComposeMentions((prev) => [...prev, staff.name])
      setComposeMentionIds((prev) => [...prev, staff.id])
    }
    setShowMentionPopover(false)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 26214400) {
      toast.error('File must be under 25MB')
      return
    }
    setFileUploading(true)
    setPendingFile(file)
    try {
      const { data } = await api.post(
        `/firm-chat/channels/${activeChannelId}/upload-url`,
        { file_name: file.name, file_type: file.type, file_size: file.size }
      )
      await fetch(data.upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type },
      })
      setPendingFileKey(data.key)
    } catch {
      toast.error('File upload failed — please try again')
      setPendingFile(null)
      setPendingFileKey(null)
    } finally {
      setFileUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDownloadAttachment(message: { id: string }) {
    try {
      const { data } = await api.get(`/firm-chat/messages/${message.id}/attachment-url`)
      window.open(data.download_url, '_blank')
    } catch {
      toast.error('Could not load attachment')
    }
  }

  const handleCreateChannel = () => {
    const name = createChannelName.trim().toLowerCase().replace(/\s+/g, '-')
    if (!name) return
    createChannel(name)
    setShowCreateModal(false)
    setCreateChannelName('')
  }

  const handleRenameChannel = () => {
    const name = renameChannelNameInput.trim().toLowerCase().replace(/\s+/g, '-')
    if (!name) return
    renameChannel(renameChannelId, name)
    setShowRenameModal(false)
  }

  const handleDeleteChannel = () => {
    deleteChannel(deleteChannelId)
    if (activeChannelId === deleteChannelId) setActiveChannelId('')
    setShowDeleteModal(false)
  }

  const openRenameModal = (channelId: string, currentName: string) => {
    setRenameChannelId(channelId)
    setRenameChannelNameInput(currentName)
    setShowRenameModal(true)
    setOpenDropdownId(null)
  }

  const openDeleteModal = (channelId: string, channelName: string) => {
    setDeleteChannelId(channelId)
    setDeleteChannelDisplayName(channelName)
    setShowDeleteModal(true)
    setOpenDropdownId(null)
  }

  const openMembersModal = async (channelId: string) => {
    setMembersChannelId(channelId)
    setShowMembersModal(true)
    setOpenDropdownId(null)
    setAddMemberSearch('')
    setMembersLoading(true)
    try {
      const members = await firmChatApi.listMembers(channelId)
      setChannelMembers(members)
    } catch {
      setChannelMembers([])
    } finally {
      setMembersLoading(false)
    }
    // Fetch staff list for member search
    if (memberSearchResults.length === 0) {
      setMemberSearchLoading(true)
      api.get('/users/').then((res) => {
        const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
        setMemberSearchResults(items.map((u: Record<string, unknown>) => ({
          id: String(u.id),
          name: String(u.full_name ?? u.name ?? ''),
          initials: String(u.full_name ?? u.name ?? '').split(' ').map((p: string) => p[0]).join('').slice(0, 2).toUpperCase(),
        })))
      }).catch(() => {}).finally(() => setMemberSearchLoading(false))
    }
  }

  const handleAddMember = async (userId: string) => {
    if (!membersChannelId) return
    setAddMemberLoading(true)
    try {
      const member = await firmChatApi.addMember(membersChannelId, userId)
      setChannelMembers((prev) => [...prev, member])
      setAddMemberSearch('')
    } catch {
      // silently fail — member may already exist
    } finally {
      setAddMemberLoading(false)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    if (!membersChannelId) return
    try {
      await firmChatApi.removeMember(membersChannelId, userId)
      setChannelMembers((prev) => prev.filter((m) => m.userId !== userId))
    } catch {
      // silently fail
    }
  }

  // ─── Message rendering ───────────────────────────────────────────────────

  const renderMessages = (): ReactNode => {
    if (messagesLoading) {
      return (
        <div className="space-y-4 p-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex gap-3 items-start">
              <div className="w-7 h-7 rounded-full bg-[#D5D8DE] dark:bg-[#444444] flex-shrink-0" />
              <div className="space-y-2 flex-1">
                <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-2/5" />
                <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-3/4" />
              </div>
            </div>
          ))}
        </div>
      )
    }

    if (messages.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-1">
          <p className="text-[12px] text-[#6B7280]">
            No messages in #{activeChannel?.name ?? ''} yet.
          </p>
          <p className="text-[12px] text-[#6B7280]">Be the first to post something.</p>
        </div>
      )
    }

    const items: ReactNode[] = []
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      const prev = i > 0 ? messages[i - 1] : null

      if (!prev || !isSameDay(msg.createdAt, prev.createdAt)) {
        items.push(
          <div key={`divider-${i}`} className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-[#C8CDD6] dark:bg-[#484848]" />
            <span className="text-[11px] text-[#6B7280]">{formatDateLabel(msg.createdAt)}</span>
            <div className="flex-1 h-px bg-[#C8CDD6] dark:bg-[#484848]" />
          </div>
        )
      }

      const isGrouped = prev !== null && isSameSenderWithin5Min(prev, msg)
      const senderIdx = getSenderIndex(msg.senderId)

      if (isGrouped) {
        items.push(
          <div key={msg.id} className="ml-10">
            <p
              className="text-[13px] text-[#374151] dark:text-[#9CA3AF]"
              style={{ lineHeight: '1.6' }}
            >
              {renderBody(msg.body, msg.mentions, staffMap)}
            </p>
            {msg.attachmentKey && (
              <button
                onClick={() => handleDownloadAttachment(msg)}
                className="flex items-center gap-2 mt-1.5 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-md px-2.5 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:border-[#4A7FA5] transition-colors max-w-[240px]"
              >
                <Paperclip className="w-3.5 h-3.5 text-[#6B7280] flex-shrink-0" />
                <span className="truncate flex-1">{msg.attachmentName}</span>
                <Download className="w-3.5 h-3.5 text-[#6B7280] flex-shrink-0" />
              </button>
            )}
          </div>
        )
      } else {
        items.push(
          <div key={msg.id} className="flex gap-3 items-start">
            <div
              className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
              style={{ backgroundColor: getAvatarColor(senderIdx) }}
            >
              <span className="text-white text-[11px] font-medium">{msg.senderInitials}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                  {msg.senderName}
                </span>
                <span className="text-[11px] text-[#6B7280]">{formatTimestamp(msg.createdAt)}</span>
              </div>
              <p
                className="text-[13px] text-[#374151] dark:text-[#9CA3AF] mt-0.5"
                style={{ lineHeight: '1.6', marginLeft: '0' }}
              >
                {renderBody(msg.body, msg.mentions, staffMap)}
              </p>
              {msg.attachmentKey && (
                <button
                  onClick={() => handleDownloadAttachment(msg)}
                  className="flex items-center gap-2 mt-1.5 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-md px-2.5 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:border-[#4A7FA5] transition-colors max-w-[240px]"
                >
                  <Paperclip className="w-3.5 h-3.5 text-[#6B7280] flex-shrink-0" />
                  <span className="truncate flex-1">{msg.attachmentName}</span>
                  <Download className="w-3.5 h-3.5 text-[#6B7280] flex-shrink-0" />
                </button>
              )}
            </div>
          </div>
        )
      }
    }

    return <div className="space-y-2 p-4">{items}</div>
  }

  // ─── Modal input classes ──────────────────────────────────────────────────
  const inputClass =
    'w-full h-9 px-3 text-[14px] text-[#1F3148] dark:text-[#EDEEF0] bg-surface-input dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-md outline-none focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] transition-colors placeholder:text-[#9CA3AF]'

  const labelClass = 'block text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-1'

  // ─── JSX ─────────────────────────────────────────────────────────────────

  return (<>
      <div className="flex h-full overflow-hidden">

        {/* ── Channel list (220px fixed) ─────────────────────────────────── */}
        <div
          className="flex-shrink-0 flex flex-col border-r border-[#C8CDD6] dark:border-[#484848] h-full bg-surface-page dark:bg-dark-page"
          style={{ width: '220px' }}
        >
          {/* Header */}
          <div className="px-3.5 pt-4 pb-2">
            <h2 className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
              Firm Chat
            </h2>
            {isFirmOwner && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-1 text-[11px] font-medium text-[#4A7FA5] hover:underline text-left"
              >
                + New Channel
              </button>
            )}
          </div>

          {/* Channel rows */}
          <div className="flex-1 overflow-y-auto px-1.5 pb-3">
            {channelsLoading ? (
              <div className="space-y-1 px-2 pt-1">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-2 rounded bg-[#D5D8DE] dark:bg-[#444444] w-4/5 my-3" />
                ))}
              </div>
            ) : channels.length === 0 ? (
              /* Empty state */
              <div className="flex flex-col items-center justify-center h-full gap-2.5 px-3 text-center">
                <div className="w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card flex items-center justify-center">
                  <MessageSquare className="w-[18px] h-[18px] text-[#6B7280]" />
                </div>
                <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                  No channels yet
                </p>
                <p className="text-[12px] text-[#6B7280]">
                  Create your first channel to start the conversation.
                </p>
                {isFirmOwner && (
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="text-[12px] font-medium text-white bg-brand dark:bg-brand-btn px-3 py-1.5 rounded-md hover:opacity-90 transition-opacity"
                  >
                    + New Channel
                  </button>
                )}
              </div>
            ) : (
              channels.map((ch) => {
                const isActive = ch.id === activeChannelId
                const isHovered = hoveredChannelId === ch.id
                return (
                  <div
                    key={ch.id}
                    className="relative"
                    onMouseEnter={() => setHoveredChannelId(ch.id)}
                    onMouseLeave={() => setHoveredChannelId(null)}
                  >
                    <button
                      onClick={() => handleSelectChannel(ch.id)}
                      className={cn(
                        'w-full flex items-center gap-1 h-9 px-3.5 rounded-md text-[13px] transition-colors text-left',
                        isActive
                          ? 'bg-brand dark:bg-dark-sidebar text-white'
                          : 'text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-dark-card'
                      )}
                    >
                      <span className="truncate flex-1">
                        #{ch.name}
                      </span>
                      {ch.unreadCount > 0 && !isActive && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[#4A7FA5] flex-shrink-0" />
                      )}
                    </button>

                    {/* "..." dropdown button (firm_owner only, visible on hover) */}
                    {isFirmOwner && (isHovered || openDropdownId === ch.id) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setOpenDropdownId((prev) => (prev === ch.id ? null : ch.id))
                        }}
                        className={cn(
                          'absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded transition-colors',
                          isActive
                            ? 'text-white/70 hover:text-white hover:bg-white/15'
                            : 'text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] hover:bg-[#C8CDD6] dark:hover:bg-[#484848]'
                        )}
                      >
                        <MoreHorizontal className="w-3.5 h-3.5" />
                      </button>
                    )}

                    {/* Dropdown menu */}
                    {openDropdownId === ch.id && (
                      <div
                        ref={dropdownRef}
                        className="absolute right-2 top-full mt-1 z-20 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-md overflow-hidden"
                      >
                        <button
                          onClick={() => openRenameModal(ch.id, ch.name)}
                          className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
                        >
                          Rename
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); openMembersModal(ch.id) }}
                          onMouseDown={(e) => e.stopPropagation()}
                          className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
                        >
                          Manage Members
                        </button>
                        <button
                          onClick={() => openDeleteModal(ch.id, ch.name)}
                          className="block w-full text-left px-3 py-2 text-[13px] text-[#991B1B] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* ── Message feed (flex-1) ──────────────────────────────────────── */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-surface-page dark:bg-dark-page">
          {!activeChannelId ? (
            /* No channel selected */
            <div className="flex-1 flex items-center justify-center">
              <p className="text-[13px] text-[#6B7280]">Select a channel to start messaging</p>
            </div>
          ) : (
            <>
              {/* Channel header */}
              <div
                className="flex-shrink-0 flex items-center justify-between px-4 border-b border-[#C8CDD6] dark:border-[#484848] bg-surface-page dark:bg-dark-page"
                style={{ height: 48 }}
              >
                <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                  #{activeChannel?.name ?? ''}
                </span>
                {isFirmOwner && (
                  <button
                    onClick={(e) => { e.stopPropagation(); openMembersModal(activeChannelId) }}
                    className="flex items-center gap-1.5 h-7 px-3 rounded-md text-[12px] font-medium text-[#4A7FA5] border border-[#C8CDD6] dark:border-[#484848] hover:bg-[#D5D8DE] dark:hover:bg-dark-card transition-colors"
                  >
                    <Users className="w-[12px] h-[12px]" />
                    Members
                  </button>
                )}
              </div>

              {/* Messages list */}
              <div className="flex-1 overflow-y-auto">
                {renderMessages()}
                <div ref={messagesEndRef} />
              </div>

              {/* Compose box */}
              <div className="flex-shrink-0 border-t border-[#C8CDD6] dark:border-[#484848] px-4 py-3 relative">
                {/* @mention popover */}
                {showMentionPopover && filteredStaff.length > 0 && (
                  <div className="absolute bottom-full left-4 right-4 mb-1 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg overflow-y-auto shadow-md z-10"
                    style={{ maxHeight: '200px' }}>
                    {filteredStaff.map((staff, idx) => (
                      <button
                        key={staff.id}
                        onMouseDown={(e) => {
                          e.preventDefault()
                          handleMentionSelect(staff)
                        }}
                        onMouseEnter={() => setMentionIndex(idx)}
                        className={`flex items-center gap-2 w-full px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] transition-colors text-left ${
                          idx === mentionIndex
                            ? 'bg-[#D5D8DE] dark:bg-[#444444]'
                            : 'hover:bg-[#D5D8DE] dark:hover:bg-[#444444]'
                        }`}
                      >
                        <div
                          className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: '#4A7FA5' }}
                        >
                          <span className="text-white text-[10px] font-medium">{staff.initials}</span>
                        </div>
                        {staff.name}
                      </button>
                    ))}
                  </div>
                )}

                {/* Entity link picker */}
                {showPicker && (
                  <EntityLinkPicker
                    anchorRef={toolbarRef as React.RefObject<HTMLElement>}
                    onSelect={handleEntitySelect}
                    onClose={() => setShowPicker(false)}
                  />
                )}

                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.xlsx,.csv,.docx"
                  className="hidden"
                  onChange={handleFileSelect}
                />

                {/* Toolbar */}
                <div ref={toolbarRef} className="flex items-center gap-1 mb-2">
                  <button
                    onClick={() => { setShowPicker(true); setShowMentionPopover(false) }}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-[#6B7280] hover:bg-[#D5D8DE] dark:hover:bg-[#2D2D2D] transition-colors"
                  >
                    <Link className="w-3.5 h-3.5" />
                    Link record
                  </button>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-[#6B7280] hover:bg-[#D5D8DE] dark:hover:bg-[#2D2D2D] transition-colors"
                  >
                    <Paperclip className="w-3.5 h-3.5" />
                    Attach file
                  </button>
                </div>

                {/* Entity chips preview */}
                {linkedEntities.size > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {Array.from(linkedEntities.entries()).map(([token, link]) => (
                      <EntityChip key={token} link={link} onRemove={() => handleEntityRemove(token)} />
                    ))}
                  </div>
                )}

                {/* File preview chip */}
                {pendingFile && (
                  <div className="flex items-center gap-2 mb-2 px-1">
                    <div className="flex items-center gap-2 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-md px-2.5 py-1.5 text-[12px] text-[#374151] dark:text-[#EDEEF0] max-w-[240px]">
                      {fileUploading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#6B7280] flex-shrink-0" />
                      ) : (
                        <Paperclip className="w-3.5 h-3.5 text-[#6B7280] flex-shrink-0" />
                      )}
                      <span className="truncate flex-1">{pendingFile.name}</span>
                      <span className="text-[11px] text-[#6B7280] flex-shrink-0">
                        {(pendingFile.size / 1024).toFixed(0)}KB
                      </span>
                      <button
                        onClick={() => { setPendingFile(null); setPendingFileKey(null) }}
                        className="text-[#6B7280] hover:text-[#991B1B] transition-colors flex-shrink-0"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                )}

                <div className="flex items-end gap-2">
                  <textarea
                    ref={textareaRef}
                    value={composeValue}
                    onChange={handleComposeChange}
                    onKeyDown={handleKeyDown}
                    placeholder={activeChannel ? `Message #${activeChannel.name}...` : 'Select a channel...'}
                    rows={1}
                    className={`flex-1 resize-none border ${
                      showMentionPopover
                        ? 'border-[#4A7FA5] bg-[#EFF6FF] dark:bg-[#1e2a3a]'
                        : composeMentionIds.length > 0
                          ? 'bg-[#EFF6FF] dark:bg-[#1e2a3a] border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5]'
                          : 'bg-surface-input dark:bg-dark-page border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5]'
                    } rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors overflow-hidden`}
                    style={{ minHeight: '40px', maxHeight: '160px' }}
                  />
                  <div className="flex flex-col items-end flex-shrink-0">
                    <button
                      onClick={handleSend}
                      disabled={!composeValue.trim()}
                      className="bg-brand dark:bg-brand-btn text-white text-[12px] font-medium rounded-md h-8 px-3 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
                    >
                      Send
                    </button>
                    {sendHint && (
                      <p className="text-[11px] text-[#F59E0B] mt-1">
                        Please wait for the file to finish uploading
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Create channel modal ─────────────────────────────────────────── */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/[0.35] z-50 flex items-center justify-center">
          <div className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] p-6 w-[400px] shadow-xl">
            <h2 className="text-[16px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-4">
              Create Channel
            </h2>
            <div className="mb-4">
              <label className={labelClass}>
                Channel name
                <span className="inline-block w-1 h-1 rounded-full bg-[#E24B4A] ml-1 mb-0.5 align-middle" />
              </label>
              <input
                type="text"
                value={createChannelName}
                onChange={(e) => setCreateChannelName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreateChannel() }}
                placeholder="e.g. general"
                className={inputClass}
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowCreateModal(false); setCreateChannelName('') }}
                className="h-9 px-4 text-[14px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-dark-card rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateChannel}
                disabled={!createChannelName.trim()}
                className="h-9 px-4 text-[14px] font-medium text-white bg-brand dark:bg-brand-btn rounded-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Rename channel modal ─────────────────────────────────────────── */}
      {showRenameModal && (
        <div className="fixed inset-0 bg-black/[0.35] z-50 flex items-center justify-center">
          <div className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] p-6 w-[400px] shadow-xl">
            <h2 className="text-[16px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-4">
              Rename Channel
            </h2>
            <div className="mb-4">
              <label className={labelClass}>
                Channel name
                <span className="inline-block w-1 h-1 rounded-full bg-[#E24B4A] ml-1 mb-0.5 align-middle" />
              </label>
              <input
                type="text"
                value={renameChannelNameInput}
                onChange={(e) => setRenameChannelNameInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleRenameChannel() }}
                className={inputClass}
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowRenameModal(false)}
                className="h-9 px-4 text-[14px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-dark-card rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleRenameChannel}
                disabled={!renameChannelNameInput.trim()}
                className="h-9 px-4 text-[14px] font-medium text-white bg-brand dark:bg-brand-btn rounded-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              >
                Rename
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete channel modal ─────────────────────────────────────────── */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/[0.35] z-50 flex items-center justify-center">
          <div className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] p-6 w-[400px] shadow-xl">
            <h2 className="text-[16px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-3">
              Delete Channel
            </h2>
            <p className="text-[14px] text-[#374151] dark:text-[#9CA3AF] mb-6">
              Delete #{deleteChannelDisplayName}? This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="h-9 px-4 text-[14px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-dark-card rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteChannel}
                className="h-9 px-4 text-[14px] font-medium text-white rounded-md hover:opacity-90 transition-opacity"
                style={{ backgroundColor: '#991B1B' }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ── Manage Members Modal ─────────────────────────────────────── */}
      {showMembersModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/35"
            onClick={() => setShowMembersModal(false)}
          />
          <div className="relative z-10 w-[420px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#C8CDD6] dark:border-[#484848]">
              <div className="flex items-center gap-2">
                <Users className="w-[14px] h-[14px] text-[#6B7280]" />
                <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                  Manage Members
                </span>
              </div>
              <button
                onClick={() => setShowMembersModal(false)}
                className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
              >
                <X className="w-[14px] h-[14px]" />
              </button>
            </div>

            {/* Add member search */}
            <div className="px-4 pt-3 pb-2">
              <label className={labelClass}>Add staff member</label>
              <div className="relative">
                <input
                  type="text"
                  value={addMemberSearch}
                  onChange={(e) => setAddMemberSearch(e.target.value)}
                  placeholder="Search by name..."
                  className={inputClass}
                />
                {addMemberSearch && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-lg z-10 max-h-[160px] overflow-y-auto">
                    {memberSearchLoading ? (
                      <div className="px-3 py-2 text-[13px] text-[#6B7280]">Loading...</div>
                    ) : memberSearchResults.filter((s) =>
                        s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
                        !channelMembers.some((m) => m.userId === s.id)
                      ).length === 0 ? (
                      <div className="px-3 py-2 text-[13px] text-[#6B7280]">No staff found</div>
                    ) : (
                      memberSearchResults
                        .filter((s) =>
                          s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
                          !channelMembers.some((m) => m.userId === s.id)
                        )
                        .map((s) => (
                          <button
                            key={s.id}
                            onClick={() => handleAddMember(s.id)}
                            disabled={addMemberLoading}
                            className="w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors disabled:opacity-50 flex items-center gap-2"
                          >
                            <div
                              className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-white text-[10px] font-medium"
                              style={{ backgroundColor: '#4A7FA5' }}
                            >
                              {s.initials}
                            </div>
                            {s.name}
                          </button>
                        ))
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Current members list */}
            <div className="px-4 pb-4">
              <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2 mt-2">
                Current Members
              </p>
              {membersLoading ? (
                <div className="space-y-2">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-8 bg-[#D5D8DE] dark:bg-[#444444] rounded animate-pulse" />
                  ))}
                </div>
              ) : channelMembers.length === 0 ? (
                <p className="text-[12px] text-[#6B7280] text-center py-4">
                  No members yet. Add staff above.
                </p>
              ) : (
                <div className="space-y-1">
                  {channelMembers.map((m) => (
                    <div
                      key={m.id}
                      className="flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-[#F3F4F6] dark:hover:bg-[#333333]"
                    >
                      <div>
                        <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                          {m.userFullName}
                        </p>
                        <p className="text-[11px] text-[#6B7280]">{m.userEmail}</p>
                      </div>
                      <button
                        onClick={() => handleRemoveMember(m.userId)}
                        className="text-[#6B7280] hover:text-[#DC2626] transition-colors p-1"
                        title="Remove member"
                      >
                        <UserMinus className="w-[13px] h-[13px]" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

  </>)
}
