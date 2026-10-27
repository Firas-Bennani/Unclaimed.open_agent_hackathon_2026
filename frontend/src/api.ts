import type {
  Assessment,
  DecisionCorrectionResult,
  Draft,
  FactCorrectionResult,
  Health,
  HouseholdList,
  Patch,
  RuleInfo,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the Unclaimed server. Is the backend running on port 8000?')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/health'),
  households: () => request<HouseholdList>('/api/households'),
  household: (id: string) => request<Assessment>(`/api/households/${id}`),
  reassess: (id: string) => post<Assessment>(`/api/households/${id}/assess`),
  correctFact: (id: string, field: string, value: unknown, note: string) =>
    post<FactCorrectionResult>(`/api/households/${id}/facts`, { field, value, note }),
  correctDecision: (id: string, benefit: string, expected: 'eligible' | 'not_eligible', explanation: string) =>
    post<DecisionCorrectionResult>(`/api/households/${id}/decision-corrections`, { benefit, expected, explanation }),
  draft: (id: string, benefit: string) => request<Draft>(`/api/households/${id}/drafts/${benefit}`),
  recordUrl: (id: string) => `/api/households/${id}/record`,
  patches: () => request<Patch[]>('/api/patches'),
  rules: () => request<Record<string, RuleInfo>>('/api/rules'),
  evaluation: () => request<Record<string, unknown>>('/api/eval'),
  setDemoMode: (demo_mode: boolean) => post<Health>('/api/settings/demo-mode', { demo_mode }),
  assessAll: () => post<HouseholdList['bulk']>('/api/assess-all'),
  demoReset: () => post<HouseholdList>('/api/demo/reset'),
}
