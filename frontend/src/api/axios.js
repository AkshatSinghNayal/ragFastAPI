import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL,
  withCredentials: true, // send httpOnly refresh cookie
  headers: { 'Content-Type': 'application/json' },
})

// --- In-memory access token (set by AuthContext after login/refresh) ---
let accessToken = null
let onTokenExpired = null // callback to AuthContext.handleTokenRefresh

export function setAccessToken(token) {
  accessToken = token
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    delete api.defaults.headers.common.Authorization
  }
}

export function getAccessToken() {
  return accessToken
}

export function setRefreshHandler(handler) {
  onTokenExpired = handler
}

// --- Request interceptor: attach access token ---
api.interceptors.request.use(
  (config) => {
    if (accessToken && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// --- Response interceptor: silent refresh on 401 TOKEN_EXPIRED ---
let isRefreshing = false
let refreshQueue = [] // callbacks waiting for refresh result

function onRefreshed(newToken) {
  refreshQueue.forEach((cb) => cb(newToken))
  refreshQueue = []
}

function onRefreshFailed() {
  refreshQueue.forEach((cb) => cb(null))
  refreshQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config || {}
    const status = error.response?.status
    const code = error.response?.data?.code

    // Not a 401, or already retried, or refresh endpoint itself — bail out.
    if (
      status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.includes('/auth/refresh')
    ) {
      return Promise.reject(error)
    }

    // If the refresh token itself is invalid, surface to caller (AuthContext
    // will redirect to /login).
    if (code === 'INVALID_REFRESH_TOKEN') {
      if (onTokenExpired) onTokenExpired(null)
      return Promise.reject(error)
    }

    // If multiple requests fail simultaneously, queue them behind one refresh.
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        refreshQueue.push((newToken) => {
          if (!newToken) {
            reject(error)
            return
          }
          originalRequest.headers.Authorization = `Bearer ${newToken}`
          resolve(api(originalRequest))
        })
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    try {
      // Call /auth/refresh — refresh token is in the httpOnly cookie.
      const { data } = await axios.post(
        `${baseURL}/auth/refresh`,
        {},
        { withCredentials: true },
      )
      const newToken = data.access_token
      setAccessToken(newToken)
      onRefreshed(newToken)
      if (onTokenExpired) onTokenExpired(newToken)

      originalRequest.headers.Authorization = `Bearer ${newToken}`
      return api(originalRequest)
    } catch (refreshError) {
      onRefreshFailed()
      if (onTokenExpired) onTokenExpired(null)
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

export default api
