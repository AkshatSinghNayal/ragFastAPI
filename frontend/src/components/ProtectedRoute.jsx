import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="relative flex h-screen items-center justify-center bg-zinc-950 overflow-hidden select-none">
        {/* Glowing Background Accent */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[350px] h-[350px] bg-brand-500/10 rounded-full blur-[80px]" />
        
        <div className="relative flex flex-col items-center gap-6 z-10">
          {/* Logo container with pulsing animation */}
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900/40 p-1.5 shadow-2xl overflow-hidden animate-pulse">
            <img src="/logo.png" alt="ContextIQ" className="h-full w-full object-cover" />
          </div>
          
          <div className="flex flex-col items-center gap-1.5 text-center">
            <h2 className="text-xs font-bold tracking-widest uppercase text-zinc-400">ContextIQ</h2>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 animate-spin rounded-full border border-zinc-700 border-t-brand-500" />
              <p className="text-xs text-zinc-500 font-medium">Securing connection...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
