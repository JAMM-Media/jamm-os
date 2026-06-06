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
