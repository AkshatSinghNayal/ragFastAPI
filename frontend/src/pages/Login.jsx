import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Sun, Moon, Sparkles, Mail, Lock, Loader2, Chrome } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/dashboard'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
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

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Login failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 px-4 transition-colors duration-200">
      {/* Theme Switcher in Corner */}
      <div className="absolute right-4 top-4">
        <button
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors"
          type="button"
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>

      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/40 overflow-hidden shadow-sm">
            <img src="/logo.png" alt="ContextIQ" className="h-full w-full object-cover" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">Welcome to ContextIQ</h1>
          <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            Sign in to analyze and chat with your PDFs
          </p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4 p-6">
          {error && (
            <div className="rounded-lg bg-rose-50 dark:bg-rose-950/30 px-3 py-2 text-xs text-rose-700 dark:text-rose-400 ring-1 ring-inset ring-rose-600/10 dark:ring-rose-500/20">
              {error}
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400 dark:text-zinc-500" />
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field pl-9"
                placeholder="you@example.com"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400 dark:text-zinc-500" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field pl-9"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button type="submit" disabled={submitting} className="btn-primary w-full h-10 gap-2">
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            <span>{submitting ? 'Signing in…' : 'Sign in'}</span>
          </button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-zinc-200 dark:border-zinc-800" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white dark:bg-zinc-900 px-2 text-zinc-400">or continue with</span>
            </div>
          </div>

          <a
            href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/auth/google/login`}
            className="flex w-full items-center justify-center gap-2 h-10 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors"
          >
            <Chrome className="h-4 w-4" />
            Sign in with Google
          </a>

          <button
            type="button"
            onClick={() => {
              setEmail('demo@contextiq.com')
              setPassword('password123')
            }}
            className="flex w-full items-center justify-center h-10 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors"
          >
            Use Demo Account
          </button>

          <p className="text-center text-xs text-zinc-500 dark:text-zinc-400 mt-4">
            Don't have an account?{' '}
            <Link to="/register" className="font-semibold text-brand-600 hover:text-brand-500 dark:text-brand-400 dark:hover:text-brand-300">
              Register
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
