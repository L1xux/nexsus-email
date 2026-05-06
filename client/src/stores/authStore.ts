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
  lastSyncedAt: number | null
  setToken: (token: string) => void
  setUser: (user: User) => void
  setSyncedAt: (t: number) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  lastSyncedAt: null,
  setToken: (token: string) => {
    localStorage.setItem('token', token)
    set({ token })
  },
  setUser: (user: User) => {
    localStorage.setItem('user', JSON.stringify(user))
    set({ user })
  },
  setSyncedAt: (t: number) => set({ lastSyncedAt: t }),
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ token: null, user: null })
  },
}))
