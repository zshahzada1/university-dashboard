import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { openFile } from '../lib/openFile'
import type { SearchHit, Module } from '../lib/types'
import s from './Resources.module.css'

export default function Resources() {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [mods, setMods] = useState<Module[]>([])

  useEffect(() => { api.modules().then(setMods) }, [])
  useEffect(() => {
    if (!q.trim()) { setHits([]); return }
    const id = setTimeout(() => api.search(q).then(setHits), 200)
    return () => clearTimeout(id)
  }, [q])

  const byModule: Record<string, SearchHit[]> = {}
  for (const h of hits) (byModule[h.module] ??= []).push(h)

  return (
    <>
      <h1 className={s.h1}>RESOURCES</h1>
      <input className={s.in} placeholder="Filename or path…" value={q} onChange={e => setQ(e.target.value)} autoFocus />
      {!q.trim() && <div className={s.empty}>Type to search filenames across all modules.</div>}
      {Object.entries(byModule).map(([code, list]) => {
        const m = mods.find(x => x.code === code)
        return (
          <section key={code} className={s.sec}>
            <h2 className={s.h2} style={{ color: m?.color }}>{code} · {m?.name}</h2>
            <ul className={s.list}>
              {list.map(h => (
                <li key={h.rel_path}>
                  <button onClick={() => openFile(h.rel_path)}>{h.name}</button>
                  <span className={s.path}>{h.rel_path}</span>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
      {q.trim() && hits.length === 0 && <div className={s.empty}>No matches.</div>}
    </>
  )
}
