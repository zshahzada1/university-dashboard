import { useEffect, useState } from 'react'
export function useHashRoute(): string {
  const [h, setH] = useState(() => location.hash || '#/')
  useEffect(() => {
    const onHash = () => setH(location.hash || '#/')
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return h
}