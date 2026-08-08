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
}

export interface PeerNetworkRoom {
  id: string
  room_type: string
  name: string | null
}

export const peerNetworkApi = {
  optIn: async (): Promise<{ peer_network_enabled: boolean; handle: string }> => {
    const { data } = await api.post('/peer-network/opt-in')
    return data as { peer_network_enabled: boolean; handle: string }
  },

  getRooms: async (): Promise<{ items: PeerNetworkRoom[]; total: number; my_handle: string }> => {
    const { data } = await api.get('/peer-network/rooms')
    return data as { items: PeerNetworkRoom[]; total: number; my_handle: string }
  },

  getMessages: async (roomId: string, page = 1): Promise<{ items: PeerNetworkMessage[]; total: number }> => {
    const { data } = await api.get(`/peer-network/rooms/${roomId}/messages`, {
      params: { page, page_size: 100 },
    })
    return data as { items: PeerNetworkMessage[]; total: number }
  },

  postMessage: async (roomId: string, body: string): Promise<PeerNetworkMessage> => {
    const { data } = await api.post(`/peer-network/rooms/${roomId}/messages`, { body })
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
}
