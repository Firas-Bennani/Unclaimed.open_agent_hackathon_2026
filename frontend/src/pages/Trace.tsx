import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import TraceTree from '../components/TraceTree'
import { Card, ErrorBox, Spinner, StatusPill } from '../components/ui'
import { fieldLabel, formatValue, gbp } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Assessment, Decision } from '../types'

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="relative pl-10">
      <div className="absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full bg-navy text-sm font-bold text-gold">{n}</div>
      <h2 className="mb-2 text-lg font-bold text-navy">{title}</h2>
      {children}
    </section>
  )
}

function Sources({ a }: { a: Assessment }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {a.sources.map((s) => (
        <Card key={s.source} className={`p-3 ${s.ok ? '' : 'border-red-300 bg-red-50'}`}>
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-bold text-navy">{s.label}</span>
            <span className={`text-xs font-bold ${s.ok ? 'text-teal-dark' : 'text-red-700'}`}>{s.ok ? '✓' : '✗ failed'}</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">backend: {s.backend}</div>
          <code className="mt-1 block break-words rounded bg-slate-100 px-1.5 py-1 text-[11px] text-slate-700">{s.query}</code>
          <div className="mt-1 text-xs text-slate-600">
            {s.records} record{s.records === 1 ? '' : 's'} · {Math.round(s.latency_ms)} ms
            {s.tokens ? ` · ${s.tokens} tokens` : ''}
          </div>
          {s.error && <p className="mt-1 text-xs text-red-700">{s.error}</p>}
        </Card>
      ))}
    </div>
  )
}

