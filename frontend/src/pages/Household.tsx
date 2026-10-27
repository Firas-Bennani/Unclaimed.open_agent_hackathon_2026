import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import BenefitCard from '../components/BenefitCard'
import CorrectModal from '../components/CorrectModal'
import DraftModal from '../components/DraftModal'
import { FactItem } from '../components/Evidence'
import { Button, Card, ErrorBox, Spinner } from '../components/ui'
import { BENEFIT_LONG, STATUS_ICON, STATUS_LABEL, fieldLabel, formatDateTime, formatValue, gbp } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Assessment, Change, ResolvedFact } from '../types'

const STATE_CHIP: Record<ResolvedFact['state'], string> = {
  known: 'bg-teal/15 text-teal-dark',
  missing: 'bg-slate-200 text-slate-700',
  conflict: 'bg-red-100 text-red-800',
  stale: 'bg-gold/30 text-gold-dark',
}

function ChangesBanner({ changes, onDismiss }: { changes: Change[] | null; onDismiss: () => void }) {
  if (changes === null) return null
  return (
    <div role="status" className="flex items-start gap-3 rounded-lg border-2 border-teal bg-mint-light p-3">
      <div className="flex-1 text-sm">
        <div className="font-bold text-navy">Re-assessed with your answer</div>
        {changes.length === 0 ? (
          <p className="text-slate-700">No decision changed.</p>
        ) : (
          <ul className="mt-1 space-y-0.5">
            {changes.map((c) => (
              <li key={c.benefit}>
                <strong>{BENEFIT_LONG[c.benefit] ?? c.benefit}:</strong> {STATUS_ICON[c.from]} {STATUS_LABEL[c.from]} → {STATUS_ICON[c.to]} {STATUS_LABEL[c.to]}
                {c.to_amount !== null && c.to_amount !== c.from_amount && <> ({gbp(c.to_amount)}/month)</>}
              </li>
            ))}
          </ul>
        )}
      </div>
      <button type="button" onClick={onDismiss} className="text-xl leading-none text-slate-500 hover:text-navy" aria-label="Dismiss">
        ×
      </button>
    </div>
  )
}

