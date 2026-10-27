import { useMemo, useState } from 'react'
import { api, ApiError } from '../api'
import { Card, ErrorBox, Spinner } from '../components/ui'
import { BENEFITS, BENEFIT_SHORT, formatDateTime, pct } from '../lib/format'
import { useAsync } from '../lib/useAsync'

type Metrics = Record<string, number | null | undefined>
type Row = {
  id: string
  name: string
  scenario: string
  expected: Record<string, { decision: string }>
  [system: string]: unknown
}

const SYSTEM_LABEL: Record<string, string> = {
  baseline: 'Standard agent (Nemotron, no DSL/arbiter)',
  deterministic: 'Unclaimed: rule engine only',
  unclaimed: 'Unclaimed: full (both lanes + arbiter)',
}
const SYSTEM_COLOR: Record<string, string> = { baseline: '#94a3b8', deterministic: '#9fd8c4', unclaimed: '#3fbf98' }
const ORDER = ['baseline', 'deterministic', 'unclaimed']

const METRICS: { key: string; label: string; fmt: (v: unknown) => string; better: 'high' | 'low' }[] = [
  { key: 'accuracy_decidable', label: 'Accuracy on decidable cases', fmt: pct, better: 'high' },
  { key: 'wrong_yes_rate', label: 'Wrong "yes" rate', fmt: pct, better: 'low' },
  { key: 'wrong_no_rate', label: 'Wrong "no" rate', fmt: pct, better: 'low' },
  { key: 'escalation_precision', label: 'Escalation precision', fmt: pct, better: 'high' },
  { key: 'escalation_recall', label: 'Escalation recall', fmt: pct, better: 'high' },
  { key: 'amount_accuracy', label: 'Amount accuracy (±£0.50)', fmt: pct, better: 'high' },
  { key: 'citation_validity', label: 'Citation validity', fmt: pct, better: 'high' },
  { key: 'wrong_yes', label: 'Wrong "yes" (count)', fmt: (v) => (typeof v === 'number' ? String(v) : '—'), better: 'low' },
  { key: 'wrong_no', label: 'Wrong "no" (count)', fmt: (v) => (typeof v === 'number' ? String(v) : '—'), better: 'low' },
  { key: 'latency_s_mean', label: 'Mean latency / household', fmt: (v) => (typeof v === 'number' ? `${v.toFixed(1)} s` : '—'), better: 'low' },
  { key: 'tokens_mean', label: 'Mean tokens / household', fmt: (v) => (typeof v === 'number' ? Math.round(v).toLocaleString('en-GB') : '—'), better: 'low' },
]

const CHART = ['accuracy_decidable', 'wrong_yes_rate', 'wrong_no_rate', 'escalation_recall']

