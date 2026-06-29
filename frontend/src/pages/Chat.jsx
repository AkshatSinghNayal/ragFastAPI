import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Sun, Moon, Sparkles, ArrowLeft, Send, Search, LogOut, Loader2, MessageSquare, AlertCircle } from 'lucide-react'
import api from '../api/axios.js'
import { useAuth } from '../context/AuthContext.jsx'
import MessageBubble from '../components/MessageBubble.jsx'
import CommandMenu from '../components/CommandMenu.jsx'

function ChatSkeleton() {
  return (
    <div className="flex h-screen flex-col bg-zinc-50 dark:bg-zinc-950 animate-pulse">
      <header className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-16" />
          <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-48" />
        </div>
        <div className="h-8 bg-zinc-200 dark:bg-zinc-800 rounded w-20" />
      </header>
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="flex justify-end gap-3">
            <div className="h-12 bg-zinc-200 dark:bg-zinc-850 rounded-xl w-1/2" />
            <div className="h-8 w-8 rounded-lg bg-zinc-200 dark:bg-zinc-800" />
          </div>
          <div className="flex justify-start gap-3">
            <div className="h-8 w-8 rounded-lg bg-zinc-200 dark:bg-zinc-800" />
            <div className="h-20 bg-zinc-200 dark:bg-zinc-850 rounded-xl w-3/4" />
          </div>
          <div className="flex justify-end gap-3">
            <div className="h-16 bg-zinc-200 dark:bg-zinc-850 rounded-xl w-2/5" />
            <div className="h-8 w-8 rounded-lg bg-zinc-200 dark:bg-zinc-800" />
          </div>
        </div>
      </div>
      <div className="border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6 py-4">
        <div className="mx-auto max-w-3xl flex gap-2">
          <div className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-lg flex-1" />
          <div className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-lg w-16" />
        </div>
      </div>
    </div>
  )
}

