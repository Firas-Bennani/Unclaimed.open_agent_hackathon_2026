import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: Error | null
  loading: boolean
  reload: () => void
  setData: (d: T) => void
}

/** Runs an async loader on mount / when deps change; exposes reload + local overwrite. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps)

  const reload = useCallback(() => {
    const id = ++seq.current
    setLoading(true)
    setError(null)
    run()
      .then((d) => {
        if (id === seq.current) setData(d)
      })
      .catch((e: Error) => {
        if (id === seq.current) setError(e)
      })
      .finally(() => {
        if (id === seq.current) setLoading(false)
      })
  }, [run])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, loading, reload, setData }
}
