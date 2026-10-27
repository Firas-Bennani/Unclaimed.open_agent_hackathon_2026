import type { SourceName, Status } from '../types'

export const BENEFITS = ['pension_credit', 'attendance_allowance', 'council_tax_reduction', 'warm_home_discount'] as const

export const BENEFIT_SHORT: Record<string, string> = {
  pension_credit: 'Pension Credit',
  attendance_allowance: 'Attendance Allow.',
  council_tax_reduction: 'Council Tax Red.',
  warm_home_discount: 'Warm Home Disc.',
}

export const BENEFIT_LONG: Record<string, string> = {
  pension_credit: 'Pension Credit',
  attendance_allowance: 'Attendance Allowance',
  council_tax_reduction: 'Council Tax Reduction',
  warm_home_discount: 'Warm Home Discount',
}

export const STATUS_LABEL: Record<Status, string> = {
  eligible: 'Eligible',
  not_eligible: 'Not eligible',
  needs_info: 'Needs info',
}

export const STATUS_ICON: Record<Status, string> = {
  eligible: '✅',
  not_eligible: '❌',
  needs_info: '⚠️',
}

export const SOURCE_STYLE: Record<SourceName, { label: string; cls: string }> = {
  dwp: { label: 'DWP', cls: 'bg-sky-100 text-sky-900 ring-sky-300' },
  housing: { label: 'Housing export', cls: 'bg-violet-100 text-violet-900 ring-violet-300' },
  council: { label: 'Council tax', cls: 'bg-orange-100 text-orange-900 ring-orange-300' },
  notes: { label: 'Caseworker notes', cls: 'bg-amber-100 text-amber-900 ring-amber-300' },
  caseworker: { label: 'Caseworker', cls: 'bg-teal/20 text-teal-dark ring-teal' },
  derived: { label: 'Derived', cls: 'bg-slate-100 text-slate-700 ring-slate-300' },
}

export const BOOL_FIELDS = new Set([
  'has_partner',
  'partner_reached_spa',
  'receives_pension_credit',
  'receives_housing_benefit',
  'receives_qualifying_benefit_on_whd_date',
  'receives_dla_or_pip',
  'needs_care_help',
  'care_day_and_night',
  'in_gb_2_of_last_3_years',
  'council_tax_liable',
  'electricity_bill_in_name',
])

export const NUMBER_FIELDS = new Set([
  'age_years',
  'state_pension_age',
  'weekly_income_total',
  'savings',
  'care_need_months',
  'council_tax_annual_net',
])

const MONEY_FIELDS = new Set(['weekly_income_total', 'savings', 'council_tax_annual_net'])

export function fieldLabel(field: string): string {
  const s = field.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function gbp(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toLocaleString('en-GB', { style: 'currency', currency: 'GBP', minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function formatValue(v: unknown, field?: string): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (typeof v === 'number') {
    if (field && MONEY_FIELDS.has(field)) return gbp(v)
    return Number.isInteger(v) ? v.toLocaleString('en-GB') : v.toLocaleString('en-GB', { maximumFractionDigits: 2 })
  }
  if (Array.isArray(v)) return v.map((x) => formatValue(x)).join(', ')
  if (typeof v === 'object') {
    const o = v as Record<string, unknown>
    if ('ref' in o) return `${String(o.ref).replace(/_/g, ' ')} (${formatValue(o.value)})`
    return JSON.stringify(v)
  }
  return String(v)
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
}

export function pct(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}
