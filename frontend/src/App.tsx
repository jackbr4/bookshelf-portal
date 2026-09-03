import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import PasswordRoute from './routes/PasswordRoute'
import RequestRoute from './routes/RequestRoute'
import AdminRoute from './routes/AdminRoute'
import ImportRoute from './routes/ImportRoute'
import { isSessionValid } from './lib/session'
import { MamStatusProvider } from './lib/mamStatus'

/**
 * Reset scroll on navigation. Without this the offset left by the mobile
 * keyboard (e.g. while typing the access code) carries over to the next
 * page, which then loads with the header scrolled out of view.
 */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

/**
 * Layout route for everything behind the password gate. Sitewide state that
 * should survive navigation between pages (MAM slot status polling) lives here.
 */
function AuthedLayout() {
  if (!isSessionValid()) {
    return <Navigate to="/" replace />
  }
  return (
    <MamStatusProvider>
      <Outlet />
    </MamStatusProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<PasswordRoute />} />
        <Route element={<AuthedLayout />}>
          <Route path="/request" element={<RequestRoute />} />
          <Route path="/admin" element={<AdminRoute />} />
          <Route path="/import" element={<ImportRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
