import type { Patch } from '../types'
import { BENEFIT_LONG, formatValue } from '../lib/format'

const TONE = {
  accepted: 'border-teal bg-teal/10 text-teal-dark',
  rejected: 'border-red-300 bg-red-50 text-red-800',
  failed: 'border-slate-300 bg-slate-50 text-slate-700',
}

export default function PatchResult({ patch }: { patch: Patch }) {
  const g = patch.gate
  return (
    <div className="space-y-3 text-sm">
      <div className={`rounded-lg border-2 p-3 ${TONE[patch.status]}`}>
        <div className="text-base font-bold">
          {patch.status === 'accepted' ? '✅ Patch accepted' : patch.status === 'rejected' ? '❌ Patch rejected' : '⚠️ No patch'}
          <span className="ml-2 font-normal">
            {BENEFIT_LONG[patch.benefit] ?? patch.benefit}
            {patch.from_version && ` · ${patch.from_version}${patch.to_version ? ` → ${patch.to_version}` : ''}`}
          </span>
        </div>
        {patch.reason && <p className="mt-1">{patch.reason}</p>}
      </div>
      {patch.rationale && (
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">Nemotron's rationale</h4>
          <p className="mt-1 text-slate-700">{patch.rationale}</p>
        </div>
      )}
      {patch.ops && patch.ops.length > 0 && (
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">Proposed changes</h4>
          <ul className="mt-1 space-y-1">
            {patch.ops.map((o, i) => (
              <li key={i} className="overflow-x-auto rounded bg-slate-900 px-2 py-1 font-mono text-xs text-mint">
                {o.op} {o.path} → {typeof o.value === 'string' ? `"${o.value.length > 120 ? o.value.slice(0, 120) + '…' : o.value}"` : formatValue(o.value)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {g && (
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">Regression gate</h4>
          <div className="mt-1 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Before" value={`${g.before.passed}/${g.before.total}`} />
            <Stat label="After" value={`${g.after.passed}/${g.after.total}`} />
            <Stat label="Regressions" value={String(g.regressions.length)} bad={g.regressions.length > 0} />
            <Stat label="Fixed" value={String(g.fixes.length)} good={g.fixes.length > 0} />
          </div>
          <p className="mt-2 text-xs text-slate-600">Reported case fixed: {g.target_fixed ? 'yes' : 'no'}</p>
          {g.regressions.length > 0 && <CaseList title="Regressions" items={g.regressions} />}
          {g.fixes.length > 0 && <CaseList title="Cases fixed" items={g.fixes} />}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, bad, good }: { label: string; value: string; bad?: boolean; good?: boolean }) {
  return (
    <div className={`rounded-md border p-2 text-center ${bad ? 'border-red-300 bg-red-50' : good ? 'border-teal bg-teal/10' : 'border-slate-200'}`}>
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="text-lg font-extrabold text-navy">{value}</div>
    </div>
  )
}

function CaseList({ title, items }: { title: string; items: string[] }) {
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs font-semibold text-navy">
        {title} ({items.length})
      </summary>
      <ul className="mt-1 flex flex-wrap gap-1">
        {items.map((x) => (
          <li key={x} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px]">
            {x}
          </li>
        ))}
      </ul>
    </details>
  )
}
