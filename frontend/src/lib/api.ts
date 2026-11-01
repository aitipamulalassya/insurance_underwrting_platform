import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('yottaflex_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error?.response?.data?.detail
    error.message = typeof detail === 'string' ? detail : (error.message || 'Request failed')
    return Promise.reject(error)
  }
)

export const getError = (error: unknown) =>
  error instanceof Error ? error.message : 'Something went wrong'

export const money = (value: unknown, currency = 'INR') => {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount)
}

export const dateTime = (value: unknown) => {
  if (!value) return '—'
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

export const titleCase = (value: unknown) =>
  String(value ?? '—').replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())

export const rowsFrom = (value: any, key?: string): any[] => {
  const candidate = key ? value?.[key] : value
  if (Array.isArray(candidate)) return candidate
  if (Array.isArray(value?.data)) return value.data
  return []
}