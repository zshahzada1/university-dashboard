import s from './CountdownCard.module.css'
import { daysUntil, fmt } from '../lib/dates'

type Props = {
  moduleCode: string;
  moduleName: string;
  accent: string;
  title: string;
  date: string; time: string;
}
export default function CountdownCard({ moduleCode, moduleName, accent, title, date, time }: Props) {
  const d = daysUntil(date, time)
  const hot = d <= 7
  return (
    <div className={`${s.card} ${hot ? s.hot : ''}`} style={{ ['--accent' as any]: accent }}>
      <div className={s.tag}>{moduleCode} · {moduleName}</div>
      <div className={s.num}>{d}</div>
      <div className={s.lbl}>DAYS REMAINING</div>
      <div className={s.title}>{title}</div>
      <div className={s.date}>{fmt(date, time)}</div>
    </div>
  )
}