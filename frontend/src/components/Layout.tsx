import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../lib/useAsync'

function Badge({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${ok ? 'bg-teal/15 text-mint ring-teal/40' : 'bg-white/5 text-slate-300 ring-white/20'}`}>
      {children}
    </span>
  )
}

export default function Layout() {
  const health = useAsync(() => api.health(), [])
  const [toggling, setToggling] = useState(false)
  const h = health.data

  const toggleDemo = async () => {
    if (!h) return
    setToggling(true)
    try {
      health.setData(await api.setDemoMode(!h.demo_mode))
    } catch {
      health.reload()
    } finally {
      setToggling(false)
    }
  }

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm font-semibold ${isActive ? 'bg-teal text-navy' : 'text-slate-200 hover:bg-white/10'}`

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-gold focus:px-3 focus:py-1 focus:text-navy">
        Skip to content
      </a>
      <header className="bg-navy text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-3">
            <img src="/unclaimed_mark.png" alt="" className="h-10 w-10 rounded-lg" />
            <div>
              <div className="text-lg font-extrabold leading-tight tracking-tight">Unclaimed</div>
              <div className="text-xs text-mint">Find benefits. Prove decisions.</div>
            </div>
          </NavLink>
          <nav aria-label="Main" className="flex gap-1">
            <NavLink to="/" end className={navCls}>
              Dashboard
            </NavLink>
            <NavLink to="/evaluation" className={navCls}>
              Evaluation
            </NavLink>
            <NavLink to="/rules" className={navCls}>
              Rules & learning
            </NavLink>
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {health.loading && !h && <span className="text-xs text-slate-300">Checking backends…</span>}
            {health.error && <Badge ok={false}>⚠ Backend unreachable</Badge>}
            {h && (
              <>
                <Badge ok={h.backends.llm_available || h.demo_mode}>{h.backends.llm}</Badge>
                <Badge ok>Data: {h.backends.data}</Badge>
                <Badge ok>Memory: {h.backends.memory}</Badge>
                <label className="ml-1 flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-200">
                  <span>Demo mode</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={h.demo_mode}
                    disabled={toggling}
                    onClick={toggleDemo}
                    className={`relative h-6 w-11 rounded-full transition ${h.demo_mode ? 'bg-gold' : 'bg-slate-500'}`}
                  >
                    <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${h.demo_mode ? 'left-[22px]' : 'left-0.5'}`} />
                  </button>
                </label>
              </>
            )}
          </div>
        </div>
        {h?.demo_mode && (
          <div className="bg-gold px-4 py-1 text-center text-xs font-semibold text-navy">
            Demo mode: Nemotron answers come from the record/replay cache, so nothing waits on the API.
          </div>
        )}
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-500 sm:px-6">
        All data is synthetic. Unclaimed supports caseworkers and is not legal advice. Rules are simplified from GOV.UK guidance.
      </footer>
    </div>
  )
}
