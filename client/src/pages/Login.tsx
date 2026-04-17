import { useState } from 'react'
import { Mail, Loader2 } from 'lucide-react'
import { authApi } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { useNavigate } from 'react-router-dom'

export default function Login() {
  const { setToken, setUser } = useAuthStore()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isDev = window.location.port === '5174'
  const urlParams = new URLSearchParams(window.location.search)
  const googleRequired = urlParams.get('google_required') === 'true'

  const handleDevLogin = async () => {
    setLoading(true)
    try {
      const devUser = {
        id: 1,
        email: "dev@nexusmail.local",
        name: "Dev User",
        picture: null,
      }
      const devToken = "dev-token"
      localStorage.setItem('token', devToken)
      localStorage.setItem('user', JSON.stringify(devUser))
      setToken(devToken)
      setUser(devUser)
      navigate('/')
    } catch (err) {
      setError('Dev login failed')
    }
    setLoading(false)
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await authApi.getGoogleAuthUrl()
      window.location.href = data.url
    } catch (err: unknown) {
      console.error('Login error:', err)
      const errorMessage = err && typeof err === 'object' && 'response' in err 
        ? (err.response as { data?: { detail?: string } })?.data?.detail 
        : 'Failed to initiate login'
      setError(errorMessage || 'Failed to initiate login')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-black flex">
      {/* Left Side - Dark */}
      <div className="hidden lg:flex lg:w-1/2 bg-black flex-col justify-center px-16 border-r border-zinc-800">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 border border-zinc-700 rounded-xl flex items-center justify-center">
            <Mail className="w-6 h-6 text-white" />
          </div>
          <span className="text-2xl font-semibold text-white">NexusMail</span>
        </div>
        
        <h1 className="text-5xl font-bold text-white mb-4 leading-tight">
          Your emails,<br />
          intelligently<br />
          organized.
        </h1>
        
        <p className="text-zinc-400 text-lg max-w-md">
          AI-powered email management that learns from your feedback.
        </p>

        <div className="mt-12 space-y-4">
          <div className="flex items-center gap-3 text-zinc-400">
            <span className="w-6 h-6 border border-zinc-700 rounded-full flex items-center justify-center text-xs">1</span>
            <span>Auto-categorize into ToDo, Waiting, Done</span>
          </div>
          <div className="flex items-center gap-3 text-zinc-400">
            <span className="w-6 h-6 border border-zinc-700 rounded-full flex items-center justify-center text-xs">2</span>
            <span>Smart AI learns from your corrections</span>
          </div>
          <div className="flex items-center gap-3 text-zinc-400">
            <span className="w-6 h-6 border border-zinc-700 rounded-full flex items-center justify-center text-xs">3</span>
            <span>Focus on what matters</span>
          </div>
        </div>
      </div>

      {/* Right Side - Login */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center justify-center gap-3 mb-10">
            <div className="w-10 h-10 border-2 border-black rounded-lg flex items-center justify-center">
              <Mail className="w-5 h-5" />
            </div>
            <span className="text-xl font-semibold">NexusMail</span>
          </div>

          <h2 className="text-2xl font-semibold text-black mb-2">Welcome back</h2>
          <p className="text-zinc-500 mb-8">Sign in to continue</p>

          {googleRequired && !isDev && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-sm">
              Sync requires a connected Gmail account. Please sign in with Google to enable email sync.
            </div>
          )}

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          <button
            onClick={isDev ? handleDevLogin : handleGoogleLogin}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 px-5 py-3.5 bg-black text-white rounded-lg font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : isDev ? (
              <span>Continue as Dev User</span>
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#fff" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#fff" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#fff" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#fff" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            {isDev ? 'Continue as Dev User' : 'Continue with Google'}
          </button>

          <p className="mt-10 text-center text-xs text-zinc-400">
            By continuing, you agree to allow NexusMail<br />to access your Gmail account
          </p>
        </div>
      </div>
    </div>
  )
}
