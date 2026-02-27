export interface VixData {
  value: number
  direction: 'rising' | 'falling' | 'flat'
  prev_week: number
}

export interface YieldsData {
  us10y: number
  us2y: number
  spread: number
  spread_direction: 'widening' | 'narrowing' | 'flat'
  real_yield: number
  cpi: number
}

export interface SectorData {
  perf_1m: number
  ticker: string
}

export interface SectorRotation {
  sectors: Record<string, SectorData>
  risk_on_vs_off: number | null
}

export interface RegionalComparison {
  spy_perf_1m: number | null
  ezu_perf_1m: number | null
  usa_vs_europe: number | null
}

export interface Seasonality {
  current_month: number
  avg_return_pct: number
  monthly_returns: Record<string, number>
  seasonal_bias: 'bullish' | 'bearish' | 'neutral'
}

export interface PutCallRatio {
  put_oi: number
  call_oi: number
  ratio: number
  signal: 'bullish' | 'neutral' | 'bearish'
}

export interface MarketContext {
  sector_rotation_note?: string
  regional_note?: string
  seasonality_note?: string
  breadth_note?: string
  put_call_note?: string
}

export interface MarketData {
  price: number
  sma50: number
  sma200: number
  ath: number
  delta_ath_pct: number
  puffer_sma50_pct: number
  golden_cross: boolean
  vix: VixData
  yields: YieldsData
  sector_rotation?: SectorRotation | null
  regional?: RegionalComparison | null
  seasonality?: Seasonality | null
  put_call?: PutCallRatio | null
}

export type SignalColor = 'green' | 'yellow' | 'red'

export interface Signal {
  mechanical: SignalColor
  context: SignalColor
  note?: string
}

export type OverallRating =
  | 'GREEN'
  | 'GREEN_FRAGILE'
  | 'YELLOW'
  | 'YELLOW_BEARISH'
  | 'RED'
  | 'RED_CAPITULATION'

export type ActionType = 'hold' | 'buy' | 'partial_sell' | 'hedge' | 'wait'

export interface Rating {
  mechanical_score: number
  overall: OverallRating
  reasoning: string
}

export interface Recommendation {
  action: ActionType
  detail: string
}

export interface SentimentEvent {
  headline: string
  summary?: string
  affects_portfolio?: string
  cascade_risk?: string
  is_primary?: boolean
}

export interface BellerCheck {
  triggered: boolean
  classification?: string | null
  trigger_type?: string | null
  vix_pattern?: string | null
  earnings_status?: string | null
  breadth?: string | null
  reasoning?: string
}

export interface Thesis {
  statement: string
  catalyst?: string
  catalyst_date?: string
  expected_if_positive?: string
  expected_if_negative?: string
}

export interface SimplifiedTexts {
  rating_reasoning: string
  recommendation_detail: string
  escalation_trigger: string
  signal_notes: Record<string, string>
  sentiment_events: Array<{ headline: string; summary: string }>
  beller_check_reasoning: string
  thesis?: {
    statement: string
    catalyst: string
    expected_if_positive: string
    expected_if_negative: string
  }
}

export interface Analysis {
  _id: string
  date: string
  weekday?: string
  market: MarketData
  signals: Record<string, Signal>
  rating: Rating
  recommendation: Recommendation
  beller_check?: BellerCheck
  sentiment_events?: SentimentEvent[]
  thesis?: Thesis
  escalation_trigger?: string
  crash_rule_active?: boolean
  market_context?: MarketContext | null
  simplified?: SimplifiedTexts
}

export interface OpenThesis {
  _id: string
  created_date: string
  analysis_id: string
  statement: string
  catalyst?: string
  catalyst_date?: string
  expected_if_positive?: string
  expected_if_negative?: string
  status: 'open' | 'resolved'
}
