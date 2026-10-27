export type Status = 'eligible' | 'not_eligible' | 'needs_info'
export type Tri = 'TRUE' | 'FALSE' | 'UNKNOWN'
export type SourceName = 'dwp' | 'housing' | 'council' | 'notes' | 'derived' | 'caseworker'

export interface Backends {
  llm: string
  data: string
  memory: string
  models?: { reasoning: string; extraction: string }
  llm_available?: boolean
}

export interface Health {
  status: string
  backends: Backends
  demo_mode: boolean
  llm_mode: string
  households: number
}

export interface Totals {
  eligible: number
  not_eligible: number
  needs_info: number
  monthly_found: number
  one_off_found: number
}

export interface HouseholdRef {
  id: string
  name: string
  ni: string
  dob: string
  postcode: string
  partner_ni: string | null
}

export interface HouseholdSummary extends HouseholdRef {
  assessed: boolean
  totals?: Totals
  statuses?: Record<string, Status>
  assessed_at?: string
}

export interface HouseholdList {
  households: HouseholdSummary[]
  counts: { eligible: number; not_eligible: number; needs_info: number }
  monthly_found: number
  one_off_found: number
  assessed: number
  bulk: { running: boolean; done: number; total: number }
}

export interface Fact {
  id: string
  field: string
  value: unknown
  source: SourceName
  source_label: string
  record_id: string
  as_of: string | null
  extraction_method: string
  confidence: number
  quote: string | null
  note: string | null
  status: 'active' | 'stale' | 'superseded'
}

export interface ResolvedFact {
  field: string
  value: unknown
  state: 'known' | 'missing' | 'conflict' | 'stale'
  fact_ids: string[]
  explanation: string
}

export interface SourceHit {
  source: string
  label: string
  backend: string
  query: string
  records: number
  latency_ms: number
  ok: boolean
  error: string | null
  tokens?: number
  llm_latency_s?: number
}

export interface TraceNode {
  kind: 'all' | 'any' | 'not' | 'leaf'
  result: Tri
  clause?: string | null
  children?: TraceNode[]
  subject?: string
  subject_kind?: 'field' | 'derived'
  op?: string
  left?: unknown
  right?: unknown
  fact_ids?: string[]
}

export interface Clause {
  id: string
  text: string
  source_url: string
  cited_by?: string
}

export interface Decision {
  benefit: string
  benefit_name: string
  status: Status
  amount_weekly: number | null
  amount_monthly: number | null
  amount_one_off: number | null
  amount_is_minimum: boolean
  already_receiving: boolean
  reason: string
  question: string | null
  question_field: string | null
  escalation_cause: string | null
  rule_version: string
  clauses: Clause[]
  fact_ids: string[]
  deterministic: {
    status: Tri
    amount: number | null
    amount_unit?: string
    trace: TraceNode
    derived: Record<string, { value: unknown; clause: string; fields: string[]; fact_ids: string[] }>
    unknown_fields: { field: string; reason: string }[]
  }
  reasoning: {
    status?: 'ok' | 'invalid' | 'unavailable'
    decision?: string
    weekly_amount?: number | null
    clause_ids?: string[]
    fact_ids?: string[]
    reason?: string
    missing_info?: string | null
    error?: string
  }
  arbiter: {
    status: Status
    reason: string
    question: string | null
    cause: string | null
    agreement: boolean | null
  }
}

export interface Correction {
  id: string
  household_id: string
  kind: string
  target: string
  value: unknown
  note: string
  created_at: string
}

export interface Assessment {
  run_id: string
  household: HouseholdRef
  assessed_at: string
  backends: Backends
  sources: SourceHit[]
  facts: Fact[]
  resolved: Record<string, ResolvedFact>
  decisions: Decision[]
  totals: Totals
  rule_versions: Record<string, string>
  reasoning_meta: { model?: string; source?: string; tokens?: number; latency_s?: number; attempts?: number }
  timing_ms: Record<string, number>
  corrections: Correction[]
}

export interface Change {
  benefit: string
  from: Status
  to: Status
  from_amount: number | null
  to_amount: number | null
}

export interface Patch {
  id: string
  benefit: string
  household_id?: string
  status: 'accepted' | 'rejected' | 'failed'
  reason?: string
  rationale?: string
  ops?: { op: string; path: string; value: unknown }[]
  from_version?: string
  to_version?: string
  explanation?: string
  gate?: {
    before: { passed: number; total: number }
    after: { passed: number; total: number }
    regressions: string[]
    fixes: string[]
    target_fixed: boolean
  }
}

export interface FactCorrectionResult {
  assessment: Assessment
  changes: Change[]
}

export interface DecisionCorrectionResult {
  patch: Patch
  assessment: Assessment | null
  changes: Change[]
}

export interface Draft {
  benefit: string
  title: string
  markdown: string
}

export interface RuleInfo {
  version: string
  name: string
  origin: string
  rule: unknown
}
