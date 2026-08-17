// path: frontend/src/components/leads/BookCallModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Modal } from '@/components/ui/Modal'
import { bookingsApi, type Slot } from '@/lib/api/bookings'
import { staffApi } from '@/lib/api/staffApi'

interface BookCallModalProps {
  open: boolean
  onClose: () => void
  leadId: string
  onBooked: () => void
}

function groupSlotsByDate(slots: Slot[]): Record<string, Slot[]> {
  const groups: Record<string, Slot[]> = {}
  for (const slot of slots) {
    const dateKey = slot.startTime.slice(0, 10)
    if (!groups[dateKey]) groups[dateKey] = []
    groups[dateKey].push(slot)
  }
  return groups
}

function formatDayHeading(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

function formatSlotTime(isoStr: string): string {
  return new Date(isoStr).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function BookCallModal({ open, onClose, leadId, onBooked }: BookCallModalProps) {
  const [staffList, setStaffList] = useState<{ id: string; full_name: string | null }[]>([])
  const [staffLoading, setStaffLoading] = useState(false)
  const [selectedStaffId, setSelectedStaffId] = useState<string | null>(null)
  const [slots, setSlots] = useState<Slot[]>([])
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [booking, setBooking] = useState(false)

  useEffect(() => {
    if (!open) return
    setSelectedStaffId(null)
    setSlots([])
    setStaffLoading(true)
    staffApi.listBookableStaff()
      .then(setStaffList)
      .catch(() => toast.error('Failed to load staff list.'))
      .finally(() => setStaffLoading(false))
  }, [open])

  function fetchSlots(staffId: string) {
    setSlotsLoading(true)
    setSlots([])
    bookingsApi.getSlots(staffId)
      .then(setSlots)
      .catch(() => toast.error('Failed to load available slots.'))
      .finally(() => setSlotsLoading(false))
  }

  function handleSelectStaff(staffId: string) {
    setSelectedStaffId(staffId)
    fetchSlots(staffId)
  }

  async function handleSelectSlot(slot: Slot) {
    if (booking) return
    setBooking(true)
    try {
      await bookingsApi.create({
        lead_id: leadId,
        staff_user_id: selectedStaffId!,
        start_time: slot.startTime,
        end_time: slot.endTime,
      })
      toast.success('Call booked.')
      onBooked()
      onClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to book the call.')
      if (selectedStaffId) fetchSlots(selectedStaffId)
    } finally {
      setBooking(false)
    }
  }

  const slotGroups = groupSlotsByDate(slots)
  const dateKeys = Object.keys(slotGroups).sort()

  return (
    <Modal open={open} onClose={onClose} title="Book a Call" size="md">
      {selectedStaffId === null ? (
        <div className="flex flex-col gap-3">
          {staffLoading ? (
            <p className="text-[13px] text-[#6B7280] py-4 text-center">Loading staff...</p>
          ) : staffList.length === 0 ? (
            <p className="text-[13px] text-[#6B7280] py-4 text-center">
              No staff members have set up availability yet.
            </p>
          ) : (
            <>
              <p className="text-[12px] text-[#6B7280] mb-1">Select a staff member to see their open times.</p>
              {staffList.map((s) => (
                <button
                  key={s.id}
                  onClick={() => handleSelectStaff(s.id)}
                  className="w-full text-left px-4 py-3 rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[14px] font-medium text-brand dark:text-[#EDEEF0] hover:border-brand dark:hover:border-[#4A7FA5] transition-colors"
                >
                  {s.full_name ?? 'Unnamed staff'}
                </button>
              ))}
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <button
            onClick={() => { setSelectedStaffId(null); setSlots([]) }}
            className="self-start text-[12px] text-brand dark:text-[#4A7FA5] hover:underline"
          >
            Back to staff list
          </button>
          <p className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0]">
            {staffList.find((s) => s.id === selectedStaffId)?.full_name ?? 'Staff member'}
          </p>
          {slotsLoading ? (
            <p className="text-[13px] text-[#6B7280] py-4 text-center">Loading available times...</p>
          ) : dateKeys.length === 0 ? (
            <p className="text-[13px] text-[#6B7280] py-4 text-center">
              No open times in the next two weeks.
            </p>
          ) : (
            <div className="flex flex-col gap-5 max-h-[420px] overflow-y-auto pr-1">
              {dateKeys.map((dateKey) => (
                <div key={dateKey}>
                  <p className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] mb-2">
                    {formatDayHeading(dateKey)}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {slotGroups[dateKey].map((slot) => (
                      <button
                        key={slot.startTime}
                        onClick={() => handleSelectSlot(slot)}
                        disabled={booking}
                        className="h-9 px-4 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[13px] font-medium text-brand dark:text-[#EDEEF0] hover:border-brand dark:hover:border-[#4A7FA5] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {formatSlotTime(slot.startTime)}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