function FactGraph({ a }: { a: Assessment }) {
  const rows = Object.values(a.resolved)
  const flagged = rows.filter((r) => r.state !== 'known')
  return (
    <Card className="p-3">
      <p className="text-sm text-slate-600">
        {a.facts.length} facts from {a.sources.filter((s) => s.records > 0).length} sources resolved into {rows.length} fields:{' '}
        <strong className="text-teal-dark">{rows.length - flagged.length} known</strong>, <strong className="text-gold-dark">{flagged.length} unknown</strong>.
      </p>
      {flagged.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {flagged.map((r) => (
            <li key={r.field}>
              <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-bold ${r.state === 'conflict' ? 'bg-red-100 text-red-800' : r.state === 'stale' ? 'bg-gold/30 text-gold-dark' : 'bg-slate-200 text-slate-700'}`}>
                {r.state}
              </span>
              <strong>{fieldLabel(r.field)}</strong>: <span className="text-slate-600">{r.explanation}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function LaneCompare({ d }: { d: Decision }) {
  const r = d.reasoning
  const det = d.deterministic
  const laneTone = r.status === 'ok' ? 'text-teal-dark' : r.status === 'invalid' ? 'text-red-700' : 'text-slate-500'
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2">
        <h3 className="font-bold text-navy">{d.benefit_name}</h3>
        <span className="text-xs text-slate-500">rule {d.rule_version}</span>
      </div>
      <div className="grid gap-0 lg:grid-cols-[1fr_1fr_0.8fr]">
        <div className="border-b border-slate-100 p-4 lg:border-b-0 lg:border-r">
          <div className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">3a · Deterministic lane (Kleene logic)</div>
          <div className="mb-2 text-sm">
            Result <strong>{det.status}</strong>
            {det.amount !== null && <> · {gbp(det.amount)}{det.amount_unit === 'weekly' ? '/week' : ' one-off'}</>}
          </div>
          <TraceTree node={det.trace} />
          {Object.keys(det.derived).length > 0 && (
            <div className="mt-2 text-xs text-slate-600">
              <div className="font-semibold">Derived values</div>
              {Object.entries(det.derived).map(([k, v]) => (
                <div key={k} className="font-mono">
                  {k} = {formatValue(v.value)} <span className="text-slate-400">({v.clause})</span>
                </div>
              ))}
            </div>
          )}
          {det.unknown_fields.length > 0 && (
            <div className="mt-2 text-xs text-gold-dark">Unknown: {det.unknown_fields.map((u) => fieldLabel(u.field)).join(', ')}</div>
          )}
        </div>
        <div className="border-b border-slate-100 p-4 lg:border-b-0 lg:border-r">
          <div className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">3b · Reasoning lane (Nemotron)</div>
          <div className={`text-sm font-semibold ${laneTone}`}>
            {r.status === 'ok' ? 'Valid answer' : r.status === 'invalid' ? 'Invalid: rejected' : 'Unavailable'}
            {r.decision && <span className="ml-1 text-navy">· {r.decision.replace(/_/g, ' ')}</span>}
            {typeof r.weekly_amount === 'number' && <span className="text-slate-600"> · {gbp(r.weekly_amount)}</span>}
          </div>
          {r.reason && <p className="mt-1 text-sm italic text-slate-700">"{r.reason}"</p>}
          {r.missing_info && <p className="mt-1 text-xs text-gold-dark">Missing: {r.missing_info}</p>}
          {r.error && <p className="mt-1 text-xs text-red-700">{r.error}</p>}
          {(r.clause_ids?.length ?? 0) > 0 && (
            <div className="mt-2 flex flex-wrap gap-1 text-xs">
              <span className="text-slate-500">clauses:</span>
              {r.clause_ids!.map((c) => (
                <span key={c} className="rounded bg-navy px-1 font-mono text-[10px] font-bold text-white">{c}</span>
              ))}
            </div>
          )}
          {(r.fact_ids?.length ?? 0) > 0 && <div className="mt-1 text-xs text-slate-500">{r.fact_ids!.length} facts cited, all verified to exist</div>}
        </div>
        <div className="bg-mint-light/60 p-4">
          <div className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">4 · Arbiter</div>
          <StatusPill status={d.status} />
          <div className="mt-2 text-sm">
            {d.arbiter.agreement === true && <span className="font-semibold text-teal-dark">Lanes agree</span>}
            {d.arbiter.agreement === false && <span className="font-semibold text-red-700">Lanes disagree</span>}
            {d.arbiter.agreement === null && <span className="text-slate-500">No comparison</span>}
          </div>
          {d.arbiter.cause && <p className="mt-1 text-xs text-slate-600">Cause: {d.arbiter.cause}</p>}
          {d.question && <p className="mt-2 rounded bg-gold/20 p-2 text-xs font-semibold text-navy">Q: {d.question}</p>}
        </div>
      </div>
    </Card>
  )
}

export default function Trace() {
  const { id = '' } = useParams()
  const state = useAsync(() => api.household(id), [id])
  const a = state.data
  if (state.loading && !a) return <Spinner label="Loading trace…" />
  if (state.error && !a) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!a) return null
  const m = a.reasoning_meta
  return (
    <div className="space-y-8">
      <div>
        <Link to={`/households/${id}`} className="text-sm font-semibold text-teal-dark hover:underline">
          ← Back to {a.household.name}
        </Link>
        <h1 className="mt-1 text-2xl font-extrabold text-navy">How the decision was made</h1>
        <p className="text-sm text-slate-600">
          Run {a.run_id} · total {a.timing_ms.total} ms (harness {a.timing_ms.harness} ms, rules {a.timing_ms.deterministic} ms, Nemotron {a.timing_ms.reasoning} ms)
          {m.model && <> · {m.model} · {m.tokens ?? 0} tokens · {m.source === 'cache' ? 'replayed from cache' : m.source}</>}
        </p>
      </div>
      <Step n={1} title="Sources hit: data harness">
        <Sources a={a} />
      </Step>
      <Step n={2} title="Fact graph: provenance, conflicts, staleness">
        <FactGraph a={a} />
      </Step>
      <Step n={3} title="Two independent lanes, then the arbiter">
        <div className="space-y-4">
          {a.decisions.map((d) => (
            <LaneCompare key={d.benefit} d={d} />
          ))}
        </div>
      </Step>
    </div>
  )
}
