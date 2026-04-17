import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Inbox,
  CheckCircle2,
  Clock,
  Archive,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { threadsApi, type Thread, type Category } from '../api/client'
import ThreadModal from '../components/ThreadModal'

const STATUS_CONFIG = {
  inbox: { label: 'Inbox', icon: Inbox },
  todo: { label: 'ToDo', icon: CheckCircle2 },
  waiting: { label: 'Waiting', icon: Clock },
  done: { label: 'Done', icon: Archive },
}

export default function Dashboard() {
  const [searchParams] = useSearchParams()
  const [threads, setThreads] = useState<Thread[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState<number | null>(null)
  const [draggedThreadId, setDraggedThreadId] = useState<number | null>(null)
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null)

  const currentStatus = searchParams.get('status') as keyof typeof STATUS_CONFIG | null
  const currentCategory = searchParams.get('category')

  useEffect(() => {
    setFilterStatus(currentStatus)
    setFilterCategory(currentCategory ? parseInt(currentCategory) : null)
  }, [currentStatus, currentCategory])

  const fetchThreads = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page: 1, page_size: 200 }
      if (filterStatus) params.status = filterStatus
      if (filterCategory) params.category_id = filterCategory

      const { data } = await threadsApi.list({ ...params, page_size: Math.min(Number(params.page_size) || 100, 100) } as any)
      setThreads(data.threads)
    } catch {
      setThreads([])
    } finally {
      setLoading(false)
    }
  }, [filterStatus, filterCategory])

  useEffect(() => {
    fetchThreads()
  }, [fetchThreads])

  const handleStatusChange = async (threadId: number, newStatus: string) => {
    setThreads(threads.map(t =>
      t.id === threadId ? { ...t, status: newStatus } : t
    ))
    if (selectedThreadId === threadId) {
      setThreads(prev => prev.map(t =>
        t.id === threadId ? { ...t, status: newStatus } : t
      ))
    }
    try {
      await threadsApi.update(threadId, { status: newStatus as any })
    } catch {
      fetchThreads()
    }
  }

  const handleDragStart = (threadId: number) => setDraggedThreadId(threadId)
  const handleDragEnd = () => setDraggedThreadId(null)

  const handleDrop = (newStatus: string, e: React.DragEvent) => {
    e.preventDefault()
    if (draggedThreadId) {
      handleStatusChange(draggedThreadId, newStatus)
      setDraggedThreadId(null)
    }
  }

  const handleDragOver = (e: React.DragEvent) => e.preventDefault()

  const groupedThreads = filterStatus
    ? { [filterStatus]: threads }
    : {
        todo: threads.filter(t => t.status === 'todo'),
        waiting: threads.filter(t => t.status === 'waiting'),
        done: threads.filter(t => t.status === 'done'),
        inbox: threads.filter(t => t.status === 'inbox'),
      }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    )
  }

  if (filterStatus || filterCategory) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-black">
          <h2 className="text-xl font-medium tracking-tight">
            {filterStatus ? STATUS_CONFIG[filterStatus as keyof typeof STATUS_CONFIG]?.label : 'Category'}
            <span className="ml-3 font-normal text-zinc-400 text-sm">
              {threads.length} threads
            </span>
          </h2>
          <button
            onClick={fetchThreads}
            className="p-2 hover:bg-black hover:text-white transition-colors rounded"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-0 divide-y divide-black">
          {threads.length === 0 ? (
            <div className="text-center py-16 text-zinc-400 text-sm">
              No threads found
            </div>
          ) : (
            threads.map(thread => (
              <ThreadCard
                key={thread.id}
                thread={thread}
                onClick={() => setSelectedThreadId(thread.id)}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                isDragging={draggedThreadId === thread.id}
              />
            ))
          )}
        </div>

        {selectedThreadId !== null && (
          <ThreadModal
            threadId={selectedThreadId}
            onClose={() => setSelectedThreadId(null)}
            onStatusChange={handleStatusChange}
          />
        )}
      </div>
    )
  }

  return (
    <>
      <div className="grid grid-cols-4 gap-px bg-black" style={{ minHeight: 'calc(100vh - 220px)' }}>
        {(['todo', 'waiting', 'done', 'inbox'] as const).map(status => {
          const config = STATUS_CONFIG[status]
          const Icon = config.icon
          const statusThreads = groupedThreads[status] || []

          return (
            <div
              key={status}
              className="flex flex-col bg-white"
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(status, e)}
            >
              <div className="px-4 py-3 flex items-center justify-between border-b border-black bg-zinc-50">
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4" />
                  <span className="font-medium text-sm tracking-tight">{config.label}</span>
                </div>
                <span className="text-xs font-medium px-2 py-0.5 bg-black text-white rounded-sm">
                  {statusThreads.length}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto p-2 space-y-px">
                {statusThreads.length === 0 ? (
                  <div className="text-center py-8 text-zinc-400 text-sm">Empty</div>
                ) : (
                  statusThreads.map(thread => (
                    <ThreadCard
                      key={thread.id}
                      thread={thread}
                      compact
                      onClick={() => setSelectedThreadId(thread.id)}
                      onDragStart={handleDragStart}
                      onDragEnd={handleDragEnd}
                      isDragging={draggedThreadId === thread.id}
                    />
                  ))
                )}
              </div>
            </div>
          )
        })}
      </div>

      {selectedThreadId !== null && (
        <ThreadModal
          threadId={selectedThreadId}
          onClose={() => setSelectedThreadId(null)}
          onStatusChange={handleStatusChange}
        />
      )}
    </>
  )
}

