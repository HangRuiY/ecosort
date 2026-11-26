import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client.js'

export function useHealth(interval = 10000) {
  const [health, setHealth] = useState(null)
  const [online, setOnline] = useState(null)
  const refresh = useCallback(async () => {
    try {
      const r = await api.health()
      setHealth(r.result)
      setOnline(true)
    } catch {
      setOnline(false)
    }
  }, [])
  useEffect(() => {
    refresh()
    const t = setInterval(refresh, interval)
    return () => clearInterval(t)
  }, [refresh, interval])
  return { health, online, refresh }
}
