import s from './TaskRow.module.css'
import type { Task } from '../lib/types'

export default function TaskRow({ task, onToggle, onDelete }:
  { task: Task; onToggle: () => void; onDelete: () => void }) {
  return (
    <div className={`${s.row} ${task.done ? s.done : ''}`}>
      <input type="checkbox" checked={task.done} onChange={onToggle} />
      <span className={s.text}>{task.text}</span>
      {task.module_code && <span className={s.mod}>{task.module_code}</span>}
      <button className={s.del} onClick={onDelete} aria-label="Delete">×</button>
    </div>
  )
}
