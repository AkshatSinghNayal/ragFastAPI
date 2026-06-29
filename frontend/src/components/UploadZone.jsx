import { useRef, useState } from 'react'
import { UploadCloud, File, Loader2 } from 'lucide-react'
import api from '../api/axios.js'

export default function UploadZone({ onUploaded, onError }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  async function uploadFile(file) {
    if (!file) return
    if (file.type !== 'application/pdf') {
      onError?.('Only PDF files are supported.')
      return
    }
    if (file.size > 25 * 1024 * 1024) {
      onError?.('File is too large (max 25 MB).')
      return
    }

    const formData = new FormData()
    formData.append('file', file)

    setUploading(true)
    setProgress(0)
    try {
      const { data } = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (event) => {
          if (event.total) {
            setProgress(Math.round((event.loaded * 100) / event.total))
          }
        },
      })
      onUploaded?.(data.document)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Upload failed.'
      onError?.(detail)
    } finally {
      setUploading(false)
      setProgress(0)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) uploadFile(file)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all duration-200 ${
        isDragging
          ? 'border-brand-500 bg-brand-50/50 dark:bg-brand-500/10'
          : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/30 hover:border-zinc-300 dark:hover:border-zinc-700 hover:bg-zinc-50/50 dark:hover:bg-zinc-900/50'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        id="hidden-file-input"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => uploadFile(e.target.files?.[0])}
        disabled={uploading}
      />

      <div className={`mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full transition-transform duration-200 ${
        isDragging ? 'scale-110' : ''
      } ${
        uploading
          ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'
          : 'bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400'
      }`}>
        {uploading ? (
          <Loader2 className="h-6 w-6 animate-spin" />
        ) : (
          <UploadCloud className="h-6 w-6" />
        )}
      </div>

      <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {uploading ? 'Uploading your document…' : 'Drag & drop a PDF here'}
      </p>
      
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        or{' '}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="font-medium text-brand-600 hover:text-brand-500 dark:text-brand-400 dark:hover:text-brand-300 focus:outline-none focus:underline disabled:opacity-50"
        >
          browse files
        </button>{' '}
        · max 25 MB
      </p>

      <div className="mt-4 hidden sm:block">
        <kbd className="inline-flex h-5 select-none items-center gap-0.5 rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-1.5 font-mono text-[10px] font-medium text-zinc-400 dark:text-zinc-500">
          <span>Ctrl</span><span>+</span><span>U</span>
        </kbd>
        <span className="ml-1.5 text-[10px] text-zinc-400 dark:text-zinc-500">to upload from anywhere</span>
      </div>

      {uploading && (
        <div className="mt-6 w-full max-w-xs">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div
              className="h-full bg-brand-600 dark:bg-brand-500 transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-2 text-center text-xs font-medium text-zinc-500 dark:text-zinc-400">{progress}%</p>
        </div>
      )}
    </div>
  )
}
