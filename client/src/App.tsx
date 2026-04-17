import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import Layout from './components/Layout'
import { useAuthStore } from './stores/authStore'

function AuthCallback() {
  const { setToken, setUser } = useAuthStore()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const userId = params.get('user_id')
    const email = params.get('email')
    const name = params.get('name')
    const picture = params.get('picture')

    if (token && email) {
      const user = { id: Number(userId), email, name, picture }
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
      setToken(token)
      setUser(user)
      // Use window.location.replace so this navigation cannot be
      // interrupted by React StrictMode double-invocation in dev.
      window.location.replace('/')
    } else {
      window.location.replace('/login')
    }
  }, [setToken, setUser])

  return null
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        path="/"
        element={
          <Layout />
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
