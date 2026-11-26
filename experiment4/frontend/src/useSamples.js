import { useEffect, useState } from 'react'
import { api, sampleUrl } from './api/client.js'

let cache = null
export function useSamples(online) {
  const [samples, setSamples] = useState(cache || [])
  useEffect(() => {
    if (!online || cache) return
    api.samples().then((r) => {
      cache = r.result.samples.map((s) => ({ id: s.id, src: sampleUrl(s.id) }))
      setSamples(cache)
    }).catch(() => {})
  }, [online])
  return samples
}
