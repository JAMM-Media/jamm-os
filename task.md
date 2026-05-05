TASK: Add upload method to documentsApi

FILE: frontend/src/lib/api/documents.ts

Find:
  getSignedUrl: async (id: string): Promise<string> => {
    const { data } = await api.get(`/documents/${id}/download`)
    return String(data.url ?? data.signed_url ?? '')
  },
}

Replace with:
  getSignedUrl: async (id: string): Promise<string> => {
    const { data } = await api.get(`/documents/${id}/download`)
    return String(data.url ?? data.signed_url ?? '')
  },

  upload: async (file: File, clientId?: string, engagementId?: string): Promise<Document> => {
    const formData = new FormData()
    formData.append('file', file)
    if (clientId) formData.append('client_id', clientId)
    if (engagementId) formData.append('engagement_id', engagementId)
    const { data } = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return mapDocument(data)
  },
}

No other files need to be changed.