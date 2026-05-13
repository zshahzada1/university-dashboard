export function daysUntil(date: string, time: string = '23:59'): number {
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  const target = new Date(y, m - 1, d, hh, mm).getTime()
  return Math.max(0, Math.floor((target - Date.now()) / 86400000))
}
export function fmt(date: string, time: string): string {
  const [y, m, d] = date.split('-').map(Number)
  const mons = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${d} ${mons[m-1]} ${y} · ${time}`
}