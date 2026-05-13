import { render, fireEvent, screen, act } from '@testing-library/react'
import { vi, it, expect, beforeEach } from 'vitest'
import NoteEditor from './NoteEditor'

beforeEach(() => vi.restoreAllMocks())

it('saves note after debounce', async () => {
  vi.useFakeTimers()
  const save = vi.fn().mockResolvedValue(undefined)
  render(<NoteEditor initial="" onSave={save} />)
  const ta = screen.getByRole('textbox')
  await act(async () => {
    fireEvent.change(ta, { target: { value: '# Hello' } })
  })
  await act(async () => {
    vi.advanceTimersByTime(900)
    await vi.runAllTimersAsync()
  })
  expect(save).toHaveBeenCalledWith('# Hello')
  vi.useRealTimers()
})
