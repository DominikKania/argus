export type ResearchStatus = 'draft' | 'ready' | 'running' | 'completed' | 'error'

export interface Research {
  _id: string
  topic: string
  title: string
  prompt: string
  status: ResearchStatus
  results: string | null
  relevance_summary: string | null
  error_message: string | null
  created_date: string
  updated_date: string
  last_run_date: string | null
}
