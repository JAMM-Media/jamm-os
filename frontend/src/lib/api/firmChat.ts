// path: frontend/src/lib/api/firmChat.ts
import api from '@/lib/api'

export interface Channel {
  id: string
  name: string
  unreadCount: number
  createdAt: string
}

export interface ChannelMember {
  id: string
  channelId: string
  userId: string
  userFullName: string
  userEmail: string
  addedAt: string
}

export interface FirmMessage {
  id: string
  channelId: string
  senderId: string
  senderName: string
  senderInitials: string
  body: string
  attachmentKey: string | null
  attachmentName: string | null
  attachmentSize: number | null
  mentions: string[]
  createdAt: string
}

function mapChannel(raw: Record<string, unknown>): Channel {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ''),
    unreadCount: Number(raw.unread_count ?? raw.unreadCount ?? 0),
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
  }
}

function mapMessage(raw: Record<string, unknown>): FirmMessage {
  return {
    id: String(raw.id),
    channelId: String(raw.channel_id ?? raw.channelId ?? ''),
    senderId: String(raw.sender_id ?? raw.senderId ?? ''),
    senderName: String(raw.sender_name ?? raw.senderName ?? ''),
    senderInitials: String(raw.sender_initials ?? raw.senderInitials ?? ''),
    body: String(raw.body ?? ''),
    attachmentKey: (raw.attachment_key ?? raw.attachmentKey ?? null) as string | null,
    attachmentName: (raw.attachment_name ?? raw.attachmentName ?? null) as string | null,
    attachmentSize:
      raw.attachment_size != null
        ? Number(raw.attachment_size)
        : raw.attachmentSize != null
          ? Number(raw.attachmentSize)
          : null,
    mentions: Array.isArray(raw.mentions) ? raw.mentions.map(String) : [],
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
  }
}

function mapChannelMember(raw: Record<string, unknown>): ChannelMember {
  return {
    id: String(raw.id),
    channelId: String(raw.channel_id ?? raw.channelId ?? ''),
    userId: String(raw.user_id ?? raw.userId ?? ''),
    userFullName: String(raw.user_full_name ?? raw.userFullName ?? ''),
    userEmail: String(raw.user_email ?? raw.userEmail ?? ''),
    addedAt: String(raw.added_at ?? raw.addedAt ?? ''),
  }
}

export const firmChatApi = {
  listChannels: async (): Promise<Channel[]> => {
    const { data } = await api.get('/firm-chat/channels')
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return items.map(mapChannel) as Channel[]
  },

  listMessages: async (channelId: string): Promise<FirmMessage[]> => {
    const { data } = await api.get(`/firm-chat/channels/${channelId}/messages`, {
      params: { limit: 50, offset: 0 },
    })
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return items.map(mapMessage) as FirmMessage[]
  },

  createChannel: async (name: string): Promise<Channel> => {
    const { data } = await api.post('/firm-chat/channels', { name })
    return mapChannel(data)
  },

  deleteChannel: async (channelId: string): Promise<void> => {
    await api.delete(`/firm-chat/channels/${channelId}`)
  },

  renameChannel: async (channelId: string, name: string): Promise<void> => {
    await api.patch(`/firm-chat/channels/${channelId}`, { name })
  },

  markChannelRead: async (channelId: string): Promise<void> => {
    await api.post(`/firm-chat/channels/${channelId}/read`)
  },

  postMessage: async (channelId: string, body: string, mentions?: string[]): Promise<FirmMessage> => {
    const { data } = await api.post(`/firm-chat/channels/${channelId}/messages`, { body, mentions })
    return mapMessage(data)
  },

  listMembers: async (channelId: string): Promise<ChannelMember[]> => {
    const { data } = await api.get(`/firm-chat/channels/${channelId}/members`)
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return items.map(mapChannelMember)
  },

  addMember: async (channelId: string, userId: string): Promise<ChannelMember> => {
    const { data } = await api.post(
      `/firm-chat/channels/${channelId}/members`,
      null,
      { params: { user_id: userId } }
    )
    return mapChannelMember(data)
  },

  removeMember: async (channelId: string, userId: string): Promise<void> => {
    await api.delete(`/firm-chat/channels/${channelId}/members/${userId}`)
  },
}
