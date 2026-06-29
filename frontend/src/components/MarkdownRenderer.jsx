import React from 'react'

export default function MarkdownRenderer({ content }) {
  if (!content) return null

  // Split by double newlines to get paragraphs / lists / code blocks
  const blocks = content.split(/\n\n+/)

  return (
    <div className="space-y-3 leading-relaxed text-sm text-zinc-700 dark:text-zinc-300">
      {blocks.map((block, idx) => {
        const trimmed = block.trim()
        if (!trimmed) return null

        // Code block
        if (trimmed.startsWith('```')) {
          const lines = trimmed.split('\n')
          const code = lines.slice(1, -1).join('\n')
          return (
            <pre key={idx} className="overflow-x-auto rounded-lg bg-zinc-100 dark:bg-zinc-800/80 p-4 font-mono text-xs text-zinc-950 dark:text-zinc-50 border border-zinc-200 dark:border-zinc-850">
              <code>{code}</code>
            </pre>
          )
        }

        // Bullet list
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
          const items = trimmed.split('\n').map(line => line.replace(/^[-*•]\s+/, ''))
          return (
            <ul key={idx} className="list-disc pl-5 space-y-1">
              {items.map((item, i) => (
                <li key={i}>{parseInline(item)}</li>
              ))}
            </ul>
          )
        }

        // Numbered list
        if (/^\d+\.\s+/.test(trimmed)) {
          const items = trimmed.split('\n').map(line => line.replace(/^\d+\.\s+/, ''))
          return (
            <ol key={idx} className="list-decimal pl-5 space-y-1">
              {items.map((item, i) => (
                <li key={i}>{parseInline(item)}</li>
              ))}
            </ol>
          )
        }

        // Heading
        if (trimmed.startsWith('#')) {
          const match = trimmed.match(/^(#{1,6})\s+(.*)$/)
          if (match) {
            const level = match[1].length
            const text = match[2]
            const Tag = `h${Math.min(level + 1, 6)}` // h2, h3, etc.
            const sizeClass = 
              level === 1 ? 'text-lg font-bold' :
              level === 2 ? 'text-base font-bold' :
              'text-sm font-semibold'
            return (
              <Tag key={idx} className={`${sizeClass} text-zinc-900 dark:text-zinc-50 mt-4 mb-2`}>
                {parseInline(text)}
              </Tag>
            )
          }
        }

        // Standard paragraph
        return (
          <p key={idx}>
            {parseInline(trimmed)}
          </p>
        )
      })}
    </div>
  )
}

function parseInline(text) {
  // Regexes to parse bold, italic, code, citation badges
  // 1. Code: `text`
  // 2. Bold: **text**
  // 3. Italic: *text*
  // 4. Citation: [Page N]
  
  const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`|\[Page \d+\])/g
  const subParts = text.split(regex)
  
  return subParts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-bold text-zinc-900 dark:text-zinc-50">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="italic text-zinc-800 dark:text-zinc-200">{part.slice(1, -1)}</em>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="px-1.5 py-0.5 rounded bg-zinc-150 dark:bg-zinc-800/80 font-mono text-[11px] text-brand-600 dark:text-brand-400 border border-zinc-200 dark:border-zinc-800">{part.slice(1, -1)}</code>
    }
    if (part.startsWith('[Page ') && part.endsWith(']')) {
      const pageNum = part.match(/\d+/)?.[0] || '?'
      return (
        <span
          key={i}
          className="inline-flex items-center gap-0.5 mx-0.5 px-1.5 py-0.5 rounded bg-brand-50 dark:bg-brand-950/40 text-[10px] font-bold text-brand-600 dark:text-brand-400 border border-brand-200/50 dark:border-brand-900/30 cursor-default"
        >
          {part}
        </span>
      )
    }
    return part
  })
}
