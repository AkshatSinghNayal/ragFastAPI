import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sun, Moon, Sparkles, Plus, Search, FileText, LogOut, Loader2, ArrowUpRight, Terminal } from 'lucide-react'
import api from '../api/axios.js'
import { useAuth } from '../context/AuthContext.jsx'
import DocumentCard from '../components/DocumentCard.jsx'
import UploadZone from '../components/UploadZone.jsx'
import CommandMenu from '../components/CommandMenu.jsx'

function DocumentCardSkeleton() {
  return (
    <div className="card flex flex-col p-4 animate-pulse border-zinc-200 dark:border-zinc-800">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-1">
          <div className="h-5 w-5 rounded bg-zinc-200 dark:bg-zinc-800 shrink-0" />
          <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-2/3" />
        </div>
        <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-12 shrink-0" />
      </div>
      <div className="mt-6 grid grid-cols-3 gap-2 border-y border-zinc-100 dark:border-zinc-800/80 py-2.5">
        <div className="h-3 bg-zinc-200 dark:bg-zinc-800 rounded w-10 mx-auto" />
        <div className="h-3 bg-zinc-200 dark:bg-zinc-800 rounded w-10 mx-auto" />
        <div className="h-3 bg-zinc-200 dark:bg-zinc-800 rounded w-10 mx-auto" />
      </div>
      <div className="mt-4 flex items-center justify-between">
        <div className="h-7 bg-zinc-200 dark:bg-zinc-800 rounded w-16" />
        <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-12" />
      </div>
    </div>
  )
}

function EmptyState({ onUploadClick }) {
  return (
    <div className="card flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/10">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400">
        <Plus className="h-6 w-6" />
      </div>
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Upload your first document</h3>
      <p className="mx-auto mt-2 max-w-sm text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
        Before you can start chatting, you need to ingest a PDF. We support file sizes up to 25 MB.
      </p>
      <div className="mt-6 flex flex-col sm:flex-row gap-3 items-center justify-center">
        <button
          type="button"
          onClick={onUploadClick}
          className="btn-primary !py-2 !px-4 gap-2 text-xs font-semibold"
        >
          <Plus className="h-4 w-4" />
          <span>Upload PDF</span>
        </button>
        <div className="flex items-center gap-1.5 text-xs text-zinc-400 dark:text-zinc-500">
          <kbd className="inline-flex h-5 items-center gap-0.5 rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-1.5 font-mono text-[10px] font-semibold">
            <span>Ctrl</span><span>+</span><span>U</span>
          </kbd>
          <span className="text-[10px]">shortcut</span>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [isCommandOpen, setIsCommandOpen] = useState(false)
  const [theme, setTheme] = useState(() => 
    window.document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  )

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

  const showToast = (message, kind = 'error') => {
    setToast({ message, kind })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchDocuments = useCallback(async () => {
    try {
      const { data } = await api.get('/documents')
      setDocuments(data.documents)
    } catch (err) {
      const detail = err.response?.data?.detail
      showToast(typeof detail === 'string' ? detail : 'Failed to load documents.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  // Poll any documents still processing so the user sees status flip to ready.
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'processing')
    if (!hasProcessing) return
    const id = setInterval(fetchDocuments, 3000)
    return () => clearInterval(id)
  }, [documents, fetchDocuments])

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setIsCommandOpen((prev) => !prev)
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
        e.preventDefault()
        document.getElementById('hidden-file-input')?.click()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  async function handleUploaded(doc) {
    setDocuments((prev) => [doc, ...prev])
    showToast('Upload received — extraction started.', 'success')
  }

  async function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.filename}"? This removes its chat history and vectors.`)) {
      return
    }
    try {
      await api.delete(`/documents/${doc.id}`)
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id))
      showToast('Document deleted.', 'success')
    } catch (err) {
      const detail = err.response?.data?.detail
      showToast(typeof detail === 'string' ? detail : 'Delete failed.')
    }
  }

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  const triggerUploadClick = () => {
    document.getElementById('hidden-file-input')?.click()
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 transition-colors duration-200">
      {/* Search Command Menu */}
      <CommandMenu
        isOpen={isCommandOpen}
        onClose={() => setIsCommandOpen(false)}
        documents={documents}
        onUploadClick={triggerUploadClick}
        onLogout={handleLogout}
      />

      <header className="sticky top-0 z-40 border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/40 overflow-hidden shadow-sm">
              <img src="/logo.png" alt="ContextIQ" className="h-full w-full object-cover" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-zinc-950 dark:text-zinc-50">ContextIQ</h1>
              <p className="text-[10px] text-zinc-400 dark:text-zinc-500">RAG PDF Analyzer</p>
            </div>
          </div>

          {/* Search Trigger Shortcut */}
          <button
            onClick={() => setIsCommandOpen(true)}
            className="hidden md:flex items-center gap-2 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-3 py-1.5 text-xs text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-400 transition-colors cursor-pointer w-64 justify-between"
          >
            <div className="flex items-center gap-1.5">
              <Search className="h-3.5 w-3.5" />
              <span>Search documents...</span>
            </div>
            <kbd className="inline-flex items-center gap-0.5 rounded border border-zinc-200 dark:border-zinc-850 px-1.5 font-mono text-[9px] font-semibold bg-white dark:bg-zinc-900">
              <span>Ctrl</span><span>+</span><span>K</span>
            </kbd>
          </button>

          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-805 transition-colors"
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">{user?.email?.split('@')[0]}</span>
              <span className="text-[9px] text-zinc-400 dark:text-zinc-500">{user?.email}</span>
            </div>
            <button
              onClick={handleLogout}
              className="btn-secondary !py-1.5 !px-3 !text-xs font-semibold flex items-center gap-1.5"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {toast && (
          <div
            className={`mb-6 rounded-lg px-4 py-2.5 text-xs font-semibold ring-1 ring-inset ${
              toast.kind === 'success'
                ? 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-400 ring-emerald-600/10 dark:ring-emerald-500/20'
                : 'bg-rose-50 dark:bg-rose-950/30 text-rose-800 dark:text-rose-400 ring-rose-600/10 dark:ring-rose-500/20'
            }`}
          >
            {toast.message}
          </div>
        )}

        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              Upload a document
            </h2>
          </div>
          <UploadZone onUploaded={handleUploaded} onError={(m) => showToast(m)} />
        </section>

        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              Your documents
            </h2>
            <span className="text-[11px] font-semibold bg-zinc-100 dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 px-2 py-0.5 rounded-full">
              {documents.length} total
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <DocumentCardSkeleton />
              <DocumentCardSkeleton />
              <DocumentCardSkeleton />
            </div>
          ) : documents.length === 0 ? (
            <EmptyState onUploadClick={triggerUploadClick} />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {documents.map((doc) => (
                <DocumentCard key={doc.id} document={doc} onDelete={handleDelete} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