function FactsTable({ a }: { a: Assessment }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const rows = Object.values(a.resolved).sort((x, y) => (x.state === 'known' ? 1 : 0) - (y.state === 'known' ? 1 : 0) || x.field.localeCompare(y.field))
  const byId = new Map(a.facts.map((f) => [f.id, f]))
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[700px] text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-3 py-2">Fact</th>
            <th scope="col" className="px-3 py-2">Value</th>
            <th scope="col" className="px-3 py-2">State</th>
            <th scope="col" className="px-3 py-2">How we know</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Fragment key={r.field}>
              <tr className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 font-semibold text-navy">{fieldLabel(r.field)}</td>
                <td className="px-3 py-2 font-mono">{r.state === 'known' ? formatValue(r.value, r.field) : '—'}</td>
                <td className="px-3 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${STATE_CHIP[r.state]}`}>{r.state}</span>
                </td>
                <td className="px-3 py-2 text-slate-600">
                  {r.explanation}
                  {r.fact_ids.length > 0 && (
                    <button
                      type="button"
                      className="ml-2 text-xs font-semibold text-teal-dark underline"
                      aria-expanded={expanded === r.field}
                      onClick={() => setExpanded(expanded === r.field ? null : r.field)}
                    >
                      {expanded === r.field ? 'hide records' : `${r.fact_ids.length} record${r.fact_ids.length > 1 ? 's' : ''}`}
                    </button>
                  )}
                </td>
              </tr>
              {expanded === r.field && (
                <tr>
                  <td colSpan={4} className="bg-slate-50 px-3 py-2">
                    <ul className="space-y-2">
                      {r.fact_ids.map((id) => byId.get(id)).filter(Boolean).map((f) => <FactItem key={f!.id} f={f!} />)}
                    </ul>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Household() {
  const { id = '' } = useParams()
  const state = useAsync(() => api.household(id), [id])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [changes, setChanges] = useState<Change[] | null>(null)
  const [correcting, setCorrecting] = useState<string | null>(null)
  const [drafting, setDrafting] = useState<string | null>(null)
  const a = state.data

  const updated = (next: Assessment, ch: Change[]) => {
    state.setData(next)
    setChanges(ch)
  }

  const answer = async (field: string, value: unknown, note: string) => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.correctFact(id, field, value, note)
      updated(r.assessment, r.changes)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const reassess = async () => {
    setBusy(true)
    setError(null)
    try {
      state.setData(await api.reassess(id))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (state.loading && !a) return <Spinner label="Gathering facts and checking eligibility…" />
  if (state.error && !a) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!a) return null

  const correctingDecision = a.decisions.find((d) => d.benefit === correcting)

  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link to="/" className="font-semibold text-teal-dark hover:underline">
          ← All households
        </Link>
      </nav>

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-navy">{a.household.name}</h1>
            <p className="text-sm text-slate-600">
              {a.household.id} · NI {a.household.ni} · {a.household.postcode} · born {a.household.dob}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Assessed {formatDateTime(a.assessed_at)} · rules {Object.entries(a.rule_versions).map(([b, v]) => `${BENEFIT_LONG[b]?.split(' ')[0] ?? b} ${v}`).join(' · ')}
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Found</div>
            <div className="text-3xl font-extrabold text-teal-dark">
              {gbp(a.totals.monthly_found)}
              <span className="text-base font-semibold text-slate-500"> /month</span>
            </div>
            {a.totals.one_off_found > 0 && <div className="text-sm text-slate-600">+ {gbp(a.totals.one_off_found, 0)} one-off</div>}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to={`/households/${id}/trace`} className="inline-flex items-center rounded-md bg-navy px-3 py-1.5 text-sm font-semibold text-white hover:bg-navy-2">
            View trace →
          </Link>
          <Button variant="secondary" onClick={reassess} disabled={busy}>
            {busy ? 'Working…' : 'Re-assess'}
          </Button>
          <a href={api.recordUrl(id)} download={`${id}-decision-record.json`} className="inline-flex items-center rounded-md px-3 py-1.5 text-sm font-semibold text-teal-dark hover:bg-teal/10">
            Download decision record
          </a>
        </div>
      </Card>

      <ChangesBanner changes={changes} onDismiss={() => setChanges(null)} />
      {error && <ErrorBox error={error} />}

      <div className="grid items-start gap-4 md:grid-cols-2">
        {a.decisions.map((d) => (
          <BenefitCard
            key={d.benefit}
            d={d}
            facts={a.facts}
            busy={busy}
            onAnswer={answer}
            onCorrect={() => setCorrecting(d.benefit)}
            onDraft={() => setDrafting(d.benefit)}
          />
        ))}
      </div>

      <Card>
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="font-bold text-navy">Facts</h2>
          <p className="text-xs text-slate-500">Merged from every source. Where sources conflict or a record is out of date, the fact is unknown, never silently chosen.</p>
        </div>
        <FactsTable a={a} />
      </Card>

      {a.corrections.length > 0 && (
        <Card className="p-4">
          <h2 className="font-bold text-navy">Caseworker corrections (memory)</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {a.corrections.map((c) => (
              <li key={c.id} className="text-slate-700">
                <span className="font-mono text-xs text-slate-500">{formatDateTime(c.created_at)}</span> · {c.kind}: <strong>{fieldLabel(c.target)}</strong> = {formatValue(c.value, c.target)}
                {c.note && <span className="text-slate-500">, "{c.note}"</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {correctingDecision && <CorrectModal assessment={a} decision={correctingDecision} onClose={() => setCorrecting(null)} onUpdated={updated} />}
      {drafting && <DraftModal householdId={id} benefit={drafting} onClose={() => setDrafting(null)} />}
    </div>
  )
}
