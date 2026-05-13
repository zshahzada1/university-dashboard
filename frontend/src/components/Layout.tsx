import type { ReactNode } from 'react'
import s from './Layout.module.css'
const NAV = [
  ['#/',          'HOME'],
  ['#/planner',   'PLANNER'],
  ['#/deadlines', 'DEADLINES'],
  ['#/resources', 'RESOURCES'],
] as const
export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className={s.shell}>
      <aside className={s.side}>
        <div className={s.brand}>UNI · HUB</div>
        <nav>{NAV.map(([h, l]) => <a key={h} href={h} className={s.link}>{l}</a>)}</nav>
      </aside>
      <main className={s.main}>{children}</main>
    </div>
  )
}