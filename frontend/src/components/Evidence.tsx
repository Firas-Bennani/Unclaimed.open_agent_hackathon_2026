import type { Clause, Fact } from '../types'
import { fieldLabel, formatValue } from '../lib/format'
import { SourceBadge } from './ui'

export function ClauseList({ clauses }: { clauses: Clause[] }) {
  if (!clauses.length) return <p className="text-sm text-slate-500">No clause cited.</p>
  return (
    <ul className="space-y-2">
      {clauses.map((c) => (
        <li key={`${c.id}-${c.cited_by}`} className="rounded-md border border-slate-200 bg-slate-50 p-2.5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded bg-navy px-1.5 py-0.5 font-mono text-[11px] font-bold text-white">{c.id}</span>
            {c.cited_by && <span className="text-[11px] text-slate-500">cited by {c.cited_by}</span>}
            <a href={c.source_url} target="_blank" rel="noreferrer" className="ml-auto text-xs font-semibold text-teal-dark underline">
              Source ↗
            </a>
          </div>
          <p className="mt-1 text-slate-700">{c.text}</p>
        </li>
      ))}
    </ul>
  )
}

export function FactItem({ f }: { f: Fact }) {
  const flags: string[] = []
  if (f.status === 'stale') flags.push('out of date')
  if (f.status === 'superseded') flags.push('superseded')
  if (f.confidence < 0.8) flags.push('approximate')
  else if (f.confidence < 1) flags.push(`confidence ${Math.round(f.confidence * 100)}%`)
  return (
    <li className="rounded-md border border-slate-200 p-2.5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <SourceBadge source={f.source} />
        <span className="font-semibold text-navy">{fieldLabel(f.field)}</span>
        <span className="font-mono text-navy">= {formatValue(f.value, f.field)}</span>
        {flags.map((x) => (
          <span key={x} className="rounded bg-gold/30 px-1.5 py-0.5 text-[11px] font-semibold text-gold-dark">
            {x}
          </span>
        ))}
      </div>
      <div className="mt-1 text-xs text-slate-500">
        record <code className="text-slate-700">{f.record_id}</code>
        {f.as_of && <> · as of {f.as_of}</>} · {f.extraction_method.replace(/_/g, ' ')}
      </div>
      {f.quote && <blockquote className="mt-1.5 border-l-4 border-amber-300 bg-amber-50 px-2 py-1 text-xs italic text-slate-700">"{f.quote}"</blockquote>}
      {f.note && !f.quote && <p className="mt-1 text-xs text-slate-600">{f.note}</p>}
    </li>
  )
}

export function FactList({ ids, facts }: { ids: string[]; facts: Fact[] }) {
  const byId = new Map(facts.map((f) => [f.id, f]))
  const items = ids.map((i) => byId.get(i)).filter((f): f is Fact => Boolean(f))
  if (!items.length) return <p className="text-sm text-slate-500">No source records cited.</p>
  return (
    <ul className="space-y-2">
      {items.map((f) => (
        <FactItem key={f.id} f={f} />
      ))}
    </ul>
  )
}
