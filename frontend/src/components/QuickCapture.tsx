import { useEffect, useRef, useState } from 'react'
import s from './QuickCapture.module.css'
import { api } from '../lib/api'

export default function QuickCapture({ onAdded }: { onAdded: () => void }) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); ref.current?.focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    const today = new Date().toISOString().slice(0,10)
    await api.createTask({ text: text.trim(), due_date: today })
    setText(''); onAdded()
  }

  return (
    <form className={s.box} onSubmit={submit}>
      <input ref={ref} className={s.in} value={text} onChange={e => setText(e.target.value)}
             placeholder="Quick capture (⌘/Ctrl-K)…" />
      <button className={s.btn}>ADD</button>
    </form>
  )
}