function BarChart({ summary, systems }: { summary: Record<string, Metrics>; systems: string[] }) {
  const W = 720
  const H = 260
  const pad = { l: 44, b: 54, t: 14 }
  const groupW = (W - pad.l) / CHART.length
  const barW = Math.min(36, (groupW - 24) / systems.length)
  const y = (v: number) => H - pad.b - v * (H - pad.b - pad.t)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Bar chart comparing systems on accuracy, wrong yes, wrong no and escalation recall">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W} y1={y(t)} y2={y(t)} stroke="#e2e8f0" />
          <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#64748b">
            {t * 100}%
          </text>
        </g>
      ))}
      {CHART.map((m, gi) => {
        const x0 = pad.l + gi * groupW + (groupW - barW * systems.length) / 2
        return (
          <g key={m}>
            {systems.map((s, si) => {
              const v = summary[s]?.[m]
              const val = typeof v === 'number' ? v : 0
              return (
                <g key={s}>
                  <rect x={x0 + si * barW} y={y(val)} width={barW - 4} height={H - pad.b - y(val)} fill={SYSTEM_COLOR[s] ?? '#0b1a2b'} rx="2">
                    <title>{`${SYSTEM_LABEL[s] ?? s}: ${pct(v)}`}</title>
                  </rect>
                  <text x={x0 + si * barW + (barW - 4) / 2} y={y(val) - 3} textAnchor="middle" fontSize="10" fill="#0b1a2b">
                    {typeof v === 'number' ? `${Math.round(v * 100)}` : '–'}
                  </text>
                </g>
              )
            })}
            <text x={pad.l + gi * groupW + groupW / 2} y={H - pad.b + 18} textAnchor="middle" fontSize="12" fontWeight="600" fill="#0b1a2b">
              {METRICS.find((x) => x.key === m)?.label.replace(' on decidable cases', '').replace(' rate', '')}
            </text>
            <text x={pad.l + gi * groupW + groupW / 2} y={H - pad.b + 33} textAnchor="middle" fontSize="10" fill="#64748b">
              {METRICS.find((x) => x.key === m)?.better === 'high' ? 'higher is better' : 'lower is better'}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function decisionOf(row: Row, system: string, b: string): string | undefined {
  const s = row[system] as { benefits?: Record<string, { decision: string }> } | undefined
  return s?.benefits?.[b]?.decision
}

function Mistakes({ rows, systems }: { rows: Row[]; systems: string[] }) {
  const [system, setSystem] = useState(systems.includes('unclaimed') ? 'unclaimed' : systems[0])
  const items = useMemo(
    () =>
      rows.flatMap((r) =>
        BENEFITS.map((b) => ({ r, b, exp: r.expected?.[b]?.decision, got: decisionOf(r, system, b) })).filter((x) => x.got && x.exp && x.got !== x.exp),
      ),
    [rows, system],
  )
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h2 className="font-bold text-navy">Where each system differs from ground truth</h2>
        <label className="text-sm">
          <span className="mr-2 text-slate-600">System</span>
          <select value={system} onChange={(e) => setSystem(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1 text-sm">
            {systems.map((s) => (
              <option key={s} value={s}>
                {SYSTEM_LABEL[s] ?? s}
              </option>
            ))}
          </select>
        </label>
      </div>
      {items.length === 0 ? (
        <p className="p-4 text-sm text-slate-600">No differences.</p>
      ) : (
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Household</th>
                <th className="px-3 py-2">Scenario</th>
                <th className="px-3 py-2">Benefit</th>
                <th className="px-3 py-2">Expected</th>
                <th className="px-3 py-2">Got</th>
              </tr>
            </thead>
            <tbody>
              {items.map(({ r, b, exp, got }) => {
                const severe = got === 'yes'
                return (
                  <tr key={`${r.id}-${b}`} className="border-t border-slate-100">
                    <td className="px-3 py-1.5">
                      {r.id} <span className="text-slate-500">{r.name}</span>
                    </td>
                    <td className="px-3 py-1.5 text-slate-600">{r.scenario}</td>
                    <td className="px-3 py-1.5">{BENEFIT_SHORT[b]}</td>
                    <td className="px-3 py-1.5 font-mono">{exp}</td>
                    <td className={`px-3 py-1.5 font-mono font-bold ${severe ? 'text-red-700' : got === 'escalate' ? 'text-gold-dark' : 'text-slate-700'}`}>
                      {got}
                      {severe && ' (wrong yes)'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export default function Evaluation() {
  const ev = useAsync(() => api.evaluation(), [])
  if (ev.loading && !ev.data) return <Spinner label="Loading evaluation…" />
  if (ev.error instanceof ApiError && ev.error.status === 404) {
    return (
      <Card className="p-6">
        <h1 className="text-xl font-bold text-navy">Evaluation not run yet</h1>
        <p className="mt-2 text-sm text-slate-600">
          Run <code className="rounded bg-slate-100 px-1">python eval/run.py</code> to produce <code className="rounded bg-slate-100 px-1">eval/results.json</code>.
        </p>
      </Card>
    )
  }
  if (ev.error) return <ErrorBox error={ev.error} onRetry={ev.reload} />
  const data = ev.data as Record<string, unknown> | null
  const summary = (data?.summary ?? {}) as Record<string, Metrics>
  const systems = ORDER.filter((s) => summary[s] && Object.keys(summary[s]).length).concat(
    Object.keys(summary).filter((s) => !ORDER.includes(s) && Object.keys(summary[s] ?? {}).length),
  )
  const rows = (Array.isArray(data?.rows) ? data!.rows : []) as Row[]
  const n = (data?.n_households ?? data?.n) as number | undefined
  const best = (key: string, better: 'high' | 'low') => {
    const vals = systems.map((s) => summary[s]?.[key]).filter((v): v is number => typeof v === 'number')
    if (!vals.length) return null
    return better === 'high' ? Math.max(...vals) : Math.min(...vals)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-navy">Evaluation: Unclaimed vs a standard AI agent</h1>
        <p className="mt-1 text-sm text-slate-600">
          {n ?? '?'} synthetic households × {BENEFITS.length} benefits
          {data?.generated_at ? <> · run {formatDateTime(String(data.generated_at))}</> : null}. Ground truth comes from an independent plain-Python reference implementation of the policy
          text plus hand-labelled escalations. All numbers are read from <code className="rounded bg-slate-100 px-1">eval/results.json</code>, produced by a real run.
        </p>
      </div>

      {systems.length === 0 ? (
        <Card className="p-6 text-sm text-slate-600">The results file has no summary yet.</Card>
      ) : (
        <>
          <Card className="p-4">
            <div className="mb-2 flex flex-wrap gap-4 text-xs">
              {systems.map((s) => (
                <span key={s} className="flex items-center gap-1.5">
                  <span className="inline-block h-3 w-3 rounded-sm" style={{ background: SYSTEM_COLOR[s] ?? '#0b1a2b' }} />
                  {SYSTEM_LABEL[s] ?? s}
                </span>
              ))}
            </div>
            <BarChart summary={summary} systems={systems} />
          </Card>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th scope="col" className="px-4 py-2">Metric</th>
                    {systems.map((s) => (
                      <th key={s} scope="col" className="px-4 py-2 text-right">
                        {SYSTEM_LABEL[s] ?? s}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {METRICS.filter((m) => systems.some((s) => summary[s]?.[m.key] !== undefined)).map((m) => {
                    const b = best(m.key, m.better)
                    return (
                      <tr key={m.key} className="border-t border-slate-100">
                        <th scope="row" className="px-4 py-2 text-left font-semibold text-navy">
                          {m.label}
                        </th>
                        {systems.map((s) => {
                          const v = summary[s]?.[m.key]
                          const isBest = typeof v === 'number' && v === b && systems.length > 1
                          return (
                            <td key={s} className={`px-4 py-2 text-right tabular-nums ${isBest ? 'font-extrabold text-teal-dark' : 'text-slate-700'}`}>
                              {m.fmt(v)}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
          {rows.length > 0 && <Mistakes rows={rows} systems={systems} />}
        </>
      )}
    </div>
  )
}
