import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { 
  Inbox, 
  CheckCircle2, 
  Clock, 
  Archive, 
  Star, 
  ChevronRight,
  Loader2,
  RefreshCw
} from 'lucide-react'
import { emailsApi, feedbackApi, categoriesApi } from '../api/client'
import clsx from 'clsx'

interface Email {
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

interface Category {
  id: number
  name: string
  color: string
}

const STATUS_CONFIG = {
  inbox: { label: 'Inbox', icon: Inbox },
  todo: { label: 'ToDo', icon: CheckCircle2 },
  waiting: { label: 'Waiting', icon: Clock },
  done: { label: 'Done', icon: Archive },
}

export default function Dashboard() {
  const [searchParams] = useSearchParams()
  const [emails, setEmails] = useState<Email[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState<number | null>(null)
  const [draggedEmailId, setDraggedEmailId] = useState<number | null>(null)

  const currentStatus = searchParams.get('status') as keyof typeof STATUS_CONFIG | null
  const currentCategory = searchParams.get('category')

  useEffect(() => {
    setFilterStatus(currentStatus)
    setFilterCategory(currentCategory ? parseInt(currentCategory) : null)
  }, [currentStatus, currentCategory])

  const fetchEmails = useCallback(async () => {
    setLoading(true)
    console.log('Fetching emails...')
    try {
      const params: Record<string, unknown> = { page: 1, page_size: 100 }
      if (filterStatus) params.status = filterStatus
      if (filterCategory) params.category_id = filterCategory
      
      const { data } = await emailsApi.list(params as any)
      console.log('API returned emails:', data.emails.length)
      setEmails(data.emails)
    } catch (error) {
      console.log('Using mock data (API unavailable)')
      setEmails([
        { id: 1, gmail_message_id: '1', subject: 'Welcome to our service', sender: 'Team', sender_email: 'team@example.com', snippet: 'Thanks for joining us', body_text: '', status: 'inbox', category_id: null, is_read: false, is_starred: false, classification_confidence: 0.9, classification_reason: 'Welcome email', received_at: new Date().toISOString() },
        { id: 2, gmail_message_id: '2', subject: 'Your order #12345', sender: 'Shop', sender_email: 'shop@example.com', snippet: 'Order confirmed', body_text: '', status: 'inbox', category_id: null, is_read: false, is_starred: false, classification_confidence: 0.8, classification_reason: 'Order notification', received_at: new Date().toISOString() },
        { id: 3, gmail_message_id: '3', subject: 'Meeting tomorrow', sender: 'John', sender_email: 'john@example.com', snippet: 'Lets discuss the project', body_text: '', status: 'inbox', category_id: null, is_read: true, is_starred: false, classification_confidence: 0.7, classification_reason: 'Meeting request', received_at: new Date().toISOString() },
        { id: 4, gmail_message_id: '4', subject: 'Newsletter: Weekly updates', sender: 'News', sender_email: 'news@example.com', snippet: 'This week in tech...', body_text: '', status: 'todo', category_id: null, is_read: false, is_starred: true, classification_confidence: 0.85, classification_reason: 'Newsletter', received_at: new Date().toISOString() },
        { id: 5, gmail_message_id: '5', subject: 'Invoice attached', sender: 'Finance', sender_email: 'finance@example.com', snippet: 'Please find attached', body_text: '', status: 'done', category_id: null, is_read: true, is_starred: false, classification_confidence: 0.95, classification_reason: 'Invoice', received_at: new Date().toISOString() },
      ])
    } finally {
      setLoading(false)
    }
  }, [filterStatus, filterCategory])

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const { data } = await categoriesApi.list()
        setCategories(data)
      } catch (error) {
        console.error('Failed to fetch categories, using mock:', error)
        setCategories([
          { id: 1, name: 'Work', color: '#3b82f6' },
          { id: 2, name: 'Personal', color: '#10b981' },
          { id: 3, name: 'Shopping', color: '#f59e0b' },
        ])
      }
    }
    fetchCategories()
  }, [])

  useEffect(() => {
    fetchEmails()
  }, [fetchEmails])

  const handleStatusChange = async (emailId: number, newStatus: string) => {
    setEmails(emails.map(e => 
      e.id === emailId ? { ...e, status: newStatus } : e
    ))
    try {
      await feedbackApi.correctStatus(emailId, newStatus)
    } catch (error) {
      console.log('API unavailable, updated locally only')
    }
  }

  const handleDragStart = (emailId: number) => {
    setDraggedEmailId(emailId)
  }

  const handleDragEnd = () => {
    setDraggedEmailId(null)
  }

  const handleDrop = (newStatus: string, e: React.DragEvent) => {
    e.preventDefault()
    if (draggedEmailId) {
      handleStatusChange(draggedEmailId, newStatus)
      setDraggedEmailId(null)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleStar = async (email: Email, e: React.MouseEvent) => {
    e.stopPropagation()
    setEmails(emails.map(em => 
      em.id === email.id ? { ...em, is_starred: !em.is_starred } : em
    ))
    try {
      await emailsApi.update(email.id, { is_starred: !email.is_starred })
    } catch (error) {
      console.log('API unavailable, updated locally only')
    }
  }

  const groupedEmails = filterStatus 
    ? { [filterStatus]: emails }
    : {
        todo: emails.filter(e => e.status === 'todo'),
        waiting: emails.filter(e => e.status === 'waiting'),
        done: emails.filter(e => e.status === 'done'),
        inbox: emails.filter(e => e.status === 'inbox'),
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
              {emails.length} emails
            </span>
          </h2>
          <button
            onClick={fetchEmails}
            className="p-2 hover:bg-black hover:text-white transition-colors rounded"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        
        <div className="space-y-0 divide-y divide-black">
          {emails.length === 0 ? (
            <div className="text-center py-16 text-zinc-400 text-sm">
              No emails found
            </div>
          ) : (
            emails.map(email => (
              <EmailCard 
                key={email.id} 
                email={email} 
                categories={categories}
                onStatusChange={handleStatusChange}
                onStar={handleStar}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                isDragging={draggedEmailId === email.id}
              />
            ))
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 gap-px bg-black" style={{ minHeight: 'calc(100vh - 220px)' }}>
      {(['todo', 'waiting', 'done', 'inbox'] as const).map(status => {
        const config = STATUS_CONFIG[status]
        const Icon = config.icon
        const statusEmails = groupedEmails[status] || []
        
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
                {statusEmails.length}
              </span>
            </div>
            
            <div className="flex-1 overflow-y-auto p-2 space-y-px">
              {statusEmails.length === 0 ? (
                <div className="text-center py-8 text-zinc-400 text-sm">
                  Empty
                </div>
              ) : (
                  statusEmails.map(email => (
                    <EmailCard 
                      key={email.id} 
                      email={email}
                      categories={categories}
                      compact
                      onStatusChange={handleStatusChange}
                      onStar={handleStar}
                      onDragStart={handleDragStart}
                      onDragEnd={handleDragEnd}
                      isDragging={draggedEmailId === email.id}
                    />
                  ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

interface EmailCardProps {
  email: Email
  categories: Category[]
  compact?: boolean
  onStatusChange: (emailId: number, status: string) => void
  onStar: (email: Email, e: React.MouseEvent) => void
  onDragStart: (emailId: number) => void
  onDragEnd: () => void
  isDragging?: boolean
}

function EmailCard({ email, categories, compact = false, onStatusChange, onStar, onDragStart, onDragEnd, isDragging }: EmailCardProps) {
  const [showStatusMenu, setShowStatusMenu] = useState(false)
  
  const category = categories.find(c => c.id === email.category_id)
  const statusConfig = STATUS_CONFIG[email.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.inbox
  
  const getConfidenceStyle = (confidence: number | null) => {
    if (!confidence) return { color: 'text-zinc-400', label: '' }
    if (confidence >= 0.8) return { color: 'text-black', label: 'High' }
    if (confidence >= 0.6) return { color: 'text-zinc-600', label: 'Med' }
    return { color: 'text-zinc-400', label: 'Low' }
  }

  return (
    <div 
      draggable
      onDragStart={() => onDragStart(email.id)}
      onDragEnd={onDragEnd}
      className={clsx(
        'bg-white transition-all hover:bg-zinc-50 cursor-grab active:cursor-grabbing',
        compact ? 'p-3' : 'p-4',
        !email.is_read && 'border-l-2 border-l-black',
        isDragging && 'opacity-50'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {!email.is_read && (
              <span className="w-1.5 h-1.5 bg-black rounded-full flex-shrink-0" />
            )}
            <span className={clsx('text-sm truncate', email.is_read ? 'text-zinc-500' : 'font-medium text-black')}>
              {email.sender || email.sender_email || 'Unknown'}
            </span>
          </div>
          
          <h3 className={clsx(
            'text-black truncate',
            compact ? 'text-sm' : 'text-base font-medium'
          )}>
            {email.subject || '(No Subject)'}
          </h3>
          
          {!compact && email.snippet && (
            <p className="text-sm text-zinc-500 mt-1 line-clamp-2">
              {email.snippet}
            </p>
          )}
          
          {email.classification_confidence && !compact && (
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 bg-black text-white rounded-sm font-medium">
                {statusConfig.label}
              </span>
              <span className={clsx('text-xs font-medium', getConfidenceStyle(email.classification_confidence).color)}>
                {getConfidenceStyle(email.classification_confidence).label}
              </span>
            </div>
          )}
          
          {email.classification_reason && !compact && (
            <p className="text-xs text-zinc-400 mt-2 italic">
              {email.classification_reason}
            </p>
          )}
          
          {category && (
            <span 
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-sm mt-3 border border-black"
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: category.color }} />
              {category.name}
            </span>
          )}
        </div>
        
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={(e) => onStar(email, e)}
            className="p-1 hover:bg-black hover:text-white transition-colors rounded"
          >
            {email.is_starred ? (
              <Star className="w-4 h-4 fill-black text-black" />
            ) : (
              <Star className="w-4 h-4 text-zinc-300" />
            )}
          </button>
          
          <div className="relative">
            <button
              onClick={() => setShowStatusMenu(!showStatusMenu)}
              className="p-1 hover:bg-black hover:text-white transition-colors rounded"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            
            {showStatusMenu && (
              <div className="absolute right-0 mt-1 w-32 bg-white border border-black rounded-sm py-0.5 z-10 shadow-none">
                {Object.entries(STATUS_CONFIG).map(([key, config]) => {
                  const Icon = config.icon
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        onStatusChange(email.id, key)
                        setShowStatusMenu(false)
                      }}
                      className={clsx(
                        'w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left hover:bg-black hover:text-white transition-colors',
                        key === email.status ? 'bg-zinc-100' : ''
                      )}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {config.label}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
      
      {email.received_at && (
        <div className="text-xs text-zinc-400 mt-3 pt-2 border-t border-zinc-100">
          {new Date(email.received_at).toLocaleDateString()}
        </div>
      )}
    </div>
  )
}
