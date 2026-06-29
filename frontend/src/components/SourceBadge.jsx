import { BookOpen } from 'lucide-react'

export default function SourceBadge({ pages = [] }) {
  if (!pages || pages.length === 0) {
    return null // Mute when no sources
  }
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-zinc-100 dark:border-zinc-800/80 pt-2.5">
      <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 flex items-center gap-1">
        <BookOpen className="h-3 w-3" />
        <span>Sources:</span>
      </span>
      <div className="flex flex-wrap gap-1">
        {pages.map((p) => (
          <span
            key={p}
            className="inline-flex items-center rounded-md bg-brand-50 dark:bg-brand-950/30 px-1.5 py-0.5 text-[10px] font-medium text-brand-700 dark:text-brand-400 ring-1 ring-inset ring-brand-600/10 dark:ring-brand-500/20"
          >
            Page {p}
          </span>
        ))}
      </div>
    </div>
  )
}
