import { useState } from 'react'
import { BOOL_FIELDS, NUMBER_FIELDS } from '../lib/format'
import { Button } from './ui'

/** Value input adapted to the field type; calls onSubmit(value, note). */
export function ValueInput({
  field,
  busy,
  submitLabel = 'Save answer',
  onSubmit,
}: {
  field: string
  busy: boolean
  submitLabel?: string
  onSubmit: (value: unknown, note: string) => void
}) {
  const [bool, setBool] = useState<boolean | null>(null)
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const isBool = BOOL_FIELDS.has(field)
  const isNum = NUMBER_FIELDS.has(field)

  const value: unknown = isBool ? bool : isNum ? (text.trim() === '' ? null : Number(text)) : text.trim() || null
  const valid = value !== null && !(isNum && Number.isNaN(value as number))

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (valid) onSubmit(value, note)
      }}
    >
      {isBool ? (
        <div className="flex gap-2" role="radiogroup" aria-label="Answer">
          {[true, false].map((v) => (
            <button
              key={String(v)}
              type="button"
              role="radio"
              aria-checked={bool === v}
              onClick={() => setBool(v)}
              className={`rounded-md px-4 py-1.5 text-sm font-semibold ring-1 ${bool === v ? 'bg-navy text-white ring-navy' : 'bg-white text-navy ring-slate-300 hover:bg-slate-50'}`}
            >
              {v ? 'Yes' : 'No'}
            </button>
          ))}
        </div>
      ) : (
        <input
          type={isNum ? 'number' : 'text'}
          step="any"
          inputMode={isNum ? 'decimal' : undefined}
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="Answer"
          placeholder={field === 'care_need_months' ? 'Number of months, e.g. 7' : isNum ? 'Enter a number' : 'Enter a value'}
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal focus:outline-none"
        />
      )}
      <input
        type="text"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        aria-label="Note (optional)"
        placeholder="Note, e.g. how you know this (optional)"
        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal focus:outline-none"
      />
      <Button type="submit" disabled={!valid || busy}>
        {busy ? 'Re-assessing…' : submitLabel}
      </Button>
    </form>
  )
}
