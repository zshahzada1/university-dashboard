import { daysUntil } from './dates'
import { it, expect, vi } from 'vitest'

it('daysUntil counts full days, clamped to 0', () => {
  vi.useFakeTimers().setSystemTime(new Date('2026-05-13T09:00:00Z'))
  expect(daysUntil('2026-05-15', '14:00')).toBe(2)
  expect(daysUntil('2026-05-13', '00:00')).toBe(0)
  expect(daysUntil('2026-05-10', '00:00')).toBe(0)  // past
  vi.useRealTimers()
})