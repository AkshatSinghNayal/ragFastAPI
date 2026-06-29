import React from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import SourceBadge from './SourceBadge.jsx'
import MarkdownRenderer from './MarkdownRenderer.jsx'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const { user } = useAuth()
  const firstChar = user?.email?.charAt(0).toUpperCase() || 'U'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900/40 overflow-hidden shadow-sm">
          <img src="/logo.png" alt="ContextIQ AI" className="h-full w-full object-cover" />
        </div>
      )}
      
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 text-sm shadow-sm ${
          isUser
            ? 'bg-brand-600 text-white'
            : 'bg-white dark:bg-zinc-900/60 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-800/80'
        }`}
      >
        <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider opacity-60">
          <span>{isUser ? 'You' : 'ContextIQ AI'}</span>
        </div>
        
        <div className="break-words leading-relaxed">
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>
        
        {!isUser && <SourceBadge pages={message.source_pages} />}
      </div>
      
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-lg border border-zinc-250 dark:border-zinc-800 bg-zinc-150 dark:bg-zinc-800/80 text-xs font-bold text-zinc-700 dark:text-zinc-300 shadow-sm">
          {firstChar}
        </div>
      )}
    </div>
  )
}
