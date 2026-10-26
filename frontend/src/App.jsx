import { Route, Routes } from 'react-router-dom'
import FeedbackButton from './components/FeedbackButton'
import NavBar from './components/NavBar'
import ProtectedRoute from './components/ProtectedRoute'
import CostsPage from './pages/CostsPage'
import FeedbackAdminPage from './pages/FeedbackAdminPage'
import GetStartedPage from './pages/GetStartedPage'
import JoinPage from './pages/JoinPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import WorkspacePage from './pages/WorkspacePage'
import WorkspacesPage from './pages/WorkspacesPage'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/join/:token" element={<JoinPage />} />
        <Route
          path="/get-started"
          element={
            <ProtectedRoute>
              <GetStartedPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <WorkspacesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workspaces/:id"
          element={
            <ProtectedRoute>
              <WorkspacePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/costs"
          element={
            <ProtectedRoute>
              <CostsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/feedback"
          element={
            <ProtectedRoute>
              <FeedbackAdminPage />
            </ProtectedRoute>
          }
        />
      </Routes>
      <FeedbackButton />
    </div>
  )
}
