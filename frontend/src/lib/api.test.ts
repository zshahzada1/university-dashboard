import { api, ApiError } from './api'
import { vi, beforeEach, it, expect } from 'vitest'

beforeEach(() => { vi.restoreAllMocks() })

it('patchTopic sends PATCH and returns json', async () => {
  const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
    JSON.stringify({ id: 'x', title: 't', folder: 'f', week: 1, confidence: 4, updated_at: 'now' }),
    { status: 200, headers: { 'content-type': 'application/json' } }
  ))
  const r = await api.patchTopic('x', { confidence: 4 })
  expect(r.confidence).toBe(4)
  expect(spy).toHaveBeenCalledWith('/api/topics/x', expect.objectContaining({ method: 'PATCH' }))
})

it('errors carry the HTTP status and server detail', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
    JSON.stringify({ detail: 'Not connected to Blackboard' }),
    { status: 401, headers: { 'content-type': 'application/json' } }
  ))
  const err = await api.syncCourses().catch(e => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err.status).toBe(401)
  expect(err.message).toBe('Not connected to Blackboard')
})
