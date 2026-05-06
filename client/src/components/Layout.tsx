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
  Clock,
  Loader2
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { authApi, categoriesApi, API_BASE_URL } from '../api/client'

interface Category {
  id: number
  name: string
  color: string
}

export default function Layout() {
  const location = useLocation()
  const { user, logout, setUser, setSyncedAt } = useAuthStore()
  const [categories, setCategories] = useState<Category[]>([])
  const [showCategories, setShowCategories] = useState(false)
  const [showSyncModal, setShowSyncModal] = useState(false)
  const [syncStep, setSyncStep] = useState<'picker' | 'syncing' | 'done'>('picker')
  const [syncFromDate, setSyncFromDate] = useState('')
  const [syncToDate, setSyncToDate] = useState('')
  const [syncProgress, setSyncProgress] = useState<{ chunk: number; total: number; from_date: string; to_date: string } | null>(null)
  const [syncTotalNew, setSyncTotalNew] = useState(0)

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
    if (!sessionStorage.getItem('justLoggedIn')) return
    sessionStorage.removeItem('justLoggedIn')

    const { from, to } = getDefaultDates()
    setSyncFromDate(from)
    setSyncToDate(to)
    setShowSyncModal(true)
    executeStreamSync(from, to)
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

  const getDefaultDates = () => {
    const today = new Date()
    const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
    return {
      from: sevenDaysAgo.toISOString().slice(0, 10),
      to: today.toISOString().slice(0, 10),
    }
  }

  const executeStreamSync = async (from: string, to: string) => {
    setSyncStep('syncing')
    setSyncProgress(null)
    setSyncTotalNew(0)

    const token = localStorage.getItem('token')
    const params = new URLSearchParams({ from_date: from, to_date: to })

    try {
      const response = await fetch(`${API_BASE_URL}/api/emails/sync-stream?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok || !response.body) throw new Error('Sync request failed')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.done) {
              setSyncStep('done')
            } else if (!data.error) {
              setSyncProgress({ chunk: data.chunk, total: data.total, from_date: data.from_date, to_date: data.to_date })
              setSyncTotalNew(prev => prev + (data.new_count ?? 0))
              setSyncedAt(Date.now())
            }
          } catch {}
        }
      }
    } catch (error) {
      console.error('Sync error:', error)
    }
    setSyncStep('done')
  }

  const handleSync = () => {
    const { from, to } = getDefaultDates()
    setSyncFromDate(from)
    setSyncToDate(to)
    setSyncStep('picker')
    setSyncProgress(null)
    setSyncTotalNew(0)
    setShowSyncModal(true)
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
      {showSyncModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white border border-zinc-200 rounded-xl shadow-xl px-8 py-6 flex flex-col gap-5 w-[340px]">
            <h2 className="text-base font-semibold text-black">이메일 동기화</h2>

            {syncStep === 'picker' && (
              <>
                <div className="flex flex-col gap-3">
                  <label className="flex flex-col gap-1 text-sm text-zinc-600">
                    시작일
                    <input
                      type="date"
                      value={syncFromDate}
                      onChange={e => setSyncFromDate(e.target.value)}
                      className="border border-zinc-200 rounded px-3 py-1.5 text-sm text-black focus:outline-none focus:border-black"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-600">
                    종료일
                    <input
                      type="date"
                      value={syncToDate}
                      onChange={e => setSyncToDate(e.target.value)}
                      className="border border-zinc-200 rounded px-3 py-1.5 text-sm text-black focus:outline-none focus:border-black"
                    />
                  </label>
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setShowSyncModal(false)}
                    className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
                  >
                    취소
                  </button>
                  <button
                    onClick={() => executeStreamSync(syncFromDate, syncToDate)}
                    className="px-4 py-2 text-sm bg-black text-white rounded-lg hover:bg-zinc-800 transition-colors"
                  >
                    시작
                  </button>
                </div>
              </>
            )}

            {syncStep === 'syncing' && (
              <div className="flex flex-col items-center gap-3 py-2">
                <Loader2 className="w-7 h-7 animate-spin text-black" />
                {syncProgress ? (
                  <div className="text-center">
                    <p className="text-sm font-medium text-black">
                      {syncProgress.from_date} ~ {syncProgress.to_date}
                    </p>
                    <p className="text-xs text-zinc-500 mt-1">
                      {syncProgress.chunk} / {syncProgress.total} 청크 진행 중...
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-zinc-500">동기화 준비 중...</p>
                )}
              </div>
            )}

            {syncStep === 'done' && (
              <div className="flex flex-col items-center gap-3 py-2">
                <CheckCircle2 className="w-7 h-7 text-black" />
                <div className="text-center">
                  <p className="text-sm font-medium text-black">동기화 완료!</p>
                  <p className="text-xs text-zinc-500 mt-1">새 이메일 {syncTotalNew}개</p>
                </div>
                <button
                  onClick={() => { setShowSyncModal(false); setSyncStep('picker') }}
                  className="px-4 py-2 text-sm bg-black text-white rounded-lg hover:bg-zinc-800 transition-colors"
                >
                  닫기
                </button>
              </div>
            )}
          </div>
        </div>
      )}
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
                disabled={showSyncModal && syncStep === 'syncing'}
                className="flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${showSyncModal && syncStep === 'syncing' ? 'animate-spin' : ''}`} />
                {showSyncModal && syncStep === 'syncing' ? 'Syncing...' : 'Sync'}
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
