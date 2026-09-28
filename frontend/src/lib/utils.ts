import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatEngagementType(value: string | null | undefined): string {
  if (!value) return '—'
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

export function formatEntityType(entityType: string | null | undefined): string {
  if (!entityType) return ''
  const labels: Record<string, string> = {
    individual: 'Individual',
    business: 'Business',
    trust: 'Trust',
    estate: 'Estate',
    non_profit: 'Non-Profit',
  }
  return labels[entityType] ?? entityType
}

// Safely format a YYYY-MM-DD date-only string without UTC midnight shift.
// The single-argument Date constructor treats bare date strings as UTC midnight,
// which shifts the displayed date back by one day for users behind UTC.
// The multi-argument constructor always uses local time and is immune to this.
export function formatLocalDate(
  dateStr: string | null | undefined,
  options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' },
  fallback = '—'
): string {
  if (!dateStr) return fallback
  const parts = dateStr.split('-')
  if (parts.length < 3) return fallback
  const year = parseInt(parts[0], 10)
  const month = parseInt(parts[1], 10) - 1
  const day = parseInt(parts[2], 10)
  return new Date(year, month, day).toLocaleDateString('en-US', options)
}

// Produce a YYYY-MM-DD string from a Date using local time, not UTC.
// Use this wherever you need today's date as a string or want to compare
// date strings in the user's local calendar day.
export function localDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Resolve the most-specific due date for an engagement: extended deadline
// beats filing deadline beats end_date. Returns null if all are null.
export function getEffectiveDueDate(engagement: {
  extendedDeadline: string | null
  filingDeadline: string | null
  endDate: string | null
}): string | null {
  return engagement.extendedDeadline ?? engagement.filingDeadline ?? engagement.endDate
}

// Keep events whose YYYY-MM-DD date string is on or after todayStr.
// Used by the Calendar's Upcoming sidebar to suppress past events.
export function filterUpcomingByDate<T extends { date: string }>(events: T[], todayStr: string): T[] {
  return events.filter(ev => ev.date >= todayStr)
}

// Return the Sunday on or before d (local time). Used for Week view rendering.
export function startOfWeek(d: Date): Date {
  const sun = new Date(d)
  sun.setDate(sun.getDate() - sun.getDay())
  return sun
}

export function formatEntitySubtype(entitySubtype: string | null | undefined): string {
  if (!entitySubtype) return ''
  const labels: Record<string, string> = {
    sole_proprietor: 'Sole Proprietor',
    partnership: 'Partnership',
    llc: 'LLC',
    s_corp: 'S-Corp',
    c_corp: 'C-Corp',
    professional_corp: 'Professional Corp',
    revocable_trust: 'Revocable Trust',
    irrevocable_trust: 'Irrevocable Trust',
    charitable_trust: 'Charitable Trust',
    special_needs_trust: 'Special Needs Trust',
    public_charity: 'Public Charity (501c3)',
    private_foundation: 'Private Foundation (501c3)',
    social_welfare: 'Social Welfare (501c4)',
    other_tax_exempt: 'Other Tax-Exempt',
  }
  return labels[entitySubtype] ?? entitySubtype
}
