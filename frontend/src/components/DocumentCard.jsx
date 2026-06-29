import { Link } from 'react-router-dom'
import { FileText, Layers, Calendar, Trash2, MessageSquare, AlertCircle } from 'lucide-react'

const STATUS_STYLES = {
  ready: 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 ring-emerald-600/10 dark:ring-emerald-500/20',
  processing: 'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 ring-amber-600/10 dark:ring-amber-500/20 animate-pulse',
  failed: 'bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-400 ring-rose-600/10 dark:ring-rose-500/20',
}

export default function DocumentCard({ document, onDelete }) {
  const status = document.status || 'processing'

  return (
    <div className="card flex flex-col p-4 hover:border-zinc-300 dark:hover:border-zinc-700/80 hover:shadow-md group">
      <div className="flex items-start justify-between gap-3">
        <Link
          to={`/chat/${document.id}`}
          className="min-w-0 flex-1 flex items-start gap-2 text-zinc-800 dark:text-zinc-200 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
          title={document.filename}
        >
          <FileText className="h-5 w-5 shrink-0 text-zinc-400 group-hover:text-brand-500 transition-colors mt-0.5" />
          <span className="block truncate font-medium text-sm leading-6">{document.filename}</span>
        </Link>
        <span
          className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset ${
            STATUS_STYLES[status] || STATUS_STYLES.processing
          }`}
        >
          {status}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 border-y border-zinc-100 dark:border-zinc-800/80 py-2.5 text-[11px] text-zinc-500 dark:text-zinc-400">
        <div className="flex items-center gap-1.5 justify-start">
          <FileText className="h-3.5 w-3.5 text-zinc-400" />
          <span>
            {document.total_pages != null ? `${document.total_pages} pgs` : '—'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 justify-center">
          <Layers className="h-3.5 w-3.5 text-zinc-400" />
          <span>
            {document.total_chunks != null ? `${document.total_chunks} chks` : '—'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 justify-end">
          <Calendar className="h-3.5 w-3.5 text-zinc-400" />
          <span>
            {new Date(document.created_at).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
            })}
          </span>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <Link
          to={`/chat/${document.id}`}
          className="btn-primary !px-3 !py-1.5 !text-xs gap-1.5"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          {status === 'ready' ? 'Chat' : 'View'}
        </Link>
        <button
          type="button"
          onClick={() => onDelete?.(document)}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span>Delete</span>
        </button>
      </div>
    </div>
  )
}
