import axios from 'axios'

// In production (Vercel), use relative path. In development, use localhost.
const getApiBaseUrl = () => {
  if (import.meta.env.PROD) {
    return '/api'
  }
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
}

const API_BASE_URL = getApiBaseUrl()

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Only log out if token was actually set — avoids logging out during
      // the initial page load before any token was ever stored.
      if (localStorage.getItem('token')) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    }
    if (error.response?.status === 403) {
      const detail = error.response?.data?.detail || ''
      if (detail.includes('Google account not connected')) {
        window.location.href = '/login?google_required=true'
      }
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  getGoogleAuthUrl: () => client.get('/auth/google'),
  getMe: () => client.get('/auth/me'),
  logout: () => client.post('/auth/logout'),
}

export const emailsApi = {
  list: (params: { page?: number; page_size?: number; category_id?: number; status?: string; is_read?: boolean; search?: string }) =>
    client.get('/emails', { params }),
  get: (id: number) => client.get(`/emails/${id}`),
  update: (id: number, data: { is_read?: boolean; is_starred?: boolean; category_id?: number; status?: string }) =>
    client.patch(`/emails/${id}`, data),
  sync: () => client.post('/emails/sync'),
}

export interface Email {
  id: number
  gmail_message_id: string
  subject: string | null
  sender: string | null
  sender_email: string | null
  snippet: string | null
  body_text: string | null
  status: string
  category_id: number | null
  is_read: boolean
  is_starred: boolean
  classification_confidence: number | null
  classification_reason: string | null
  received_at: string | null
  category?: {
    id: number
    name: string
    color: string
  }
}

export interface Thread {
  id: number
  gmail_thread_id: string
  subject: string | null
  snippet: string | null
  status: string
  category_id: number | null
  is_read: boolean
  is_starred: boolean
  classification_confidence: number | null
  classification_reason: string | null
  participant_count: number
  message_count: number
  last_message_at: string | null
  deadline: string | null
  created_at: string
  category?: {
    id: number
    name: string
    color: string
  }
}

export interface ThreadWithEmails extends Thread {
  emails: EmailInThread[]
}

export interface EmailInThread {
  id: number
  gmail_message_id: string
  sender: string | null
  sender_email: string | null
  snippet: string | null
  body_text: string | null
  body_html: string | null
  is_read: boolean
  is_starred: boolean
  received_at: string | null
}

export const threadsApi = {
  list: (params: { page?: number; page_size?: number; category_id?: number; status?: string; is_read?: boolean; search?: string }) =>
    client.get('/threads', { params }),
  get: (id: number) => client.get<ThreadWithEmails>(`/threads/${id}`),
  update: (id: number, data: { is_read?: boolean; is_starred?: boolean; category_id?: number; status?: string }) =>
    client.patch(`/threads/${id}`, data),
}

export const categoriesApi = {
  list: () => client.get('/categories'),
  create: (data: { name: string; description?: string; color?: string }) =>
    client.post('/categories', data),
  update: (id: number, data: { name?: string; description?: string; color?: string; is_active?: boolean }) =>
    client.patch(`/categories/${id}`, data),
  delete: (id: number) => client.delete(`/categories/${id}`),
}

export const feedbackApi = {
  create: (data: { 
    email_id?: number; 
    original_category?: string; 
    corrected_category?: string;
    corrected_status?: string;
    confidence_score?: number;
    user_comment?: string 
  }) => client.post('/feedback', data),
  
  correctStatus: (emailId: number, status: string, comment?: string) => 
    client.post('/feedback/correct-status', null, {
      params: { email_id: emailId, correct_status: status, comment }
    }),
    
  list: () => client.get('/feedback'),
}

export default client
