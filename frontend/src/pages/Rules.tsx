import { api } from '../api'
import PatchResult from '../components/PatchResult'
import { Card, ErrorBox, Spinner } from '../components/ui'
import { BENEFIT_LONG } from '../lib/format'
import { useAsync } from '../lib/useAsync'

export default function Rules() {
  const rules = useAsync(() => api.rules(), [])
  const patches = useAsync(() => api.patches(), [])
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-navy">Rules & learning</h1>
        <p className="text-sm text-slate-600">
          Rules are compiled by Nemotron from GOV.UK text into a versioned, cited DSL. A caseworker's decision correction becomes a candidate patch that goes live
          only if the regression suite shows no regressions.
        </p>
      </div>
      <Card>
        <h2 className="border-b border-slate-200 px-4 py-3 font-bold text-navy">Active rule versions</h2>
        {rules.loading && <Spinner />}
        {rules.error && (
          <div className="p-4">
            <ErrorBox error={rules.error} onRetry={rules.reload} />
          </div>
        )}
        {rules.data && (
          <ul className="divide-y divide-slate-100">
            {Object.entries(rules.data).map(([b, r]) => (
              <li key={b} className="px-4 py-3">
                <details>
                  <summary className="flex cursor-pointer flex-wrap items-center gap-3">
                    <span className="font-semibold text-navy">{r.name || BENEFIT_LONG[b]}</span>
                    <span className="rounded bg-navy px-1.5 py-0.5 font-mono text-xs text-white">{r.version}</span>
                    <span className={`text-xs ${r.origin === 'compiled' ? 'text-slate-500' : 'font-semibold text-gold-dark'}`}>{r.origin}</span>
                  </summary>
                  <pre className="mt-2 max-h-96 overflow-auto rounded bg-slate-900 p-3 text-xs text-mint">{JSON.stringify(r.rule, null, 2)}</pre>
                </details>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <h2 className="border-b border-slate-200 px-4 py-3 font-bold text-navy">Rule patches</h2>
        {patches.loading && <Spinner />}
        {patches.error && (
          <div className="p-4">
            <ErrorBox error={patches.error} onRetry={patches.reload} />
          </div>
        )}
        {patches.data && patches.data.length === 0 && <p className="p-4 text-sm text-slate-600">No patches yet. Use "Correct this → The decision is wrong" on a household.</p>}
        <div className="space-y-4 p-4">
          {patches.data?.map((p) => (
            <div key={p.id} className="rounded-lg border border-slate-200 p-3">
              <div className="mb-2 text-xs text-slate-500">
                Patch {p.id} · from household {p.household_id}
                {p.explanation && <> · caseworker: "{p.explanation}"</>}
              </div>
              <PatchResult patch={p} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
