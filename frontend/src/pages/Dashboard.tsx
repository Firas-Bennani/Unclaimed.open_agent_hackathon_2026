import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Button, Card, ErrorBox, Spinner, StatusPill } from '../components/ui'
import { BENEFITS, BENEFIT_SHORT, gbp } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { HouseholdSummary } from '../types'

const HERO = 'HH-001'

function Kpi({ label, value, tone = 'navy' }: { label: string; value: string | number; tone?: 'navy' | 'teal' | 'gold' | 'slate' }) {
  const color = { navy: 'text-navy', teal: 'text-teal-dark', gold: 'text-gold-dark', slate: 'text-slate-600' }[tone]
  return (
    <Card className="p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-extrabold ${color}`}>{value}</div>
    </Card>
  )
}

function Row({ h, hero }: { h: HouseholdSummary; hero: boolean }) {
  return (
    <tr className={`border-t border-slate-100 ${hero ? 'bg-mint-light' : 'hover:bg-slate-50'}`}>
      <td className="px-3 py-2.5">
        <Link to={`/households/${h.id}`} className="font-semibold text-navy underline-offset-2 hover:underline">
          {h.name}
        </Link>
        {hero && <span className="ml-2 rounded bg-gold px-1.5 py-0.5 text-[10px] font-bold uppercase text-navy">Demo case</span>}
        <div className="text-xs text-slate-500">
          {h.id} · {h.postcode}
        </div>
      </td>
      {BENEFITS.map((b) => (
        <td key={b} className="px-2 py-2.5">
          {h.statuses?.[b] ? <StatusPill status={h.statuses[b]} /> : <span className="text-xs text-slate-400">not assessed</span>}
        </td>
      ))}
      <td className="px-3 py-2.5 text-right font-semibold tabular-nums">{h.totals ? gbp(h.totals.monthly_found) : '—'}</td>
      <td className="px-3 py-2.5 text-right">
        <Link to={`/households/${h.id}`} className="rounded-md px-2 py-1 text-sm font-semibold text-teal-dark hover:bg-teal/10" aria-label={`Open ${h.name}`}>
          Open →
        </Link>
      </td>
    </tr>
  )
}

export default function Dashboard() {
  const list = useAsync(() => api.households(), [])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const data = list.data

  // poll while a bulk assessment runs
  useEffect(() => {
    if (!data?.bulk.running) return
    const t = setInterval(() => api.households().then(list.setData).catch(() => undefined), 2000)
    return () => clearInterval(t)
  }, [data?.bulk.running, list.setData])

  const rows = useMemo(() => {
    if (!data) return []
    const needle = q.trim().toLowerCase()
    const filtered = data.households.filter(
      (h) => !needle || h.name.toLowerCase().includes(needle) || h.id.toLowerCase().includes(needle) || h.postcode.toLowerCase().includes(needle),
    )
    return [...filtered.filter((h) => h.id === HERO), ...filtered.filter((h) => h.id !== HERO)]
  }, [data, q])

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      list.setData(await api.households())
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (list.loading && !data) return <Spinner label="Loading households…" />
  if (list.error && !data) return <ErrorBox error={list.error} onRetry={list.reload} />
  if (!data) return null

  const total = data.households.length
  const notAssessed = total - data.assessed

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-navy">Caseload</h1>
          <p className="text-sm text-slate-600">Each household is checked against four schemes. Every result links to the rule and the records behind it.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={busy || data.bulk.running} onClick={() => run(api.demoReset)} title="Clear memory, load the demo rule pack and re-assess everyone">
            Reset demo
          </Button>
          <Button disabled={busy || data.bulk.running} onClick={() => run(api.assessAll)}>
            {data.bulk.running ? `Assessing… ${data.bulk.done}/${data.bulk.total}` : notAssessed > 0 ? `Assess all (${notAssessed} pending)` : 'Re-assess all'}
          </Button>
        </div>
      </div>

      {actionError && <ErrorBox error={actionError} />}
      {data.bulk.running && (
        <div className="h-2 overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuemin={0} aria-valuemax={data.bulk.total} aria-valuenow={data.bulk.done}>
          <div className="h-full bg-teal transition-all" style={{ width: `${(100 * data.bulk.done) / Math.max(1, data.bulk.total)}%` }} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Households" value={`${data.assessed}/${total}`} />
        <Kpi label="£/month found" value={gbp(data.monthly_found, 0)} tone="teal" />
        <Kpi label="✅ Eligible" value={data.counts.eligible} tone="teal" />
        <Kpi label="❌ Not eligible" value={data.counts.not_eligible} tone="slate" />
        <Kpi label="⚠️ Needs info" value={data.counts.needs_info} tone="gold" />
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <h2 className="font-bold text-navy">Households</h2>
          <label className="flex items-center gap-2 text-sm">
            <span className="sr-only">Search households</span>
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search name, ID or postcode"
              className="w-64 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal focus:outline-none"
            />
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-3 py-2">Household</th>
                {BENEFITS.map((b) => (
                  <th key={b} scope="col" className="px-2 py-2">{BENEFIT_SHORT[b]}</th>
                ))}
                <th scope="col" className="px-3 py-2 text-right">£/month</th>
                <th scope="col" className="px-3 py-2"><span className="sr-only">Open</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <Row key={h.id} h={h} hero={h.id === HERO} />
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-slate-500">No households match "{q}".</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
