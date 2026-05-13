import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Module, TopicsByModule, Assignment, Task } from '../lib/types'
import CountdownCard from '../components/CountdownCard'
import StatStrip from '../components/StatStrip'
import ModuleProgress from '../components/ModuleProgress'
import { daysUntil } from '../lib/dates'
import s from './Home.module.css'

export default function Home() {
  const [modules, setModules] = useState<Module[]>([])
  const [topics, setTopics]   = useState<TopicsByModule>({})
  const [asgs, setAsgs]       = useState<Assignment[]>([])
  const [tasks, setTasks]     = useState<Task[]>([])

  useEffect(() => {
    Promise.all([api.modules(), api.topics(), api.assignments(), api.tasks('today')])
      .then(([m, t, a, k]) => { setModules(m); setTopics(t); setAsgs(a); setTasks(k) })
  }, [])

  const upcoming = asgs.filter(a => a.status === 'upcoming')
                       .sort((a, b) => (a.deadline_date+a.deadline_time).localeCompare(b.deadline_date+b.deadline_time))
  const next = upcoming[0]
  const allTopics = Object.values(topics).flat()
  const rated = allTopics.filter(t => t.confidence != null)
  const weakest = rated.length ? rated.reduce((m, t) => (t.confidence! < m.confidence! ? t : m), rated[0]) : null
  const lowCount = rated.filter(t => (t.confidence ?? 5) <= 2).length

  return (
    <>
      <header className={s.head}>
        <h1>UNI · HUB</h1>
        <div className={s.date}>{new Date().toDateString()}</div>
      </header>

      <StatStrip stats={[
        { label: 'Tasks today',   value: String(tasks.length),                                           sub: tasks.filter(t=>!t.done).length + ' open', gold: true },
        { label: 'Next deadline', value: next ? `T-${daysUntil(next.deadline_date, next.deadline_time)}` : '—', sub: next?.assignment_title, flame: true },
        { label: 'Weakest topic', value: weakest ? String(weakest.confidence) : '—',                     sub: weakest?.title ?? 'No ratings yet' },
        { label: 'Below 3/5',     value: String(lowCount),                                               sub: 'topics flagged' },
      ]} />

      <section className={s.sec}>
        <h2 className={s.h2}>TIME TO OBJECTIVE</h2>
        <div className={s.grid}>
          {upcoming.map(a => {
            const m = modules.find(x => x.code === a.module_code)
            return <CountdownCard key={a.id} moduleCode={a.module_code} moduleName={m?.name ?? ''}
                                  accent={m?.color ?? '#fff'} title={a.assignment_title}
                                  date={a.deadline_date} time={a.deadline_time} />
          })}
        </div>
      </section>

      <section className={s.sec}>
        <h2 className={s.h2}>WHERE TO FOCUS</h2>
        <div className={s.modGrid}>
          {modules.map(m => <ModuleProgress key={m.code} module={m} topics={topics[m.code] ?? []} />)}
        </div>
      </section>
    </>
  )
}
