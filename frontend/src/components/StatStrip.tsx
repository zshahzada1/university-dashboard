import s from './StatStrip.module.css'

type Stat = { label: string; value: string; sub?: string; flame?: boolean; gold?: boolean }
export default function StatStrip({ stats }: { stats: Stat[] }) {
  return (
    <div className={s.strip}>
      {stats.map(st => (
        <div className={s.stat} key={st.label}>
          <div className={s.lbl}>{st.label}</div>
          <div className={`${s.val} ${st.gold?s.gold:''} ${st.flame?s.flame:''}`}>{st.value}</div>
          {st.sub && <div className={s.sub}>{st.sub}</div>}
        </div>
      ))}
    </div>
  )
}