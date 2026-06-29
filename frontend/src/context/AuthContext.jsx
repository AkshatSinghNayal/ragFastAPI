import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api, {
  setAccessToken,
  setRefreshHandler,
} from '../api/axios.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // ignore — even if the call fails we still clear local state
    } finally {
      setAccessToken(null)
      setUser(null)
    }
  }, [])

  const refreshSession = useCallback(async () => {
    try {
      const { data } = await api.post('/auth/refresh', {})
      setAccessToken(data.access_token)
      // fetch profile
      try {
        const { data: me } = await api.get('/auth/me')
        setUser(me)
        return true
      } catch {
        setAccessToken(null)
        setUser(null)
        return false
      }
    } catch {
      setAccessToken(null)
      setUser(null)
      return false
    }
  }, [])

  // On mount: attempt silent refresh to restore session.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const ok = await refreshSession()
      if (!cancelled) {
        if (!ok) {
          setAccessToken(null)
          setUser(null)
        }
        setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshSession])

  // Register the silent-refresh handler used by the axios interceptor.
  // `newToken` is null when refresh fails → AuthContext clears state.
  useEffect(() => {
    setRefreshHandler((newToken) => {
      if (newToken) {
        // token was already set by the interceptor; nothing else to do
        return
      }
      setAccessToken(null)
      setUser(null)
    })
  }, [])

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (email, password) => {
    const { data } = await api.post('/auth/register', { email, password })
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const value = {
    user,
    loading,
    isAuthenticated: Boolean(user),
    login,
    register,
    logout,
    refreshSession,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
