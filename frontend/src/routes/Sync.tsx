import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { SyncCourse } from '../lib/types'
import s from './Sync.module.css'

type Mode = 'all' | 'files' | 'grades'

function detectCurrentYearCodes(courses: SyncCourse[]): Set<string> {
  // Strategy 1: group by term_id, pick the term with the most coded courses
  const termCounts: Record<string, string[]> = {}
  for (const c of courses) {
    if (c.code && c.term_id) {
      termCounts[c.term_id] ??= []
      termCounts[c.term_id].push(c.code)
    }
  }
  const byTermSize = Object.entries(termCounts).sort(([, a], [, b]) => b.length - a.length)
  if (byTermSize.length > 0) return new Set(byTermSize[0][1])

  // Strategy 2: match current UK academic year pattern in course name (e.g. "2025/26")
  const now = new Date()
  const yr = now.getFullYear()
  const m = now.getMonth() + 1
  const startYr = m >= 9 ? yr : yr - 1
  const pattern = new RegExp(`${startYr}[/\\-]${String(startYr + 1).slice(2)}`, 'i')
  const byName = courses.filter(c => c.code && pattern.test(c.name)).map(c => c.code!)
  if (byName.length > 0) return new Set(byName)

  // Fallback: all courses with codes
  return new Set(courses.filter(c => c.code).map(c => c.code!))
}

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
        setSelected(detectCurrentYearCodes(cs))
      })
      .catch(e => setFetchErr(String(e)))
  }, [])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [lines])

  // Deduplicated list of selectable codes — avoids Set/array length mismatch
  const allCodes = useMemo(
    () => [...new Set((courses ?? []).filter(c => c.code).map(c => c.code!))],
    [courses]
  )

  function toggleAll() {
    if (selected.size === allCodes.length) setSelected(new Set())
    else setSelected(new Set(allCodes))
  }

  function selectCurrentYear() {
    if (!courses) return
    setSelected(detectCurrentYearCodes(courses))
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
    const mods = courses.filter(c => c.code && selected.has(c.code)).map(c => c.code!)
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

  const noneSelected = selected.size === 0 && mode !== 'grades'
  const canRun = !running && !!courses && !noneSelected

  return (
    <>
      <h1 className={s.h1}>Sync</h1>

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
              <button className={s.toggleBtn} onClick={selectCurrentYear}>
                This year
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
