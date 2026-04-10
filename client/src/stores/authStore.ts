import { create } from 'zustand'

interface User {
  id: number
  email: string
  name: string | null
  picture: string | null
}

interface AuthState {
  token: string | null
  user: User | null
  setToken: (token: string) => void
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: null,
  setToken: (token: string) => {
    localStorage.setItem('token', token)
    set({ token })
  },
  setUser: (user: User) => set({ user }),
  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null })
  },
}))
