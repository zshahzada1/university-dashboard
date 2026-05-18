import { useState } from 'react'
import { api } from '../lib/api'
import type { TreeNode } from '../lib/types'
import s from './FileTree.module.css'

function fmt(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth === 0)
  const indent = { paddingLeft: `${depth * 1.25 + 0.75}rem` }

  if (node.type === 'file') {
    return (
      <div className={s.file} style={indent}>
        <button className={s.fileBtn} onClick={() => api.open(node.rel_path)}>{node.name}</button>
        <span className={s.size}>{fmt(node.size)}</span>
      </div>
    )
  }

  return (
    <div className={s.node}>
      <div className={s.dir} style={indent} onClick={() => setOpen(o => !o)}>
        <span className={s.chevron}>{open ? '▼' : '▶'}</span>
        <span className={s.dirName}>{node.name}</span>
        <span className={s.count}>{node.children.length}</span>
      </div>
      {open && (
        node.children.length === 0
          ? <div className={s.empty} style={{ paddingLeft: `${(depth + 1) * 1.25 + 0.75}rem` }}>empty</div>
          : node.children.map((child, i) => <Node key={i} node={child} depth={depth + 1} />)
      )}
    </div>
  )
}

export default function FileTree({ nodes }: { nodes: TreeNode[] }) {
  return (
    <div>
      {nodes.map((n, i) => <Node key={i} node={n} depth={0} />)}
    </div>
  )
}
