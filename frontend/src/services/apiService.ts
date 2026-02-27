import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export const ApiService = {
  async get<T>(endpoint: string): Promise<T> {
    const response = await apiClient.get<T>(endpoint)
    return response.data
  },

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await apiClient.post<T>(endpoint, data)
    return response.data
  },

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    const response = await apiClient.put<T>(endpoint, data)
    return response.data
  },

  async delete<T>(endpoint: string): Promise<T> {
    const response = await apiClient.delete<T>(endpoint)
    return response.data
  },
}
