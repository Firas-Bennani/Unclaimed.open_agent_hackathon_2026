import { useEffect, useRef, type ReactNode } from 'react'
import type { SourceName, Status } from '../types'
import { SOURCE_STYLE, STATUS_ICON, STATUS_LABEL } from '../lib/format'

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 p-6 text-slate-600">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-teal border-t-transparent" aria-hidden />
      <span>{label}</span>
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const msg = typeof error === 'string' ? error : error.message
  return (
    <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1 text-sm">{msg}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800">
          Try again
        </button>
      )}
    </div>
  )
}

const STATUS_PILL: Record<Status, string> = {
  eligible: 'bg-teal/15 text-teal-dark ring-teal/50',
  not_eligible: 'bg-slate-100 text-slate-600 ring-slate-300',
  needs_info: 'bg-gold/25 text-gold-dark ring-gold',
}

export function StatusPill({ status, compact = false }: { status: Status; compact?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${STATUS_PILL[status]}`}>
      <span aria-hidden>{STATUS_ICON[status]}</span>
      {compact ? <span className="sr-only">{STATUS_LABEL[status]}</span> : STATUS_LABEL[status]}
    </span>
  )
}

export function SourceBadge({ source }: { source: SourceName }) {
  const s = SOURCE_STYLE[source] ?? SOURCE_STYLE.derived
  return <span className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold ring-1 ${s.cls}`}>{s.label}</span>
}

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'gold' }) {
  const styles = {
    primary: 'bg-teal-dark text-white hover:bg-[#1c6d56] disabled:bg-slate-400',
    secondary: 'bg-white text-navy ring-1 ring-slate-300 hover:bg-slate-50 disabled:text-slate-400',
    ghost: 'text-teal-dark hover:bg-teal/10 disabled:text-slate-400',
    gold: 'bg-gold text-navy hover:bg-[#e9b53c] disabled:bg-slate-300',
  }[variant]
  return (
    <button type="button" className={`inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed ${styles} ${className}`} {...rest}>
      {children}
    </button>
  )
}

export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      prev?.focus()
    }
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-navy/60 p-4 sm:p-8" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className={`w-full ${wide ? 'max-w-4xl' : 'max-w-2xl'} rounded-xl bg-white shadow-2xl outline-none`}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="text-lg font-bold text-navy">{title}</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-2xl leading-none text-slate-500 hover:text-navy" aria-label="Close">
            ×
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</section>
}

export function TriChip({ v }: { v: string }) {
  const cls = v === 'TRUE' ? 'bg-teal/20 text-teal-dark' : v === 'FALSE' ? 'bg-red-100 text-red-800' : 'bg-gold/30 text-gold-dark'
  return <span className={`rounded px-1.5 py-0.5 font-mono text-[11px] font-bold ${cls}`}>{v}</span>
}
