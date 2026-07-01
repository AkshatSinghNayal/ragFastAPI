import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

export default function AuthCallback() {
  const { isAuthenticated, loading } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const error = searchParams.get('error')
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => navigate('/login', { replace: true }), 3000)
      return () => clearTimeout(timer)
    }
  }, [error, navigate])

  useEffect(() => {
    if (isAuthenticated && !loading) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, loading, navigate])

  useEffect(() => {
    const timer = setTimeout(() => setTimedOut(true), 15000)
    return () => clearTimeout(timer)
  }, [])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 px-4">
        <div className="text-center max-w-md">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-900/30">
            <span className="text-rose-600 dark:text-rose-400 text-lg font-bold">!</span>
          </div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-2">
            Sign in failed
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            {error === 'access_denied'
              ? 'You denied the sign-in request. Redirecting…'
              : 'Something went wrong during sign-in. Redirecting…'}
          </p>
        </div>
      </div>
    )
  }

  if (timedOut) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 px-4">
        <div className="text-center max-w-md">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50 mb-2">
            Taking longer than expected
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            Redirecting to login…
          </p>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="btn-primary h-10 px-6 text-sm"
          >
            Back to login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 px-4">
      <div className="text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-brand-600 dark:text-brand-400 mb-4" />
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Completing sign in…
        </h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          You'll be redirected automatically.
        </p>
      </div>
    </div>
  )
}
