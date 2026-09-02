import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import PasswordRoute from './routes/PasswordRoute'
import RequestRoute from './routes/RequestRoute'
import AdminRoute from './routes/AdminRoute'
import ImportRoute from './routes/ImportRoute'
import { isSessionValid } from './lib/session'
import { MamStatusProvider } from './lib/mamStatus'

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
