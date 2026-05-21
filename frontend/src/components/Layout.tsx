import type { ReactNode } from 'react'
import { useHashRoute } from '../lib/router'
import { useDarkMode } from '../lib/darkMode'
import s from './Layout.module.css'

const NAV = [
  ['#/',        'Home'],
  ['#/planner', 'Planner'],
  ['#/grades',  'Grades'],
  ['#/files',   'Files'],
  ['#/sync',    'Sync'],
] as const

export default function Layout({ children }: { children: ReactNode }) {
  const route = useHashRoute()
  const [dark, toggleDark] = useDarkMode()
  return (
    <div className={s.shell}>
      <aside className={s.side}>
        <div className={s.brand}>
          <div className={s.brandMark}>U</div>
          <span className={s.brandName}>
            Uni<span className={s.brandAccent}> · </span>Hub
          </span>
        </div>
        <nav>
          {NAV.map(([h, l]) => {
            const isActive = h === '#/' ? route === '#/' || route === '' : route.startsWith(h)
            return (
              <a key={h} href={h} className={`${s.link}${isActive ? ' ' + s.active : ''}`}>{l}</a>
            )
          })}
        </nav>
        <div className={s.spacer} />
        <button
          className={s.themeToggle}
          onClick={toggleDark}
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {dark ? '☀' : '☾'}
        </button>
      </aside>
      <main className={s.main}>{children}</main>
    </div>
  )
}
