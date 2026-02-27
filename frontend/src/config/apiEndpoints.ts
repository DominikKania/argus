export const API_ENDPOINTS = {
  HEALTH: '/health',
  AMPEL: {
    LATEST: '/ampel/latest',
    HISTORY: (limit = 10) => `/ampel/history?limit=${limit}`,
    THESES: '/ampel/theses',
  },
} as const
