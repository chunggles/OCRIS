import { useState, useEffect, useCallback } from 'react'
import { errorMessage } from './format'

// Runs apiFn on mount and whenever apiFn changes (wrap it in useCallback with its inputs).
export function useFetch(apiFn) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const refetch = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      setData(await apiFn())
    } catch (e) {
      setError(errorMessage(e, 'Failed to load.'))
    } finally {
      setLoading(false)
    }
  }, [apiFn])

  useEffect(() => { refetch() }, [refetch])

  return { data, loading, error, refetch }
}
