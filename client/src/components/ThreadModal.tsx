import { useEffect, useState, useRef } from 'react'
import { X, Star, ExternalLink, Tag, ChevronDown } from 'lucide-react'
import { threadsApi, categoriesApi, type ThreadWithEmails, type Category } from '../api/client'

interface ThreadModalProps {
  threadId: number
  onClose: () => void
  onStatusChange: (threadId: number, newStatus: string) => void
  onCategoryChange?: (threadId: number, categoryId: number | null, category: Category | null) => void
}

export default function ThreadModal({ threadId, onClose, onStatusChange, onCategoryChange }: ThreadModalProps) {
  const [thread, setThread] = useState<ThreadWithEmails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryOpen, setCategoryOpen] = useState(false)
  const [savingCategory, setSavingCategory] = useState(false)
  const categoryRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    threadsApi.get(threadId)
      .then(res => setThread(res.data))
      .catch(() => setError('Failed to load thread'))
      .finally(() => setLoading(false))
    categoriesApi.list().then(res => setCategories(res.data)).catch(() => {})
  }, [threadId])

  // Close category dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (categoryRef.current && !categoryRef.current.contains(e.target as Node)) {
        setCategoryOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleCategorySelect = async (cat: Category | null) => {
    if (!thread) return
    setCategoryOpen(false)
    setSavingCategory(true)
    try {
      await threadsApi.update(thread.id, { category_id: cat?.id ?? null })
      const updated = { ...thread, category_id: cat?.id ?? null, category: cat ?? undefined }
      setThread(updated as ThreadWithEmails)
      onCategoryChange?.(thread.id, cat?.id ?? null, cat)
    } catch {
      // silent — UI stays consistent
    } finally {
      setSavingCategory(false)
    }
  }

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const formatDate = (iso: string | null) => {
    if (!iso) return ''
    const d = new Date(iso)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000)
    if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return d.toLocaleDateString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  const formatDeadline = (iso: string | null) => {
    if (!iso) return null
    const d = new Date(iso)
    const now = new Date()
    const diffMs = d.getTime() - now.getTime()
    const diffDays = Math.floor(diffMs / 86400000)
    const label = d.toLocaleDateString([], { month: 'short', day: 'numeric' })
    if (diffMs < 0) return { label, urgent: true }
    if (diffDays === 0) return { label: `Today by ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`, urgent: false }
    if (diffDays === 1) return { label: `Tomorrow`, urgent: false }
    return { label, urgent: false }
  }

  const deadlineInfo = thread?.deadline ? formatDeadline(thread.deadline) : null

  const getConfidenceLabel = (confidence: number | null) => {
    if (!confidence) return null
    if (confidence >= 0.8) return 'High'
    if (confidence >= 0.6) return 'Med'
    return 'Low'
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center"
      style={{ background: 'rgba(0,0,0,0.85)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="flex flex-col bg-white w-full max-w-3xl mx-4 my-8 overflow-hidden"
        style={{ maxHeight: 'calc(100vh - 4rem)' }}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-black flex-shrink-0">
          <div className="flex-1 min-w-0 pr-4">
            <h2 className="text-base font-medium truncate pr-4">
              {thread?.subject || '(No Subject)'}
            </h2>
            <div className="flex items-center gap-3 mt-1">
              {deadlineInfo && (
                <span
                  className="text-xs px-2 py-0.5 border border-black font-medium"
                  style={deadlineInfo.urgent ? { background: '#000', color: '#fff' } : {}}
                >
                  {deadlineInfo.label}
                </span>
              )}
              {thread?.classification_reason && (
                <span className="text-xs text-zinc-500 truncate max-w-xs">
                  {thread.classification_reason}
                </span>
              )}
              {thread?.classification_confidence && (
                <span className="text-xs text-zinc-400">
                  {getConfidenceLabel(thread.classification_confidence)} {Math.round(thread.classification_confidence * 100)}%
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-black hover:text-white transition-colors flex-shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center h-48">
              <span className="text-zinc-400 text-sm">Loading…</span>
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-48">
              <span className="text-zinc-400 text-sm">{error}</span>
            </div>
          )}
          {!loading && thread && (
            <div className="px-6 py-4 space-y-6">
              {thread.emails.map((email) => {
                const isRead = email.is_read
                return (
                  <div key={email.id} className="flex gap-3">
                    {/* Avatar circle */}
                    <div className="flex-shrink-0 w-8 h-8 border border-black rounded-full flex items-center justify-center text-xs font-medium uppercase mt-0.5">
                      {(email.sender_email || email.sender || '?')[0]}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 mb-1">
                        <span className={`text-sm font-medium ${isRead ? 'text-zinc-500' : 'text-black'}`}>
                          {email.sender_email || email.sender || 'Unknown'}
                        </span>
                        <span className="text-xs text-zinc-400">
                          {formatDate(email.received_at)}
                        </span>
                        {email.is_starred && (
                          <Star className="w-3 h-3 fill-black text-black" />
                        )}
                      </div>
                      {(email.body_text || email.snippet) && (
                        <p className="text-sm text-zinc-600 leading-relaxed whitespace-pre-wrap">
                          {email.body_text || email.snippet}
                        </p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        {!loading && thread && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-black flex-shrink-0 bg-zinc-50 gap-4">
            {/* Status buttons */}
            <div className="flex items-center gap-2">
              {['todo', 'waiting', 'done'].map(s => (
                <button
                  key={s}
                  onClick={() => onStatusChange(thread.id, s)}
                  className={`text-xs px-3 py-1 border transition-colors ${
                    thread.status === s
                      ? 'bg-black text-white border-black'
                      : 'border-black text-black hover:bg-black hover:text-white'
                  }`}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>

            {/* Category selector */}
            <div className="relative flex-shrink-0" ref={categoryRef}>
              <button
                onClick={() => setCategoryOpen(o => !o)}
                disabled={savingCategory}
                className="flex items-center gap-1.5 text-xs px-3 py-1 border border-black hover:bg-black hover:text-white transition-colors disabled:opacity-50"
              >
                {thread.category ? (
                  <>
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: thread.category.color }}
                    />
                    <span>{thread.category.name}</span>
                  </>
                ) : (
                  <>
                    <Tag className="w-3 h-3" />
                    <span>카테고리</span>
                  </>
                )}
                <ChevronDown className="w-3 h-3" />
              </button>

              {categoryOpen && (
                <div className="absolute bottom-full mb-1 right-0 w-44 bg-white border border-black z-10">
                  <button
                    onClick={() => handleCategorySelect(null)}
                    className="w-full text-left px-3 py-2 text-xs text-zinc-500 hover:bg-zinc-100 transition-colors"
                  >
                    없음
                  </button>
                  {categories.map(cat => (
                    <button
                      key={cat.id}
                      onClick={() => handleCategorySelect(cat)}
                      className={`w-full text-left flex items-center gap-2 px-3 py-2 text-xs hover:bg-zinc-100 transition-colors ${
                        thread.category?.id === cat.id ? 'font-medium' : ''
                      }`}
                    >
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: cat.color }}
                      />
                      {cat.name}
                      {thread.category?.id === cat.id && (
                        <span className="ml-auto text-black">✓</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <a
              href={`https://mail.google.com/mail/u/0/#inbox/${thread.gmail_thread_id}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-black transition-colors flex-shrink-0"
            >
              <ExternalLink className="w-3 h-3" />
              Gmail
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
