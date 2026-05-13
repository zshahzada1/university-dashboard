import { useState } from 'react'
import s from './TopicRow.module.css'
import type { Topic } from '../lib/types'
import { api } from '../lib/api'

export default function TopicRow({ topic, onSelect, selected, accent }: {
  topic: Topic; selected: boolean; accent: string;
  onSelect: () => void;
}) {
  const [c, setC] = useState(topic.confidence)
  async function set(n: number) { setC(n); await api.patchTopic(topic.id, { confidence: n }) }
  return (
    <div className={`${s.row} ${selected ? s.sel : ''}`} onClick={onSelect}
         style={{ ['--accent' as any]: accent }}>
      <div className={s.wk}>{topic.week ?? '–'}</div>
      <div className={s.title}>{topic.title}</div>
      <div className={s.rate} onClick={e => e.stopPropagation()}>
        {[1,2,3,4,5].map(n => (
          <button key={n} className={`${s.r} ${c===n?s.on:''}`} onClick={() => set(n)}>{n}</button>
        ))}
      </div>
    </div>
  )
}
