import s from './WeekStrip.module.css'
import type { Task, Assignment, Event } from '../lib/types'

function dayKey(d: Date) { return d.toISOString().slice(0,10) }

export default function WeekStrip({ tasks, assignments, events }:
  { tasks: Task[]; assignments: Assignment[]; events: Event[] }) {
  const start = new Date(); start.setHours(0,0,0,0)
  const days = Array.from({length: 7}, (_, i) => { const d = new Date(start); d.setDate(start.getDate()+i); return d })
  return (
    <div className={s.grid}>
      {days.map(d => {
        const k = dayKey(d)
        const tasksHere = tasks.filter(t => t.due_date === k)
        const asgHere   = assignments.filter(a => a.deadline_date === k)
        const evHere    = events.filter(e => e.date === k)
        return (
          <div key={k} className={s.day}>
            <div className={s.head}>{d.toDateString().slice(0,3).toUpperCase()}<br/><b>{d.getDate()}</b></div>
            {asgHere.map(a => <div key={a.id} className={`${s.pill} ${s.deadline}`}>⚑ {a.assignment_title}</div>)}
            {evHere.map(e => <div key={e.id} className={`${s.pill} ${s.event}`}>◉ {e.title}</div>)}
            {tasksHere.map(t => <div key={t.id} className={s.pill}>• {t.text}</div>)}
          </div>
        )
      })}
    </div>
  )
}
