import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { SyncCourse } from '../lib/types'
import s from './Sync.module.css'

type Mode = 'all' | 'files' | 'grades'

export default function Sync() {
  const [courses, setCourses]   = useState<SyncCourse[] | null>(null)
  const [fetchErr, setFetchErr] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [mode, setMode]         = useState<Mode>('all')
  const [running, setRunning]   = useState(false)
  const [lines, setLines]       = useState<{ text: string; cls?: string }[]>([])
  const termRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.syncCourses()
      .then(cs => {
        setCourses(cs)
        setSelected(new Set(cs.filter(c => c.code).map(c => c.code!)))
      })
      .catch(e => setFetchErr(String(e)))
  }, [])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [lines])

  function toggleAll() {
    if (!courses) return
    const codes = courses.filter(c => c.code).map(c => c.code!)
    if (selected.size === codes.length) setSelected(new Set())
    else setSelected(new Set(codes))
  }

  function toggleOne(code: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(code) ? next.delete(code) : next.add(code)
      return next
    })
  }

  async function handleSync() {
    if (!courses) return
    setRunning(true)
    setLines([])
    const mods = courses.filter(c => c.code && selected.has(c.code!)).map(c => c.code!)
    try {
      await api.syncRun(mods, mode, line => {
        if (line.startsWith('__exit__:')) {
          const code = parseInt(line.split(':')[1], 10)
          setLines(l => [...l, code === 0
            ? { text: 'Done.', cls: s.done }
            : { text: `Sync failed (exit ${code}).`, cls: s.failed },
          ])
        } else {
          setLines(l => [...l, { text: line }])
        }
      })
    } catch (e) {
      setLines(l => [...l, { text: `Error: ${e}`, cls: s.failed }])
    } finally {
      setRunning(false)
    }
  }

  const allCodes = courses?.filter(c => c.code).map(c => c.code!) ?? []
  const noneSelected = selected.size === 0 && mode !== 'grades'
  const canRun = !running && !!courses && !noneSelected

  return (
    <>
      <h1 className={s.h1}>SYNC</h1>

      <div className={s.section}>
        <div className={s.label}>Modules</div>
        {!courses && !fetchErr && <div className={s.loading}>Fetching from Blackboard…</div>}
        {fetchErr && <div className={s.err}>Could not load modules: {fetchErr}</div>}
        {courses && (
          <>
            <div className={s.toggleRow}>
              <button className={s.toggleBtn} onClick={toggleAll}>
                {selected.size === allCodes.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
            <div className={s.moduleGrid}>
              {courses.map(c => (
                <label key={c.id} className={s.moduleRow}>
                  <input
                    type="checkbox"
                    checked={!!c.code && selected.has(c.code)}
                    disabled={!c.code}
                    onChange={() => c.code && toggleOne(c.code)}
                  />
                  <span className={s.code}>{c.code ?? '—'}</span>
                  <span className={s.mname}>{c.name}</span>
                </label>
              ))}
            </div>
          </>
        )}
      </div>

      <div className={s.section}>
        <div className={s.label}>What to sync</div>
        <div className={s.modeRow}>
          {(['all', 'files', 'grades'] as Mode[]).map(m => (
            <label key={m} className={s.modeOpt}>
              <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
              <span>{m === 'all' ? 'Files + Grades' : m === 'files' ? 'Files only' : 'Grades only'}</span>
            </label>
          ))}
        </div>
      </div>

      <button className={s.runBtn} disabled={!canRun} onClick={handleSync}>
        {running ? 'Syncing…' : 'Sync'}
      </button>

      {lines.length > 0 && (
        <div className={s.terminal} ref={termRef}>
          {lines.map((l, i) => (
            <div key={i} className={l.cls}>{l.text}</div>
          ))}
        </div>
      )}
    </>
  )
}
