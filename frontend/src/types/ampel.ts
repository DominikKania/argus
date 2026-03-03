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

export interface EurUsd {
  rate: number
  change_1m_pct: number
  direction: 'rising' | 'falling' | 'flat'
}

export interface CreditSpread {
  hyg_price: number
  lqd_price: number
  hyg_perf_1m: number | null
  lqd_perf_1m: number | null
  spread_proxy: number | null
  direction: 'widening' | 'narrowing' | 'flat'
}

export interface MarketContext {
  [key: string]: string | undefined
}

export interface EarningsSectorData {
  beat_rate: string
  beat_rate_pct: number
  avg_surprise_pct: number
  fwd_eps_growth: number | null
  revision_direction: 'rising' | 'flat' | 'falling'
  tickers: string[]
}

export interface EarningsEvent {
  ticker: string
  date: string
  sector: string
  surprise_pct?: number
}

export interface EarningsData {
  beat_rate: string
  beat_rate_pct: number
  avg_surprise_pct: number
  fwd_eps_growth_0y: number | null
  net_revisions_7d: number
  net_revisions_30d: number
  revision_direction: 'rising' | 'flat' | 'falling'
  earnings_health: 'strong' | 'moderate' | 'weak' | 'deteriorating'
  by_sector: Record<string, EarningsSectorData>
  upcoming: EarningsEvent[]
  recently_reported: EarningsEvent[]
  tickers_loaded: number
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
  eurusd?: EurUsd | null
  credit_spread?: CreditSpread | null
  earnings?: EarningsData | null
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

export interface Thesis {
  statement: string
  catalyst?: string
  catalyst_date?: string
  expected_if_positive?: string
  expected_if_negative?: string
}

export interface StagePrompt {
  system: string
  user: string
}

export interface AnalysisPrompts {
  system: string
  user: string
  stages?: Record<string, StagePrompt>
}

export interface KeyLevels {
  support: string
  resistance: string
  pivot_note: string
}

export type RiskLevel = 'low' | 'moderate' | 'elevated' | 'high' | 'extreme'

export interface RiskAssessment {
  level: RiskLevel
  primary_risks: string[]
  mitigating_factors: string[]
}

export interface ActionTriggers {
  buy_trigger: string
  sell_trigger: string
  watch_items: string[]
}

export interface Analysis {
  _id: string
  date: string
  weekday?: string
  market: MarketData
  signals: Record<string, Signal>
  rating: Rating
  recommendation: Recommendation
  sentiment_events?: SentimentEvent[]
  thesis?: Thesis
  escalation_trigger?: string
  crash_rule_active?: boolean
  market_context?: MarketContext | null
  key_levels?: KeyLevels | null
  risk_assessment?: RiskAssessment | null
  action_triggers?: ActionTriggers | null
  historical_comparison?: string | null
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
  resolution?: string
  resolution_date?: string
  lessons_learned?: string
}
