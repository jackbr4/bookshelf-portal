import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import PasswordRoute from './routes/PasswordRoute'
import RequestRoute from './routes/RequestRoute'
import { isSessionValid } from './lib/session'

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isSessionValid()) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PasswordRoute />} />
        <Route
          path="/request"
          element={
            <RequireAuth>
              <RequestRoute />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
