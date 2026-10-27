import { useState } from 'react'
import type { Decision, Fact } from '../types'
import { fieldLabel, gbp } from '../lib/format'
import { ValueInput } from './AnswerBox'
import { ClauseList, FactList } from './Evidence'
import { Button, Card, StatusPill } from './ui'

const BORDER = { eligible: 'border-t-teal', not_eligible: 'border-t-slate-300', needs_info: 'border-t-gold' }

function Amount({ d }: { d: Decision }) {
  if (d.status !== 'eligible') return null
  if (d.amount_one_off !== null) {
    return (
      <div>
        <div className="text-3xl font-extrabold text-teal-dark">{gbp(d.amount_one_off, 0)}</div>
        <div className="text-xs text-slate-500">one-off discount</div>
      </div>
    )
  }
  if (d.amount_monthly === null) return <div className="text-sm text-slate-500">Amount set by the council</div>
  return (
    <div>
      <div className="text-3xl font-extrabold text-teal-dark">
        {d.amount_is_minimum && <span className="mr-1 text-base font-semibold">at least</span>}
        {gbp(d.amount_monthly)}
        <span className="text-base font-semibold text-slate-500"> /month</span>
      </div>
      <div className="text-xs text-slate-500">{gbp(d.amount_weekly)} a week</div>
    </div>
  )
}

export default function BenefitCard({
  d,
  facts,
  busy,
  onAnswer,
  onCorrect,
  onDraft,
}: {
  d: Decision
  facts: Fact[]
  busy: boolean
  onAnswer: (field: string, value: unknown, note: string) => void
  onCorrect: () => void
  onDraft: () => void
}) {
  const [open, setOpen] = useState(false)
  const drawerId = `why-${d.benefit}`
  return (
    <Card className={`flex flex-col border-t-4 ${BORDER[d.status]}`}>
      <div className="flex-1 space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-bold text-navy">{d.benefit_name}</h3>
          <StatusPill status={d.status} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Amount d={d} />
          {d.already_receiving && <span className="rounded bg-mint px-2 py-0.5 text-xs font-semibold text-navy">Already receiving</span>}
        </div>
        <p className="text-sm text-slate-700">{d.reason}</p>

        {d.status === 'needs_info' && d.question && (
          <div className="rounded-lg border-2 border-gold bg-gold/10 p-3">
            <div className="text-xs font-bold uppercase tracking-wide text-gold-dark">Ask the claimant (one question resolves this)</div>
            <p className="mt-1 font-semibold text-navy">{d.question}</p>
            {d.question_field && (
              <div className="mt-2">
                <div className="mb-1 text-xs text-slate-600">Answer sets: {fieldLabel(d.question_field)}</div>
                <ValueInput field={d.question_field} busy={busy} onSubmit={(v, n) => onAnswer(d.question_field!, v, n)} />
              </div>
            )}
          </div>
        )}

        {open && (
          <div id={drawerId} className="space-y-3 rounded-lg bg-slate-50/60 pt-1">
            <div>
              <h4 className="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">Rule clauses</h4>
              <ClauseList clauses={d.clauses} />
            </div>
            <div>
              <h4 className="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">Source records</h4>
              <FactList ids={d.fact_ids} facts={facts} />
            </div>
            <p className="text-xs text-slate-500">
              Rule version {d.rule_version}
              {d.arbiter.agreement === true && ' · both independent checks agree'}
              {d.escalation_cause && ` · ${d.status === 'needs_info' ? 'escalated' : 'note'}: ${d.escalation_cause}`}
            </p>
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-2 border-t border-slate-100 px-4 py-2.5">
        <Button variant="secondary" aria-expanded={open} aria-controls={drawerId} onClick={() => setOpen((o) => !o)}>
          {open ? 'Hide why' : 'Why?'}
        </Button>
        <Button variant="ghost" onClick={onCorrect}>
          Correct this
        </Button>
        {d.status === 'eligible' && !d.already_receiving && (
          <Button variant="gold" className="ml-auto" onClick={onDraft}>
            Draft application
          </Button>
        )}
      </div>
    </Card>
  )
}
