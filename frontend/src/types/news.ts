export interface NewsHeadline {
  title: string
  source?: string
  link?: string
  relevance: 'high' | 'medium' | 'low'
  sentiment: 'positive' | 'negative' | 'neutral'
}

export interface NewsResult {
  _id: string
  topic: string
  date: string
  headlines_fetched: number
  relevant_headlines: NewsHeadline[]
  sentiment_count?: { positive: number; negative: number; neutral: number }
  summary: string
  development?: string
  recurring?: string
  trend: 'improving' | 'stable' | 'deteriorating'
  trend_reasoning?: string
  triggers_detected: string[]
  ampel_relevance: string
  deep_research?: string | null
  created_date: string
}

export interface RssFeed {
  name: string
  url: string
}

export interface NewsTopic {
  _id: string
  topic: string
  title: string
  prompt: string
  active: boolean
  rss_feeds: RssFeed[] | null
  created_date: string
  updated_date: string
  latest_result: NewsResult | null
  results_history?: NewsResult[]
}
