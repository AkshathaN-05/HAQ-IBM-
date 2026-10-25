import { useCallback, useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api, session, setUnauthorizedHandler } from './api'
import { I18nContext, isRtl, translate } from './i18n'
import { AuthContext, useAuth } from './auth'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import AuthPage from './pages/AuthPage'
import WorkerHome from './pages/WorkerHome'
import NewClaim from './pages/NewClaim'
import ClaimDetail from './pages/ClaimDetail'
import ClaimsList from './pages/ClaimsList'
import WorkRecords from './pages/WorkRecords'
import WageCalculator from './pages/WageCalculator'
import Help from './pages/Help'
import EmployerInbox from './pages/EmployerInbox'
import EmployerClaim from './pages/EmployerClaim'

const LANG_KEY = 'haq.lang'

function RequireRole({ role, children }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return null
  if (!user) return <Navigate to={`/${role}/sign-in`} replace state={{ from: loc.pathname }} />
  if (user.role !== role) return <Navigate to={user.role === 'worker' ? '/worker' : '/employer'} replace />
  return children
}

export default function App() {
  const [lang, setLangState] = useState(() => { try { return localStorage.getItem(LANG_KEY) || 'en' } catch { return 'en' } })
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  const setLang = useCallback((l) => {
    setLangState(l)
    try { localStorage.setItem(LANG_KEY, l) } catch { /* ignore */ }
    document.documentElement.lang = l
    document.documentElement.dir = isRtl(l) ? 'rtl' : 'ltr'
  }, [])

  const signOut = useCallback(() => { session.clear(); setUser(null) }, [])

  const refreshUser = useCallback(async () => {
    if (!session.get()) { setUser(null); return null }
    try {
      const d = await api('/api/auth/me')
      setUser(d.user)
      return d.user
    } catch (e) {
      if (e.status === 401) signOut()
      return null
    }
  }, [signOut])

  useEffect(() => {
    setUnauthorizedHandler(() => signOut())
    refreshUser().finally(() => setReady(true))
  }, [refreshUser, signOut])

  useEffect(() => { document.documentElement.lang = lang; document.documentElement.dir = isRtl(lang) ? 'rtl' : 'ltr' }, [lang])

  const startSession = useCallback((token, u) => {
    session.set(token)
    setUser(u)
    if (u.preferred_language) setLang(u.preferred_language)
  }, [setLang])

  const i18n = useMemo(() => ({ lang, setLang, t: (k, v) => translate(lang, k, v) }), [lang, setLang])
  const auth = useMemo(() => ({ user, setUser, ready, startSession, signOut, refreshUser }), [user, ready, startSession, signOut, refreshUser])

  return (
    <I18nContext.Provider value={i18n}>
      <AuthContext.Provider value={auth}>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/help" element={<Help />} />
              <Route path="/wages" element={<WageCalculator />} />
              <Route path="/:portal/sign-in" element={<AuthPage mode="login" />} />
              <Route path="/:portal/register" element={<AuthPage mode="register" />} />
              <Route path="/:portal/forgot" element={<AuthPage mode="forgot" />} />
              <Route path="/worker" element={<RequireRole role="worker"><WorkerHome /></RequireRole>} />
              <Route path="/worker/claims" element={<RequireRole role="worker"><ClaimsList /></RequireRole>} />
              <Route path="/worker/new" element={<RequireRole role="worker"><NewClaim /></RequireRole>} />
              <Route path="/worker/claims/:id/edit" element={<RequireRole role="worker"><NewClaim /></RequireRole>} />
              <Route path="/worker/claims/:id" element={<RequireRole role="worker"><ClaimDetail /></RequireRole>} />
              <Route path="/worker/records" element={<RequireRole role="worker"><WorkRecords /></RequireRole>} />
              <Route path="/employer" element={<RequireRole role="employer"><EmployerInbox /></RequireRole>} />
              <Route path="/employer/claims/:id" element={<RequireRole role="employer"><EmployerClaim /></RequireRole>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </BrowserRouter>
      </AuthContext.Provider>
    </I18nContext.Provider>
  )
}
