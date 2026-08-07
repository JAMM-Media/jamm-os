// frontend/src/lib/api/cooperative.ts
// Deliberately separate from firmChat.ts per spec section 3 isolation requirement.
import api from '@/lib/api'

export interface CooperativeMessage {
  id: string
  room_id: string
  author_handle: string
  body: string
  created_at: string
}

export interface CooperativeRoom {
  id: string
  room_type: string
  name: string | null
}

export const cooperativeApi = {
  optIn: async (): Promise<{ cooperative_enabled: boolean; handle: string }> => {
    const { data } = await api.post('/cooperative/opt-in')
    return data as { cooperative_enabled: boolean; handle: string }
  },

  getRooms: async (): Promise<{ items: CooperativeRoom[]; total: number }> => {
    const { data } = await api.get('/cooperative/rooms')
    return data as { items: CooperativeRoom[]; total: number }
  },

  getMessages: async (roomId: string, page = 1): Promise<{ items: CooperativeMessage[]; total: number }> => {
    const { data } = await api.get(`/cooperative/rooms/${roomId}/messages`, {
      params: { page, page_size: 100 },
    })
    return data as { items: CooperativeMessage[]; total: number }
  },

  postMessage: async (roomId: string, body: string): Promise<CooperativeMessage> => {
    const { data } = await api.post(`/cooperative/rooms/${roomId}/messages`, { body })
    return data as CooperativeMessage
  },
}
