export type Module = { code: string; name: string; color: string; folder: string }
export type Topic  = { id: string; title: string; week: number | null; folder: string;
                       confidence: number | null; updated_at: string | null }
export type Assignment = {
  id: string; module_code: string; assignment_title: string; assignment_type: string;
  description: string; deadline_date: string; deadline_time: string;
  weighting_percent: number; word_limit_or_size: string; submission_method: string;
  status: 'upcoming'|'submitted'|'graded'; status_override?: 'submitted' | null; linked_topics: string[]
}
export type Task  = { id: string; text: string; module_code?: string|null; topic_id?: string|null;
                      due_date: string | null; done: boolean; created_at: string }
export type Event = { id: string; title: string; date: string; time?: string|null;
                      module_code?: string|null; kind: 'exam'|'meeting'|'study_session'|'other' }
export type SearchHit = { name: string; rel_path: string; module: string }
export type TopicsByModule = Record<string, Topic[]>

export type AssessmentGrade = {
  title: string
  weight_percent: number
  score: number | null
  status: 'graded' | 'submitted' | 'upcoming' | 'unmapped'
}

export type ModuleGrade = {
  name: string
  credits: number
  grade_so_far: number | null
  classification: string | null
  needed_for_first: number | null
  first_status: 'possible' | 'secured' | 'impossible' | 'final'
  weights_ok: boolean
  assessments: AssessmentGrade[]
  error?: string
}

export type OverallGrade = {
  grade: number | null
  classification: string | null
  needed_for_first: number | null
  first_status: 'possible' | 'secured' | 'impossible' | 'final'
}

export type GradesResponse = {
  synced_at: string | null
  overall: OverallGrade
  excluded_modules: string[]
  modules: Record<string, ModuleGrade>
  error?: string
}

export type SyncCourse = { id: string; name: string; code: string | null; term_id?: string | null }

export type FileLeaf = {
  name: string
  type: 'file'
  size: number
  rel_path: string
}

export type DirNode = {
  name: string
  type: 'dir'
  children: TreeNode[]
}

export type TreeNode = FileLeaf | DirNode