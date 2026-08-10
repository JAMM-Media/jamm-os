// frontend/src/lib/api/peerNetwork.ts
// Deliberately separate from firmChat.ts per spec section 3 isolation requirement.
import api from '@/lib/api'

export interface PeerNetworkMessage {
  id: string
  room_id: string
  author_handle: string
  author_display: string
  author_member_id: string | null
  body: string
  created_at: string
  edited: boolean
  deleted: boolean
  is_jamm_team: boolean
  parent_id: string | null
  reply_count: number
  reactions: Array<{ emoji: string; count: number; reacted_by_me: boolean }>
}

export interface PeerNetworkRoom {
  id: string
  room_type: string
  name: string | null
  dm_display: string | null
}

export interface AliasEntry {
  target_member_id: string
  label: string | null
  handle: string
}

export const peerNetworkApi = {
  optIn: async (): Promise<{ peer_network_enabled: boolean; handle: string }> => {
    const { data } = await api.post('/peer-network/opt-in')
    return data as { peer_network_enabled: boolean; handle: string }
  },

  getRooms: async (): Promise<{ items: PeerNetworkRoom[]; total: number; my_handle: string; has_posted: boolean; is_muted: boolean; muted_reason: string | null }> => {
    const { data } = await api.get('/peer-network/rooms')
    return data as { items: PeerNetworkRoom[]; total: number; my_handle: string; has_posted: boolean; is_muted: boolean; muted_reason: string | null }
  },

  getMessages: async (roomId: string, page = 1): Promise<{ items: PeerNetworkMessage[]; total: number }> => {
    const { data } = await api.get(`/peer-network/rooms/${roomId}/messages`, {
      params: { page, page_size: 100 },
    })
    return data as { items: PeerNetworkMessage[]; total: number }
  },

  postMessage: async (roomId: string, body: string, parentId?: string): Promise<PeerNetworkMessage> => {
    const { data } = await api.post(`/peer-network/rooms/${roomId}/messages`, {
      body,
      ...(parentId ? { parent_id: parentId } : {}),
    })
    return data as PeerNetworkMessage
  },

  setAlias: async (targetMemberId: string, label: string): Promise<void> => {
    await api.patch(`/peer-network/members/${targetMemberId}/alias`, { label })
  },

  editMessage: async (messageId: string, body: string): Promise<{ id: string; body: string; edited: boolean; deleted: boolean }> => {
    const { data } = await api.patch(`/peer-network/messages/${messageId}`, { body })
    return data as { id: string; body: string; edited: boolean; deleted: boolean }
  },

  deleteMessage: async (messageId: string): Promise<void> => {
    await api.delete(`/peer-network/messages/${messageId}`)
  },

  acceptTerms: async (): Promise<{ accepted: boolean; terms_accepted_at: string }> => {
    const { data } = await api.post('/peer-network/accept-terms')
    return data as { accepted: boolean; terms_accepted_at: string }
  },

  getAliases: async (): Promise<{ items: AliasEntry[]; total: number }> => {
    const { data } = await api.get('/peer-network/aliases')
    return data as { items: AliasEntry[]; total: number }
  },

  searchMembers: async (handlePrefix: string): Promise<{ items: AliasEntry[]; total: number }> => {
    const { data } = await api.get('/peer-network/members/search', { params: { handle_prefix: handlePrefix } })
    return data as { items: AliasEntry[]; total: number }
  },

  createRoom: async (
    roomType: 'dm' | 'subgroup',
    memberIds: string[],
    name?: string,
  ): Promise<{ id: string; room_type: string; name: string | null; member_count: number }> => {
    const { data } = await api.post('/peer-network/rooms', { room_type: roomType, member_ids: memberIds, name: name ?? null })
    return data as { id: string; room_type: string; name: string | null; member_count: number }
  },

  renameRoom: async (roomId: string, name: string): Promise<{ id: string; room_type: string; name: string | null }> => {
    const { data } = await api.patch(`/peer-network/rooms/${roomId}`, { name })
    return data as { id: string; room_type: string; name: string | null }
  },

  hideRoom: async (roomId: string): Promise<{ hidden: boolean; room_id: string }> => {
    const { data } = await api.post(`/peer-network/rooms/${roomId}/hide`)
    return data as { hidden: boolean; room_id: string }
  },

  toggleReaction: async (
    messageId: string,
    emoji: string,
  ): Promise<{ message_id: string; reactions: Array<{ emoji: string; count: number; reacted_by_me: boolean }> }> => {
    const { data } = await api.post(`/peer-network/messages/${messageId}/reactions`, { emoji })
    return data as { message_id: string; reactions: Array<{ emoji: string; count: number; reacted_by_me: boolean }> }
  },
}