export default function Chat() {
  const { documentId } = useParams()
  const { logout } = useAuth()
  const navigate = useNavigate()

  const [document, setDocument] = useState(null)
  const [documents, setDocuments] = useState([])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [loadingMeta, setLoadingMeta] = useState(true)
  const [isCommandOpen, setIsCommandOpen] = useState(false)
  const [theme, setTheme] = useState(() => 
    window.document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  )

  const scrollRef = useRef(null)
  const pollRef = useRef(null)

  const toggleTheme = () => {
    if (window.document.documentElement.classList.contains('dark')) {
      window.document.documentElement.classList.remove('dark')
      localStorage.theme = 'light'
      setTheme('light')
    } else {
      window.document.documentElement.classList.add('dark')
      localStorage.theme = 'dark'
      setTheme('dark')
    }
  }

  // --- Load document metadata, chat history & background document list (for Ctrl+K) ---
  const loadAll = useCallback(async () => {
    try {
      const [docRes, histRes, docsListRes] = await Promise.all([
        api.get(`/documents/${documentId}`),
        api.get(`/chat/${documentId}`),
        api.get('/documents').catch(() => ({ data: { documents: [] } }))
      ])
      setDocument(docRes.data)
      setMessages(histRes.data.messages)
      if (docsListRes?.data?.documents) {
        setDocuments(docsListRes.data.documents)
      }
    } catch (err) {
      const code = err.response?.data?.code
      const detail = err.response?.data?.detail
      if (code === 'FORBIDDEN') {
        navigate('/dashboard', { replace: true })
        return
      }
      setError(typeof detail === 'string' ? detail : 'Failed to load chat.')
    } finally {
      setLoadingMeta(false)
    }
  }, [documentId, navigate])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  // --- Poll while document is processing ---
  useEffect(() => {
    if (!document || document.status === 'ready') {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/documents/${documentId}`)
        setDocument(data)
        if (data.status === 'ready' || data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
        }
      } catch {
        // ignore transient polling errors
      }
    }, 3000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [document, documentId])

  // --- Auto-scroll to bottom on new messages ---
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Keyboard shortcuts listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setIsCommandOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  async function handleSend(e) {
    if (e) e.preventDefault()
    const question = input.trim()
    if (!question || sending) return
    if (document?.status !== 'ready') {
      setError('Document is still processing. Please wait.')
      return
    }

    setError('')
    setSending(true)

    // Optimistic append
    const optimistic = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: question,
      source_pages: null,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimistic])
    setInput('')

    try {
      const { data } = await api.post('/chat', {
        question,
        document_id: documentId,
      })
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: data.answer,
          source_pages: data.source_pages,
          created_at: new Date().toISOString(),
        },
      ])
    } catch (err) {
      const code = err.response?.data?.code
      const detail = err.response?.data?.detail
      if (code === 'DOCUMENT_NOT_READY') {
        setError('Document is still processing. Please wait a moment.')
      } else if (code === 'LLM_UNAVAILABLE') {
        setError('The language model is unavailable. Please try again.')
      } else {
        setError(typeof detail === 'string' ? detail : (err.message || 'Failed to send message.'))
      }
      // Remove optimistic message on failure
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id))
    } finally {
      setSending(false)
    }
  }

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  if (loadingMeta) {
    return <ChatSkeleton />
  }

  return (
    <div className="flex h-screen flex-col bg-zinc-50 dark:bg-zinc-950 transition-colors duration-200">
      {/* Spotlight command search */}
      <CommandMenu
        isOpen={isCommandOpen}
        onClose={() => setIsCommandOpen(false)}
        documents={documents}
        onUploadClick={() => navigate('/dashboard')}
        onLogout={handleLogout}
      />

      {/* Header */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 px-6 py-3.5 backdrop-blur-md">
        <div className="flex min-w-0 items-center gap-4">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-500 dark:text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Dashboard</span>
          </Link>
          <div className="h-4 w-px bg-zinc-250 dark:bg-zinc-800" />
          <div className="min-w-0">
            <h1 className="truncate text-xs font-bold text-zinc-900 dark:text-zinc-50 flex items-center gap-1.5 leading-none">
              {document?.filename || 'Document'}
            </h1>
            <p className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500 mt-1">
              {document?.status === 'ready' &&
                `${document.total_pages} pages · ${document.total_chunks} chunks`}
              {document?.status === 'processing' && 'Extracting text & indexing vectors…'}
              {document?.status === 'failed' && 'Ingestion failed'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick search shortcut trigger */}
          <button
            onClick={() => setIsCommandOpen(true)}
            className="hidden md:flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors"
            title="Search documents (Ctrl + K)"
          >
            <Search className="h-4 w-4" />
          </button>
          
          <button
            onClick={toggleTheme}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors"
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <button
            onClick={handleLogout}
            className="btn-secondary !py-1.5 !px-3 !text-xs font-semibold flex items-center gap-1.5"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span>Sign out</span>
          </button>
        </div>
      </header>

      {error && (
        <div className="border-b border-rose-250 dark:border-rose-950/20 bg-rose-50 dark:bg-rose-950/30 px-6 py-2.5 text-xs font-semibold text-rose-700 dark:text-rose-450 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
        className="scroll-thin flex-1 overflow-y-auto px-6 py-6 bg-zinc-50 dark:bg-zinc-950/50"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          {messages.length === 0 ? (
            <div className="card mt-12 p-8 text-center border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/10 max-w-lg mx-auto w-full">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/40 overflow-hidden shadow-sm">
                <img src="/logo.png" alt="ContextIQ" className="h-full w-full object-cover" />
              </div>
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Ask a question about this document</h3>
              <p className="mx-auto mt-2 max-w-sm text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                Enter your query below. Answers will be semantically computed using Gemini grounded in your document's text segments, including page citations.
              </p>
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
          
          {sending && (
            <div className="flex justify-start gap-3">
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900/40 overflow-hidden shadow-sm">
                <img src="/logo.png" alt="ContextIQ AI" className="h-full w-full object-cover" />
              </div>
              <div className="rounded-xl bg-white dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800/80 px-4 py-3 text-sm shadow-sm">
                <div className="flex gap-1.5 items-center py-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500" />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <form
        onSubmit={handleSend}
        className="border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6 py-4"
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800/80 rounded-xl p-1.5 focus-within:border-brand-500 dark:focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-500 transition-colors">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            rows={1}
            disabled={document?.status !== 'ready' || sending}
            placeholder={
              document?.status === 'processing'
                ? 'Document is still being processed…'
                : document?.status === 'failed'
                  ? 'This document could not be processed.'
                  : 'Ask a question about this document...'
            }
            className="block w-full resize-none bg-transparent py-2 px-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none max-h-40 min-h-[36px]"
          />
          <button
            type="submit"
            disabled={!input.trim() || sending || document?.status !== 'ready'}
            className="btn-primary !h-9 !w-9 !p-0 shrink-0 rounded-lg"
            title="Send question"
          >
            {sending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="mx-auto mt-2 max-w-3xl text-center text-[10px] font-medium text-zinc-400 dark:text-zinc-500">
          Press Enter to send, Shift+Enter for a new line. Answers are grounded in the document text.
        </p>
      </form>
    </div>
  )
}
