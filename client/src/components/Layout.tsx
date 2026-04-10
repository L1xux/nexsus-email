import { useEffect, useState } from 'react'
import { Outlet, useLocation, Link } from 'react-router-dom'
import { 
  Inbox, 
  Settings, 
  RefreshCw, 
  LogOut, 
  Mail,
  ChevronDown,
  Archive,
  CheckCircle2,
  Clock
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { authApi, categoriesApi, emailsApi } from '../api/client'

interface Category {
  id: number
  name: string
  color: string
}

export default function Layout() {
  const location = useLocation()
  const { user, logout, setUser } = useAuthStore()
  const [categories, setCategories] = useState<Category[]>([])
  const [syncing, setSyncing] = useState(false)
  const [showCategories, setShowCategories] = useState(false)

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const { data } = await authApi.getMe()
        setUser(data)
      } catch (error) {
        console.error('Failed to fetch user')
      }
    }
    if (!user) {
      fetchUser()
    }
  }, [])

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const { data } = await categoriesApi.list()
        setCategories(data)
      } catch (error) {
        console.error('Failed to fetch categories')
      }
    }
    fetchCategories()
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await emailsApi.sync()
    } catch (error) {
      console.error('Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch (error) {
      // Ignore
    }
    logout()
  }

  const navItems = [
    { path: '/', icon: Inbox, label: 'Inbox' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ]

  return (
    <div className="min-h-screen bg-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-zinc-200 sticky top-0 z-50 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 border border-zinc-300 rounded-lg flex items-center justify-center">
                <Mail className="w-5 h-5" />
              </div>
              <span className="text-lg font-semibold">NexusMail</span>
            </div>

            {/* Navigation Links */}
            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname === item.path
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-black text-white'
                        : 'text-zinc-600 hover:bg-zinc-100'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </Link>
                )
              })}
            </nav>

            {/* Right Actions */}
            <div className="flex items-center gap-3">
              {/* Categories Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowCategories(!showCategories)}
                  className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg"
                >
                  <Archive className="w-4 h-4" />
                  Categories
                  <ChevronDown className="w-4 h-4" />
                </button>
                
                {showCategories && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-zinc-200 py-1 z-50">
                    <div className="px-3 py-2 text-xs font-medium text-zinc-500 uppercase">
                      Your Categories
                    </div>
                    {categories.map((cat) => (
                      <Link
                        key={cat.id}
                        to={`/?category=${cat.id}`}
                        onClick={() => setShowCategories(false)}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
                      >
                        <span 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: cat.color }}
                        />
                        {cat.name}
                      </Link>
                    ))}
                    {categories.length === 0 && (
                      <div className="px-3 py-2 text-sm text-zinc-500">
                        No categories yet
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Sync Button */}
              <button
                onClick={handleSync}
                disabled={syncing}
                className="flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
                {syncing ? 'Syncing...' : 'Sync'}
              </button>

              {/* User Menu */}
              <div className="flex items-center gap-3 pl-3 border-l border-zinc-200">
                <div className="w-8 h-8 bg-zinc-100 rounded-full flex items-center justify-center">
                  {user?.picture ? (
                    <img src={user.picture} alt="" className="w-8 h-8 rounded-full" />
                  ) : (
                    <span className="text-zinc-600 font-medium text-sm">
                      {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || '?'}
                    </span>
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  className="p-2 text-zinc-500 hover:text-black hover:bg-zinc-100 rounded-lg"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Status Tabs */}
      <div className="border-b border-zinc-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex gap-1 h-12">
            <StatusTab 
              icon={Inbox} 
              label="Inbox" 
              path="/" 
              active={location.pathname === '/' && !location.search}
            />
            <StatusTab 
              icon={CheckCircle2} 
              label="ToDo" 
              path="/?status=todo" 
              active={location.search.includes('status=todo')}
            />
            <StatusTab 
              icon={Clock} 
              label="Waiting" 
              path="/?status=waiting" 
              active={location.search.includes('status=waiting')}
            />
            <StatusTab 
              icon={Archive} 
              label="Done" 
              path="/?status=done" 
              active={location.search.includes('status=done')}
            />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>
    </div>
  )
}

function StatusTab({ icon: Icon, label, path, active }: any) {
  const isActive = active || (path === '/' && location.pathname === '/' && !location.search)
  
  return (
    <Link
      to={path}
      className={`flex items-center gap-2 px-4 text-sm font-medium border-b-2 transition-colors ${
        isActive
          ? 'border-black text-black'
          : 'border-transparent text-zinc-500 hover:text-zinc-700'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </Link>
  )
}
