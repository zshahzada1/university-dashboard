import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { TreeNode } from '../lib/types'
import FileTree from '../components/FileTree'
import s from './Files.module.css'

export default function Files() {
  const [tree, setTree] = useState<TreeNode[] | null>(null)
  const [err, setErr]   = useState<string | null>(null)

  useEffect(() => {
    api.fileTree().then(setTree).catch(e => setErr(String(e)))
  }, [])

  return (
    <>
      <h1 className={s.h1}>FILES</h1>
      {!tree && !err && <div className={s.loading}>Scanning…</div>}
      {err && <div className={s.err}>{err}</div>}
      {tree && <div className={s.tree}><FileTree nodes={tree} /></div>}
    </>
  )
}
