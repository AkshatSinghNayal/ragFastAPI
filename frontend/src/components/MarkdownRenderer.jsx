import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function MarkdownRenderer({ content }) {
  if (!content) return null

  return (
    <div className="markdown-body prose dark:prose-invert max-w-none text-sm leading-relaxed space-y-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ node, ...props }) => (
            <h1 className="text-base font-bold text-zinc-900 dark:text-zinc-50 mt-4 mb-2 border-b border-zinc-200 dark:border-zinc-800 pb-1" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-50 mt-3 mb-1.5" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-xs font-bold uppercase tracking-wider text-brand-600 dark:text-brand-400 mt-3 mb-1" {...props} />
          ),
          p: ({ node, children, ...props }) => (
            <p className="mb-2 text-zinc-700 dark:text-zinc-300 leading-relaxed" {...props}>
              {renderChildrenWithCitations(children)}
            </p>
          ),
          li: ({ node, children, ...props }) => (
            <li className="text-zinc-700 dark:text-zinc-300 my-0.5" {...props}>
              {renderChildrenWithCitations(children)}
            </li>
          ),
          ul: ({ node, ...props }) => <ul className="list-disc pl-5 my-2 space-y-1" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal pl-5 my-2 space-y-1" {...props} />,
          strong: ({ node, ...props }) => <strong className="font-bold text-zinc-900 dark:text-zinc-100" {...props} />,
          code: ({ node, inline, className, children, ...props }) => {
            if (inline) {
              return (
                <code className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 font-mono text-[11px] text-brand-600 dark:text-brand-400 border border-zinc-200 dark:border-zinc-700/60" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <pre className="overflow-x-auto rounded-lg bg-zinc-900 text-zinc-100 p-3.5 font-mono text-xs my-3 border border-zinc-800">
                <code {...props}>{children}</code>
              </pre>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function renderChildrenWithCitations(children) {
  if (typeof children === 'string') {
    return parseCitations(children)
  }
  if (Array.isArray(children)) {
    return children.map((child, idx) =>
      typeof child === 'string' ? <React.Fragment key={idx}>{parseCitations(child)}</React.Fragment> : child
    )
  }
  return children
}

function parseCitations(text) {
  const parts = text.split(/(\[Page \d+\])/g)
  return parts.map((part, i) => {
    if (part.match(/^\[Page \d+\]$/)) {
      return (
        <span
          key={i}
          className="inline-flex items-center gap-0.5 mx-1 px-1.5 py-0.5 rounded-full bg-brand-500/10 dark:bg-brand-500/20 text-[10px] font-bold text-brand-600 dark:text-brand-400 border border-brand-500/30 cursor-default shadow-xs"
        >
          {part}
        </span>
      )
    }
    return part
  })
}

