import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'
import type { Task, Assignment, Event, TopicsByModule } from '../lib/types'
import QuickCapture from '../components/QuickCapture'
import TaskRow from '../components/TaskRow'
import WeekStrip from '../components/WeekStrip'
import s from './Planner.module.css'

export default function Planner() {
  const TODAY = new Date().toISOString().slice(0,10)
  const [today, setToday] = useState<Task[]>([])
  const [backlog, setBacklog] = useState<Task[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [weekTasks, setWeekTasks] = useState<Task[]>([])
  const [topics, setTopics] = useState<TopicsByModule>({})
  const [dismissed, setDismissed] = useState<string[]>([])

  const refresh = useCallback(async () => {
    const [t, b, w, asgs, ev, tops, st] = await Promise.all([
      api.tasks('today'), api.tasks('backlog'), api.tasks('week'),
      api.assignments(), api.events(), api.topics(), api.state(),
    ])
    setToday(t); setBacklog(b); setWeekTasks(w); setAssignments(asgs); setEvents(ev); setTopics(tops)
    setDismissed(st.dismissed[TODAY] ?? [])
  }, [TODAY])

  useEffect(() => { refresh() }, [refresh])

  const allTopics = Object.entries(topics).flatMap(([code, ts]) => ts.map(t => ({...t, module_code: code})))
  const rated = allTopics.filter(t => t.confidence != null) as (typeof allTopics[number] & { confidence: number })[]
  const todayTexts = new Set(today.map(t => t.text.toLowerCase()))
  const suggestions = [...rated]
    .filter(t => !dismissed.includes(t.id))
    .sort((a,b) => a.confidence - b.confidence)
    .filter(t => !todayTexts.has(`revise ${t.title.toLowerCase()} (confidence: ${t.confidence})`))
    .slice(0, 3)

  async function acceptSuggestion(t: typeof suggestions[number]) {
    await api.createTask({ text: `Revise ${t.title} (confidence: ${t.confidence})`,
                           module_code: t.module_code, topic_id: t.id, due_date: TODAY })
    refresh()
  }
  async function dismissSug(tid: string) { await api.dismiss(TODAY, tid); setDismissed(d => [...d, tid]) }

  return (
    <>
      <h1 className={s.h1}>PLANNER</h1>
      <QuickCapture onAdded={refresh} />

      <section className={s.sec}>
        <h2 className={s.h2}>TODAY</h2>
        {today.map(t => (
          <TaskRow key={t.id} task={t}
            onToggle={() => api.patchTask(t.id, { done: !t.done }).then(refresh)}
            onDelete={() => api.deleteTask(t.id).then(refresh)} />
        ))}
        {!today.length && <div className={s.empty}>Nothing for today yet.</div>}
      </section>

      {suggestions.length > 0 && (
        <section className={s.sec}>
          <h2 className={s.h2}>SUGGESTED</h2>
          {suggestions.map(t => (
            <div key={t.id} className={s.sugg}>
              <span>Revise <b>{t.title}</b> ({t.module_code}, confidence {t.confidence})</span>
              <div>
                <button onClick={() => acceptSuggestion(t)}>ADD</button>
                <button onClick={() => dismissSug(t.id)}>DISMISS</button>
              </div>
            </div>
          ))}
        </section>
      )}

      <section className={s.sec}>
        <h2 className={s.h2}>THIS WEEK</h2>
        <WeekStrip tasks={weekTasks} assignments={assignments} events={events} />
      </section>

      <section className={s.sec}>
        <h2 className={s.h2}>BACKLOG</h2>
        {backlog.map(t => (
          <TaskRow key={t.id} task={t}
            onToggle={() => api.patchTask(t.id, { done: !t.done }).then(refresh)}
            onDelete={() => api.deleteTask(t.id).then(refresh)} />
        ))}
        {!backlog.length && <div className={s.empty}>Backlog is empty.</div>}
      </section>
    </>
  )
}
