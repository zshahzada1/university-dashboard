export type Module = { code: string; name: string; color: string; folder: string }
export type Topic  = { id: string; title: string; week: number | null; folder: string;
                       confidence: number | null; updated_at: string | null }
export type Assignment = {
  id: string; module_code: string; assignment_title: string; assignment_type: string;
  description: string; deadline_date: string; deadline_time: string;
  weighting_percent: number; word_limit_or_size: string; submission_method: string;
  status: 'upcoming'|'submitted'|'graded'; linked_topics: string[]
}
export type Task  = { id: string; text: string; module_code?: string|null; topic_id?: string|null;
                      due_date: string | null; done: boolean; created_at: string }
export type Event = { id: string; title: string; date: string; time?: string|null;
                      module_code?: string|null; kind: 'exam'|'meeting'|'study_session'|'other' }
export type SearchHit = { name: string; rel_path: string; module: string }
export type TopicsByModule = Record<string, Topic[]>