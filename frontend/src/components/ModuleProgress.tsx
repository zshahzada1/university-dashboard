import s from './ModuleProgress.module.css'
import type { Module, Topic } from '../lib/types'

export default function ModuleProgress({ module: m, topics }: { module: Module; topics: Topic[] }) {
  const rated = topics.filter(t => t.confidence != null) as (Topic & { confidence: number })[]
  const avg = rated.length ? rated.reduce((a, t) => a + t.confidence, 0) / rated.length : 0
  const weakest = [...rated].sort((a, b) => a.confidence - b.confidence).slice(0, 3)
  const pct = Math.round((avg / 5) * 100)
  return (
    <div className={s.box} style={{ ['--accent' as any]: m.color }}>
      <div className={s.head}>
        <a href={`#/module/${m.code}`} className={s.code}>{m.code}</a>
        <span className={s.avg}>{rated.length ? avg.toFixed(1) : '—'}/5</span>
      </div>
      <div className={s.barTrack}><div className={s.barFill} style={{ width: `${pct}%` }} /></div>
      <ul className={s.weak}>
        {weakest.map(t => <li key={t.id}><a href={`#/module/${m.code}?topic=${t.id}`}>{t.title}</a><span>{t.confidence}</span></li>)}
        {!weakest.length && <li className={s.empty}>No ratings yet — set confidence on the module page.</li>}
      </ul>
    </div>
  )
}