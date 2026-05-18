import { useEffect, useState } from 'react'
import s from './FileBrowser.module.css'
import { api } from '../lib/api'
import { openFile } from '../lib/openFile'

export default function FileBrowser({ module, topicId }: { module: string; topicId: string }) {
  const [files, setFiles] = useState<{name:string; rel_path:string; size:number}[]>([])
  useEffect(() => { api.files(module, topicId).then(setFiles) }, [module, topicId])
  if (!files.length) return <div className={s.empty}>No files in this topic folder.</div>
  return (
    <ul className={s.list}>
      {files.map(f => (
        <li key={f.rel_path}>
          <button onClick={() => openFile(f.rel_path)}>{f.name}</button>
          <span>{(f.size/1024).toFixed(0)} KB</span>
        </li>
      ))}
    </ul>
  )
}
