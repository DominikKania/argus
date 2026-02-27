export interface PriceEntry {
  _id: string
  ticker: string
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  sma50?: number
  sma200?: number
}

export interface WatchlistEntry {
  _id: string
  ticker: string
  name: string
  added_date: string
  category: 'etf' | 'stock'
}
