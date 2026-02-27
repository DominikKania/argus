export const API_ENDPOINTS = {
  HEALTH: '/health',
  AMPEL: {
    LATEST: '/ampel/latest',
    HISTORY: (limit = 10) => `/ampel/history?limit=${limit}`,
    THESES: '/ampel/theses',
  },
  PRICES: {
    WATCHLIST: '/prices/watchlist',
    TICKER: (ticker: string, days = 30) => `/prices/${ticker}?days=${days}`,
  },
  CHAT: '/chat/',
  RESEARCH: {
    LIST: '/research/',
    DETAIL: (id: string) => `/research/${id}`,
    CREATE: '/research/',
    UPDATE: (id: string) => `/research/${id}`,
    RUN: (id: string) => `/research/${id}/run`,
    DELETE: (id: string) => `/research/${id}`,
    GENERATE_PROMPT: '/research/generate-prompt',
  },
} as const
