import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Module, Assignment, Task } from '../lib/types'
import CountdownCard from '../components/CountdownCard'
import StatStrip from '../components/StatStrip'
import { daysUntil } from '../lib/dates'
import s from './Home.module.css'

export default function Home() {
  const [modules, setModules] = useState<Module[]>([])
  const [asgs, setAsgs]       = useState<Assignment[]>([])
  const [tasks, setTasks]     = useState<Task[]>([])

  useEffect(() => {
    Promise.all([api.modules(), api.assignments(), api.tasks('today')])
      .then(([m, a, k]) => { setModules(m); setAsgs(a); setTasks(k) })
  }, [])

  const upcoming = asgs.filter(a => a.status === 'upcoming')
                       .sort((a, b) => (a.deadline_date+a.deadline_time).localeCompare(b.deadline_date+b.deadline_time))
  const next = upcoming[0]

  return (
    <>
      <header className={s.head}>
        <h1>Dashboard</h1>
        <div className={s.date}>{new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>
      </header>

      <StatStrip stats={[
        { label: 'Tasks today',   value: String(tasks.length),                                               sub: tasks.filter(t=>!t.done).length + ' open' },
        { label: 'Next deadline', value: next ? `T-${daysUntil(next.deadline_date, next.deadline_time)}` : '—', sub: next?.assignment_title, flame: true },
        { label: 'Upcoming',      value: String(upcoming.length),                                            sub: 'assessments' },
        { label: 'Modules',       value: String(modules.length),                                             sub: 'active' },
      ]} />

      <section className={s.sec}>
        <h2 className={s.h2}>Time to Objective</h2>
        <div className={s.grid}>
          {upcoming.map(a => {
            const m = modules.find(x => x.code === a.module_code)
            return <CountdownCard key={a.id} moduleCode={a.module_code} moduleName={m?.name ?? ''}
                                  accent={m?.color ?? '#2F5040'} title={a.assignment_title}
                                  date={a.deadline_date} time={a.deadline_time} />
          })}
          {upcoming.length === 0 && <p className={s.empty}>No upcoming deadlines.</p>}
        </div>
      </section>
    </>
  )
}
