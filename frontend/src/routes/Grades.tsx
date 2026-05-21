import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { GradesResponse, ModuleGrade, OverallGrade, AssessmentGrade } from '../lib/types'
import s from './Grades.module.css'

function clsCls(c: string | null): string {
  if (!c) return ''
  if (c === 'First') return s.first
  if (c === '2:1')   return s.twoOne
  if (c === '2:2')   return s.twoTwo
  if (c === 'Third') return s.third
  return s.fail
}

function OverallCard({ overall, synced_at }: { overall: OverallGrade; synced_at: string | null }) {
  return (
    <div className={s.overallCard}>
      <div className={s.overallLeft}>
        <div className={s.overallGrade}>{overall.grade != null ? `${overall.grade}%` : '—'}</div>
        {overall.classification && (
          <div className={`${s.cls} ${clsCls(overall.classification)}`}>{overall.classification}</div>
        )}
      </div>
      <div className={s.overallRight}>
        <div className={s.overallLbl}>CREDIT-WEIGHTED OVERALL</div>
        {overall.first_status === 'secured' && (
          <div className={s.secured}>First class secured.</div>
        )}
        {overall.first_status === 'possible' && overall.needed_for_first != null && (
          <div className={s.needed}>
            Need <strong>{overall.needed_for_first}%</strong> average across remaining work for a First.
          </div>
        )}
        {overall.first_status === 'impossible' && (
          <div className={s.impossible}>First class no longer possible.</div>
        )}
        {synced_at && (
          <div className={s.sync}>synced {new Date(synced_at).toLocaleString()}</div>
        )}
      </div>
    </div>
  )
}

const STATUS_LABELS: Record<AssessmentGrade['status'], string> = {
  upcoming: 'UPCOMING', submitted: 'SUBMITTED', graded: 'GRADED', unmapped: ''
}

function ModuleCard({ code, mod }: {
  code: string; mod: ModuleGrade;
}) {
  return (
    <div className={s.modCard}>
      <div className={s.modHead}>
        <span className={s.code}>{code}</span>
        <span className={s.modName}>{mod.name}</span>
        <span className={s.credits}>{mod.credits}cr</span>
      </div>

      {mod.error ? (
        <div className={s.errMsg}>{mod.error}</div>
      ) : (
        <>
          <table className={s.table}>
            <tbody>
              {mod.assessments.map(a => {
                return (
                  <tr key={a.title} className={s.row}>
                    <td className={s.aTitle}>{a.title}</td>
                    <td className={s.aWeight}>{a.weight_percent}%</td>
                    <td className={s.aStatus}>
                      {a.status !== 'unmapped' && (
                        <span className={`${s.statusBadge} ${s[a.status]}`}>{STATUS_LABELS[a.status]}</span>
                      )}
                    </td>
                    <td className={s.aScore}>
                      {a.status === 'graded'   && <span className={s.graded}>{a.score}%</span>}
                      {a.status === 'unmapped' && <span className={s.unmapped}>unmapped</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div className={s.modFoot}>
            <div>
              <span className={s.lbl}>GRADE SO FAR</span>
              <span className={mod.grade_so_far != null ? clsCls(mod.classification) : ''}>
                {mod.grade_so_far != null ? `${mod.grade_so_far}% (${mod.classification})` : '—'}
              </span>
            </div>
            <div>
              {mod.first_status === 'secured' && <span className={s.secured}>First secured.</span>}
              {mod.first_status === 'possible' && mod.needed_for_first != null && (
                <span className={s.needed}>Need {mod.needed_for_first}% for a First.</span>
              )}
              {mod.first_status === 'impossible' && (
                <span className={s.impossible}>First not possible.</span>
              )}
              {mod.first_status === 'final' && mod.classification && (
                <span>Final: {mod.classification}</span>
              )}
            </div>
            {!mod.weights_ok && <div className={s.warn}>Weights ≠ 100%</div>}
          </div>
        </>
      )}
    </div>
  )
}


export default function Grades() {
  const [data, setData]   = useState<GradesResponse | null>(null)
  const [err, setErr]     = useState<string | null>(null)

  useEffect(() => {
    api.grades().then(setData).catch(e => setErr(String(e)))
  }, [])

  if (err)   return <div className={s.err}>{err}</div>
  if (!data) return <div className={s.loading}>Loading grades…</div>
  if (data.error) return (
    <>
      <h1 className={s.h1}>Grades</h1>
      <div className={s.err}>{data.error}</div>
    </>
  )

  return (
    <>
      <h1 className={s.h1}>Grades</h1>
      <OverallCard overall={data.overall} synced_at={data.synced_at} />
      {data.excluded_modules.length > 0 && (
        <div className={s.excluded}>Excluded (no access): {data.excluded_modules.join(', ')}</div>
      )}
      <div className={s.grid}>
        {Object.entries(data.modules).map(([code, mod]) => (
          <ModuleCard key={code} code={code} mod={mod} />
        ))}
      </div>
    </>
  )
}