interface ThreadCardProps {
  thread: Thread
  compact?: boolean
  onClick: () => void
  onDragStart: (threadId: number) => void
  onDragEnd: () => void
  isDragging?: boolean
}

function ThreadCard({ thread, compact = false, onClick, onDragStart, onDragEnd, isDragging }: ThreadCardProps) {
  const formatDeadline = (iso: string | null) => {
    if (!iso) return null
    const d = new Date(iso)
    const now = new Date()
    const diffMs = d.getTime() - now.getTime()
    if (diffMs < 0) return { label: 'OVERDUE', urgent: true }
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffDays === 0) return { label: 'Today', urgent: false }
    if (diffDays === 1) return { label: 'Tomorrow', urgent: false }
    if (diffDays < 7) return { label: `${diffDays}d`, urgent: false }
    return { label: d.toLocaleDateString([], { month: 'short', day: 'numeric' }), urgent: false }
  }

  const deadlineInfo = formatDeadline(thread.deadline)

  return (
    <div
      draggable
      onDragStart={() => onDragStart(thread.id)}
      onDragEnd={onDragEnd}
      onClick={onClick}
      className={`bg-white transition-all hover:bg-zinc-50 cursor-pointer select-none
        ${compact ? 'p-3' : 'p-4'}
        ${!thread.is_read ? 'border-l-2 border-l-black' : ''}
        ${isDragging ? 'opacity-50' : ''}
      `}
    >
      {/* Subject */}
      <h3 className={`text-black truncate ${compact ? 'text-sm' : 'text-base font-medium'} mb-1`}>
        {thread.subject || '(No Subject)'}
      </h3>

      {/* Snippet */}
      {!compact && thread.snippet && (
        <p className="text-sm text-zinc-500 line-clamp-2 mb-2">{thread.snippet}</p>
      )}

      {/* Meta row */}
      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Message count */}
          <span className="text-xs text-zinc-400">
            {thread.message_count} msg{thread.message_count !== 1 ? 's' : ''}
          </span>

          {/* Deadline badge */}
          {deadlineInfo && (
            <span
              className={`text-xs px-1.5 py-0.5 border font-medium ${
                deadlineInfo.urgent
                  ? 'border-red-600 text-red-600 bg-red-50'
                  : 'border-black text-black'
              }`}
            >
              {deadlineInfo.label}
            </span>
          )}

          {/* Category */}
          {thread.category && (
            <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 border border-black">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: thread.category.color }} />
              {thread.category.name}
            </span>
          )}
        </div>

        {/* Confidence */}
        {thread.classification_confidence && !compact && (
          <span className="text-xs text-zinc-400">
            {thread.classification_confidence >= 0.8 ? 'High' : thread.classification_confidence >= 0.6 ? 'Med' : 'Low'}
          </span>
        )}
      </div>

      {/* Last message time */}
      {thread.last_message_at && (
        <div className="text-xs text-zinc-400 mt-2 pt-2 border-t border-zinc-100">
          {new Date(thread.last_message_at).toLocaleDateString()}
        </div>
      )}
    </div>
  )
}
