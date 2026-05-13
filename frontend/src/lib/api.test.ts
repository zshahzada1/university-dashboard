import { api } from './api'
import { vi, beforeEach, it, expect } from 'vitest'

beforeEach(() => { vi.restoreAllMocks() })

it('patchTopic sends PATCH and returns json', async () => {
  const spy = vi.spyOn(global, 'fetch').mockResolvedValue(new Response(
    JSON.stringify({ id: 'x', title: 't', folder: 'f', week: 1, confidence: 4, updated_at: 'now' }),
    { status: 200, headers: { 'content-type': 'application/json' } }
  ))
  const r = await api.patchTopic('x', { confidence: 4 })
  expect(r.confidence).toBe(4)
  expect(spy).toHaveBeenCalledWith('/api/topics/x', expect.objectContaining({ method: 'PATCH' }))
})