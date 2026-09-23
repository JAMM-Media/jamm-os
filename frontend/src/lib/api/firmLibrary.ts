// frontend/src/lib/api/firmLibrary.ts
import api from '@/lib/api'

export const firmLibraryApi = {
  getStarterTemplatesStatus: async (): Promise<{ has_starter_templates: boolean }> => {
    const { data } = await api.get('/firm-library/starter-templates-status')
    return data as { has_starter_templates: boolean }
  },

  seedStarterTemplates: async (): Promise<{ seeded: number }> => {
    const { data } = await api.post('/firm-library/seed-starter-templates')
    return data as { seeded: number }
  },
}