import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import AuthCallback from './pages/AuthCallback.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Chat from './pages/Chat.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import { useAuth } from './context/AuthContext.jsx'

function PublicOnly({ children }) {
  const { isAuthenticated } = useAuth()
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route
        path="/login"
        element={
          <PublicOnly>
            <Login />
          </PublicOnly>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnly>
            <Register />
          </PublicOnly>
        }
      />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chat/:documentId"
        element={
          <ProtectedRoute>
            <Chat />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
