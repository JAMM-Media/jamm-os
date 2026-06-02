// frontend/src/components/engagements/SaveAsTemplateModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { X, Plus, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import type { Engagement } from '@/lib/api'

interface TaskItem {
  title: string
  description: string
}

interface SaveAsTemplateModalProps {
  engagement: Engagement
  onClose: () => void
}

export function SaveAsTemplateModal({ engagement, onClose }: SaveAsTemplateModalProps) {
  const [name, setName] = useState(engagement.name)
  const [description, setDescription] = useState(engagement.description ?? '')
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [docs, setDocs] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [loadingTasks, setLoadingTasks] = useState(true)

  useEffect(() => {
    setLoadingTasks(true)
    api.get('/tasks/', { params: { engagement_id: engagement.id, limit: 100 } })
      .then(({ data }) => {
        const items = Array.isArray(data) ? data : (data.items ?? [])
        setTasks(items.map((t: Record<string, unknown>) => ({
          title: String(t.title ?? ''),
          description: String(t.notes ?? ''),
        })))
      })
      .catch(() => {})
      .finally(() => setLoadingTasks(false))
  }, [engagement.id])

  function addTask() {
    setTasks((prev) => [...prev, { title: '', description: '' }])
  }

  function updateTask(idx: number, field: keyof TaskItem, value: string) {
    setTasks((prev) => prev.map((t, i) => i === idx ? { ...t, [field]: value } : t))
  }

  function removeTask(idx: number) {
    setTasks((prev) => prev.filter((_, i) => i !== idx))
  }

  function addDoc() {
    setDocs((prev) => [...prev, ''])
  }

  function updateDoc(idx: number, value: string) {
    setDocs((prev) => prev.map((d, i) => i === idx ? value : d))
  }

  function removeDoc(idx: number) {
    setDocs((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    if (!name.trim()) {
      toast.error('Template name is required')
      return
    }
    setSaving(true)
    try {
      await api.post('/api/v1/engagement-templates/', {
        name: name.trim(),
        description: description.trim() || null,
        engagement_type: engagement.engagementType ?? null,
        task_templates: tasks
          .filter((t) => t.title.trim())
          .map((t, i) => ({ title: t.title.trim(), description: t.description.trim() || null, order: i })),
        document_checklist: docs.filter((d) => d.trim()),
        notes: notes.trim() || null,
      })
      toast.success('Template saved')
      onClose()
    } catch {
      toast.error('Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#E5E7EB] dark:border-[#333]">
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">Save as Template</h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Template name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light resize-none"
            />
          </div>

          {/* Tasks from engagement */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Default Tasks
              </label>
              <button
                type="button"
                onClick={addTask}
                className="flex items-center gap-1 text-[11px] text-brand-light hover:underline"
              >
                <Plus className="h-3 w-3" /> Add Task
              </button>
            </div>
            {loadingTasks ? (
              <div className="flex items-center gap-2 text-[12px] text-[#6B7280]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading tasks...
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.map((task, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={task.title}
                      onChange={(e) => updateTask(idx, 'title', e.target.value)}
                      placeholder="Task title"
                      className="flex-1 h-8 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[12px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                    />
                    <button
                      type="button"
                      onClick={() => removeTask(idx)}
                      className="text-[#9CA3AF] hover:text-red-500 transition-colors flex-shrink-0"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                {tasks.length === 0 && (
                  <p className="text-[11px] text-[#9CA3AF]">No tasks. Click &ldquo;Add Task&rdquo; to add one.</p>
                )}
              </div>
            )}
          </div>

          {/* Document checklist */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Document Checklist
              </label>
              <button
                type="button"
                onClick={addDoc}
                className="flex items-center gap-1 text-[11px] text-brand-light hover:underline"
              >
                <Plus className="h-3 w-3" /> Add Document
              </button>
            </div>
            <div className="space-y-2">
              {docs.map((doc, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={doc}
                    onChange={(e) => updateDoc(idx, e.target.value)}
                    placeholder="e.g. W-2, 1099-INT"
                    className="flex-1 h-8 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[12px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
                  <button
                    type="button"
                    onClick={() => removeDoc(idx)}
                    className="text-[#9CA3AF] hover:text-red-500 transition-colors flex-shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {docs.length === 0 && (
                <p className="text-[11px] text-[#9CA3AF]">No documents. Click &ldquo;Add Document&rdquo; to add one.</p>
              )}
            </div>
          </div>

          {/* Internal notes */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Internal notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Notes visible to staff when using this template..."
              className="w-full px-3 py-2 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light resize-none"
            />
            <p className="text-[11px] text-[#9CA3AF] mt-1">Only visible to staff, not clients</p>
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-[#E5E7EB] dark:border-[#333]">
          <button
            onClick={onClose}
            className="h-8 px-4 text-[12px] font-medium text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-8 px-4 rounded-md bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity flex items-center gap-1.5"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Save Template
          </button>
        </div>
      </div>
    </div>
  )
}
