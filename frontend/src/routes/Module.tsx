import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Module as Mod, Topic } from '../lib/types'
import TopicRow from '../components/TopicRow'
import NoteEditor from '../components/NoteEditor'
import FileBrowser from '../components/FileBrowser'
import s from './Module.module.css'

export default function Module({ code }: { code: string }) {
  const [mod, setMod] = useState<Mod | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [selected, setSelected] = useState<Topic | null>(null)
  const [note, setNote] = useState<string>('')

  useEffect(() => {
    api.modules().then(ms => setMod(ms.find(x => x.code === code) ?? null))
    api.topics(code).then(t => {
      const list = t[code] ?? []
      setTopics(list)
      const want = new URLSearchParams(location.hash.split('?')[1] ?? '').get('topic')
      setSelected(list.find(x => x.id === want) ?? list[0] ?? null)
    })
  }, [code])

  useEffect(() => {
    if (selected) api.getNote(code, selected.id.replace(`${code.toLowerCase()}-`, '')).then(setNote)
  }, [code, selected?.id])

  if (!mod) return <div>Loading…</div>

  const rated = topics.filter(t => t.confidence != null) as (Topic & { confidence: number })[]
  const avg = rated.length ? (rated.reduce((a, t) => a + t.confidence, 0) / rated.length) : 0

  return (
    <>
      <header className={s.head}>
        <h1 style={{ color: mod.color }}>{mod.code}</h1>
        <div className={s.name}>{mod.name}</div>
        <div className={s.avg}>AVG CONFIDENCE: <b>{rated.length ? avg.toFixed(1) : '—'}</b>/5</div>
      </header>
      <div className={s.cols}>
        <section className={s.left}>
          {topics.map(t => (
            <TopicRow key={t.id} topic={t} accent={mod.color}
                      selected={selected?.id === t.id} onSelect={() => setSelected(t)} />
          ))}
          {!topics.length && <div>No topics seeded yet.</div>}
        </section>
        <section className={s.right}>
          {selected ? (
            <>
              <h2 className={s.tname}>{selected.title}</h2>
              <h3 className={s.h3}>NOTES</h3>
              <NoteEditor initial={note}
                onSave={body => api.putNote(code, selected.id.replace(`${code.toLowerCase()}-`, ''), body)} />
              <h3 className={s.h3}>FILES</h3>
              <FileBrowser module={code} topicId={selected.id} />
            </>
          ) : <div>No topics yet.</div>}
        </section>
      </div>
    </>
  )
}
