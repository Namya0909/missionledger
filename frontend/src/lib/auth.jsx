import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  // Login is 2 steps now (password, then that account's 3 security answers) — the
  // intermediate UI lives in LoginPage itself, so it calls api.loginStep1/loginStep2
  // directly and only hands the final Token response here to actually sign in.
  function completeLogin(data) {
    setToken(data.access_token)
    setUser(data.user)
  }

  async function signup(name, email, password, securityAnswers) {
    const data = await api.signup({ name, email, password, security_answers: securityAnswers })
    setToken(data.access_token)
    setUser(data.user)
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, completeLogin, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
