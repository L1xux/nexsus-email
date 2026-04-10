import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

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
      localStorage.removeItem('token')
      window.location.href = '/login'
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
