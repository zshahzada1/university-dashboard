import { useEffect, useRef, useState } from 'react'
import s from './NoteEditor.module.css'

export default function NoteEditor({ initial, onSave }: {
  initial: string; onSave: (body: string) => Promise<void>;
}) {
  const [text, setText] = useState(initial)
  const [status, setStatus] = useState<'idle'|'saving'|'saved'|'error'>('idle')
  const timer = useRef<number | null>(null)

  useEffect(() => { setText(initial); setStatus('idle') }, [initial])

  function schedule(next: string) {
    if (timer.current != null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      setStatus('saving')
      try { await onSave(next); setStatus('saved') } catch { setStatus('error') }
    }, 800) as unknown as number
  }

  function onChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setText(e.target.value); schedule(e.target.value)
  }
  function onBlur() {
    if (timer.current != null) window.clearTimeout(timer.current)
    setStatus('saving'); onSave(text).then(() => setStatus('saved'), () => setStatus('error'))
  }

  return (
    <div className={s.box}>
      <textarea className={s.ta} value={text} onChange={onChange} onBlur={onBlur} placeholder="Notes for this topic…" />
      <div className={s.bar}>{status === 'saving' ? 'SAVING…' : status === 'saved' ? 'SAVED' : status === 'error' ? 'ERROR' : ''}</div>
    </div>
  )
}
