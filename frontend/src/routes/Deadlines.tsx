import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Module, Assignment } from '../lib/types'
import { daysUntil, fmt } from '../lib/dates'
import s from './Deadlines.module.css'

const FILTERS = ['upcoming', 'submitted', 'graded'] as const
type Filter = typeof FILTERS[number]

export default function Deadlines() {
  const [mods, setMods] = useState<Module[]>([])
  const [asgs, setAsgs] = useState<Assignment[]>([])
  const [filter, setFilter] = useState<Filter>('upcoming')

  async function refresh() { setAsgs(await api.assignments()) }
  useEffect(() => { api.modules().then(setMods); refresh() }, [])

  const view = asgs.filter(a => a.status === filter)
                   .sort((a,b) => (a.deadline_date+a.deadline_time).localeCompare(b.deadline_date+b.deadline_time))

  return (
    <>
      <h1 className={s.h1}>DEADLINES</h1>
      <div className={s.chips}>
        {FILTERS.map(f => (
          <button key={f} className={`${s.chip} ${filter===f ? s.on : ''}`} onClick={() => setFilter(f)}>{f.toUpperCase()}</button>
        ))}
      </div>
      <div className={s.grid}>
        {view.map(a => {
          const m = mods.find(x => x.code === a.module_code)
          const d = daysUntil(a.deadline_date, a.deadline_time)
          return (
            <article key={a.id} className={s.card} style={{ ['--accent' as any]: m?.color }}>
              <div className={s.top}>
                <span className={s.pill}>{a.module_code}</span>
                <select value={a.status}
                        onChange={e => api.patchAssignment(a.id, { status: e.target.value as Assignment['status'] }).then(refresh)}>
                  {FILTERS.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
              <h3 className={s.title}>{a.assignment_title}</h3>
              <div className={s.type}>{a.assignment_type}</div>
              <p className={s.desc}>{a.description}</p>
              <div className={s.foot}>
                <div><span className={s.lbl}>DEADLINE</span><span>{fmt(a.deadline_date, a.deadline_time)} (T-{d})</span></div>
                <div><span className={s.lbl}>WEIGHT</span><span>{a.weighting_percent}%</span></div>
                <div><span className={s.lbl}>FORMAT</span><span>{a.word_limit_or_size}</span></div>
                <div><span className={s.lbl}>ROUTE</span><span>{a.submission_method}</span></div>
              </div>
            </article>
          )
        })}
        {!view.length && <div className={s.none}>No {filter} assignments.</div>}
      </div>
    </>
  )
}
