import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, FileText, LogOut, Plus, CornerDownLeft } from 'lucide-react'

export default function CommandMenu({ isOpen, onClose, documents = [], onUploadClick, onLogout }) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const menuRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  // Filter documents and build list of items
  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(query.toLowerCase())
  )

  const items = [
    ...filteredDocs.map((doc) => ({
      id: `doc-${doc.id}`,
      type: 'doc',
      label: doc.filename,
      action: () => {
        navigate(`/chat/${doc.id}`)
        onClose()
      },
    })),
    {
      id: 'action-upload',
      type: 'action',
      label: 'Upload new document',
      icon: Plus,
      action: () => {
        onUploadClick?.()
        onClose()
      },
    },
    {
      id: 'action-logout',
      type: 'action',
      label: 'Sign out',
      icon: LogOut,
      action: () => {
        onLogout?.()
        onClose()
      },
    },
  ]

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // Handle clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        onClose()
      }
    }
    if (isOpen) {
      window.addEventListener('mousedown', handleClickOutside)
    }
    return () => window.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, onClose])

  // Keyboard navigation inside the menu
  useEffect(() => {
    function handleKeyDown(e) {
      if (!isOpen) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev + 1) % items.length)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev - 1 + items.length) % items.length)
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (items[selectedIndex]) {
          items[selectedIndex].action()
        }
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, selectedIndex, items, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-zinc-950/60 p-4 pt-[15vh] backdrop-blur-sm">
      <div
        ref={menuRef}
        className="w-full max-w-lg overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xl"
      >
        {/* Search Input */}
        <div className="relative flex items-center border-b border-zinc-200 dark:border-zinc-800 px-4">
          <Search className="h-4.5 w-4.5 text-zinc-400 dark:text-zinc-500" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search documents or run actions..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            className="h-12 w-full bg-transparent pl-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:outline-none"
          />
          <button
            onClick={onClose}
            className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400 hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-400"
          >
            ESC
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-[300px] overflow-y-auto p-2 scroll-thin">
          {items.length === 0 ? (
            <p className="p-4 text-center text-xs text-zinc-400 dark:text-zinc-500">
              No results found.
            </p>
          ) : (
            <div className="space-y-0.5">
              {items.map((item, idx) => {
                const isSelected = idx === selectedIndex
                const Icon = item.icon || FileText
                return (
                  <button
                    key={item.id}
                    onClick={item.action}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition ${
                      isSelected
                        ? 'bg-zinc-100 dark:bg-zinc-800/80 text-zinc-900 dark:text-zinc-50'
                        : 'text-zinc-600 dark:text-zinc-400'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon className={`h-4 w-4 shrink-0 ${
                        isSelected 
                          ? 'text-brand-500 dark:text-brand-400' 
                          : 'text-zinc-400 dark:text-zinc-500'
                      }`} />
                      <span className="truncate font-medium">{item.label}</span>
                    </div>
                    {isSelected && (
                      <div className="flex items-center gap-1 text-[10px] font-medium text-zinc-400 dark:text-zinc-500">
                        <span>Select</span>
                        <CornerDownLeft className="h-3 w-3" />
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950/40 px-4 py-2.5 text-[10px] text-zinc-400 dark:text-zinc-500">
          <div className="flex gap-3">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-1">↑↓</kbd>
              <span>to navigate</span>
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-1">Enter</kbd>
              <span>to select</span>
            </span>
          </div>
          <span>Ctrl + K</span>
        </div>
      </div>
    </div>
  )
}
