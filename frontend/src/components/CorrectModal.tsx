import { useState } from 'react'
import { api } from '../api'
import type { Assessment, Change, Decision, Patch } from '../types'
import { fieldLabel, formatValue } from '../lib/format'
import { ValueInput } from './AnswerBox'
import { Button, ErrorBox, Modal } from './ui'
import PatchResult from './PatchResult'

export default function CorrectModal({
  assessment,
  decision,
  onClose,
  onUpdated,
}: {
  assessment: Assessment
  decision: Decision
  onClose: () => void
  onUpdated: (a: Assessment, changes: Change[]) => void
}) {
  const [tab, setTab] = useState<'fact' | 'decision'>('fact')
  const fields = Object.values(assessment.resolved).sort((a, b) => a.field.localeCompare(b.field))
  const [field, setField] = useState(decision.question_field ?? fields[0]?.field ?? '')
  const [expected, setExpected] = useState<'eligible' | 'not_eligible'>(decision.status === 'eligible' ? 'not_eligible' : 'eligible')
  const [explanation, setExplanation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [patch, setPatch] = useState<Patch | null>(null)
  const current = assessment.resolved[field]
  const id = assessment.household.id

  const submitFact = async (value: unknown, note: string) => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.correctFact(id, field, value, note)
      onUpdated(r.assessment, r.changes)
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const submitDecision = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.correctDecision(id, decision.benefit, expected, explanation)
      setPatch(r.patch)
      if (r.assessment) onUpdated(r.assessment, r.changes)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const tabCls = (t: string) =>
    `rounded-t-md px-4 py-2 text-sm font-semibold ${tab === t ? 'border-b-2 border-teal text-navy' : 'text-slate-500 hover:text-navy'}`

  return (
    <Modal title={`Correct ${decision.benefit_name}`} onClose={onClose} wide={Boolean(patch)}>
      <div role="tablist" className="mb-4 flex gap-2 border-b border-slate-200">
        <button type="button" role="tab" aria-selected={tab === 'fact'} className={tabCls('fact')} onClick={() => setTab('fact')}>
          A fact is wrong or missing
        </button>
        <button type="button" role="tab" aria-selected={tab === 'decision'} className={tabCls('decision')} onClick={() => setTab('decision')}>
          The decision is wrong
        </button>
      </div>
      {error && (
        <div className="mb-3">
          <ErrorBox error={error} />
        </div>
      )}
      {tab === 'fact' ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Your correction is stored with caseworker provenance, overrides the source records for this household, and the household is re-assessed.
          </p>
          <label className="block text-sm font-semibold text-navy">
            Fact
            <select
              value={field}
              onChange={(e) => setField(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm font-normal"
            >
              {fields.map((f) => (
                <option key={f.field} value={f.field}>
                  {fieldLabel(f.field)} ({f.state === 'known' ? formatValue(f.value, f.field) : f.state})
                </option>
              ))}
            </select>
          </label>
          {current && <p className="text-xs text-slate-500">Currently: {current.explanation || current.state}</p>}
          <ValueInput key={field} field={field} busy={busy} submitLabel="Save correction and re-assess" onSubmit={submitFact} />
        </div>
      ) : patch ? (
        <PatchResult patch={patch} />
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Nemotron proposes a rule patch from your explanation. The patch is only accepted if the regression suite (every labelled household plus the rule
            examples) shows <strong>no regressions</strong>.
          </p>
          <fieldset>
            <legend className="text-sm font-semibold text-navy">The correct decision is</legend>
            <div className="mt-1 flex gap-2">
              {(['eligible', 'not_eligible'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={expected === v}
                  onClick={() => setExpected(v)}
                  className={`rounded-md px-4 py-1.5 text-sm font-semibold ring-1 ${expected === v ? 'bg-navy text-white ring-navy' : 'bg-white ring-slate-300'}`}
                >
                  {v === 'eligible' ? '✅ Eligible' : '❌ Not eligible'}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="block text-sm font-semibold text-navy">
            Why? Cite the rule or evidence
            <textarea
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              rows={3}
              placeholder="e.g. The 2026-27 Guarantee Credit amount is £238 a week for a single person, not £227.10."
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal"
            />
          </label>
          <Button disabled={busy || explanation.trim().length < 5} onClick={submitDecision}>
            {busy ? 'Proposing patch and running regression suite…' : 'Propose rule patch'}
          </Button>
        </div>
      )}
    </Modal>
  )
}
