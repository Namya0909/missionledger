import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Landmark } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth.jsx'
import { isPrivilegedAnywhere } from '../lib/permissions'

// NavBar renders as a sibling of <Routes> (so it's visible on every page), not
// nested inside the matched route — useParams() can't see the route's :id from
// here, so the current workspace is read straight out of the URL instead.
function workspaceIdFromPath(pathname) {
  const match = pathname.match(/^\/workspaces\/(\d+)/)
  return match ? match[1] : ''
}

export default function NavBar() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const currentWorkspaceId = workspaceIdFromPath(location.pathname)
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState([])
  const canSeeCosts = isPrivilegedAnywhere(workspaces)
  // Feedback is restricted to the single project-owner account (backend-enforced,
  // config.FEEDBACK_ADMIN_EMAIL) — NOT every workspace admin/treasurer/owner, since
  // on the live site that's effectively anyone who's signed up.
  const canSeeFeedback = !!user?.is_feedback_admin

  useEffect(() => {
    if (user) api.listWorkspaces().then(setWorkspaces).catch(() => {})
  }, [user, location.pathname])

  return (
    <nav className="bg-gradient-to-b from-emerald-900 to-emerald-950 text-emerald-50 px-4 sm:px-6 py-3 flex items-center justify-between gap-3 shadow-md">
      <Link to="/" className="flex items-center gap-2 shrink-0">
        <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-700/60 text-emerald-100">
          <Landmark size={16} strokeWidth={2} />
        </span>
        <span className="font-bold text-lg tracking-tight">MissionLedger</span>
      </Link>
      {user && (
        <div className="flex items-center gap-2 sm:gap-4 text-sm min-w-0 flex-wrap justify-end">
          {workspaces.length > 1 && (
            <select
              value={currentWorkspaceId}
              onChange={(e) => navigate(`/workspaces/${e.target.value}`)}
              className="bg-emerald-800 border border-emerald-700 rounded-lg px-2 py-1.5 text-emerald-50 max-w-[110px] sm:max-w-[160px] text-xs sm:text-sm"
            >
              <option value="" disabled>
                Switch workspace
              </option>
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name}
                </option>
              ))}
            </select>
          )}
          {canSeeCosts && (
            <Link to="/costs" className="text-emerald-200 hover:text-white shrink-0">
              Costs
            </Link>
          )}
          {canSeeFeedback && (
            <Link to="/feedback" className="text-emerald-200 hover:text-white shrink-0">
              Feedback
            </Link>
          )}
          <span className="text-emerald-200 truncate max-w-[100px] sm:max-w-none">{user.name}</span>
          <button
            onClick={logout}
            className="bg-emerald-800 hover:bg-emerald-700 px-3 py-1.5 rounded-lg transition shrink-0"
          >
            Log out
          </button>
        </div>
      )}
    </nav>
  )
}
