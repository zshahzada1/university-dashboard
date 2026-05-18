import { api } from './api'

// Office files can't render in browser — open via Windows explorer.exe
const OFFICE_EXTS = new Set(['docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'pptm'])

export function openFile(rel_path: string) {
  const ext = rel_path.split('.').pop()?.toLowerCase() ?? ''
  if (OFFICE_EXTS.has(ext)) {
    api.open(rel_path)
  } else {
    window.open(api.serveUrl(rel_path), '_blank')
  }
}
