import type { Module, Topic, Assignment, Task, Event, SearchHit, TopicsByModule, GradesResponse, SyncCourse, TreeNode } from './types'

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try { const b = await r.json(); if (b?.detail) msg = String(b.detail) } catch { /* keep default */ }
    throw new Error(msg)
  }
  if (r.status === 204) return undefined as T
  return r.json()
}

async function* _readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      if (part.startsWith('data: ')) yield part.slice(6)
    }
  }
  const tail = buf + decoder.decode()
  for (const part of tail.split('\n')) {
    if (part.startsWith('data: ')) yield part.slice(6)
  }
}

export const api = {
  modules: () => fetch('/api/modules').then(j<Module[]>),
  topics:  (module?: string) =>
    fetch(`/api/topics${module ? `?module=${module}` : ''}`).then(j<TopicsByModule>),
  patchTopic: (id: string, body: Partial<Topic>) =>
    fetch(`/api/topics/${id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(j<Topic>),
  seedTopics: () => fetch('/api/topics/seed', { method: 'POST' }).then(j<TopicsByModule>),

  assignments: () => fetch('/api/assignments').then(j<Assignment[]>),
  patchAssignment: (id: string, body: Partial<Assignment>) =>
    fetch(`/api/assignments/${id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(j<Assignment>),

  tasks: (due?: 'today'|'week'|'backlog') =>
    fetch(`/api/tasks${due ? `?due=${due}` : ''}`).then(j<Task[]>),
  createTask: (body: Partial<Task>) =>
    fetch('/api/tasks', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(j<Task>),
  patchTask: (id: string, body: Partial<Task>) =>
    fetch(`/api/tasks/${id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(j<Task>),
  deleteTask: (id: string) => fetch(`/api/tasks/${id}`, { method: 'DELETE' }).then(j<void>),

  events: () => fetch('/api/events').then(j<Event[]>),
  createEvent: (body: Partial<Event>) =>
    fetch('/api/events', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(j<Event>),

  getNote: (m: string, t: string) => fetch(`/api/notes/${m}/${t}`).then(r => r.ok ? r.text() : ''),
  putNote: (m: string, t: string, body: string) =>
    fetch(`/api/notes/${m}/${t}`, { method: 'PUT', headers: { 'content-type': 'text/plain; charset=utf-8' }, body }).then(j<void>),

  files: (module: string, topic_id: string) =>
    fetch(`/api/files?module=${module}&topic_id=${topic_id}`).then(j<{name:string; rel_path:string; size:number}[]>),
  search: (q: string) => fetch(`/api/search?q=${encodeURIComponent(q)}`).then(j<SearchHit[]>),
  open:   (rel_path: string) =>
    fetch('/api/open', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ rel_path }) }).then(j<void>),
  serveUrl: (rel_path: string) => `/api/serve/${rel_path}`,

  state:   () => fetch('/api/state').then(j<{dismissed: Record<string, string[]>}>),
  dismiss: (date: string, topic_id: string) =>
    fetch('/api/state/dismiss', { method: 'POST', headers: { 'content-type': 'application/json' },
                                  body: JSON.stringify({ date, topic_id }) }).then(j<void>),

  grades: () => fetch('/api/grades').then(j<GradesResponse>),

  syncCourses: () => fetch('/api/sync/courses').then(j<SyncCourse[]>),

  syncRun: async (modules: string[], mode: string, onLine: (line: string) => void): Promise<void> => {
    const r = await fetch('/api/sync/run', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ modules, mode }),
    })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    if (!r.body) throw new Error('Server returned no response body for sync stream')
    for await (const line of _readSSE(r.body)) {
      onLine(line)
    }
  },

  fileTree: () => fetch('/api/files/tree').then(j<TreeNode[]>),
}