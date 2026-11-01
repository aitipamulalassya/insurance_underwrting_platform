import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Applicants from './pages/Applicants'
import Products from './pages/Products'
import Quotes from './pages/Quotes'
import Underwriting from './pages/Underwriting'
import Policies from './pages/Policies'
import Endorsements from './pages/Endorsements'
import Renewals from './pages/Renewals'
import Anomalies from './pages/Anomalies'
import Assistant from './pages/Assistant'
import Documents from './pages/Documents'
import Reports from './pages/Reports'
import Login from './pages/Login'
import Users from './pages/Users'
import CustomerPortal from './pages/CustomerPortal'
import { api } from './lib/api'

export default function App() {
  const [user, setUser] = useState<any>(null)
  const [checking, setChecking] = useState(true)
  useEffect(() => {
    if (localStorage.getItem('yottaflex_token')) {
      api.get('/api/auth/me').then(r => setUser(r.data)).catch(() => {
        localStorage.removeItem('yottaflex_token')
        setUser(null)
      }).finally(() => setChecking(false))
    } else setChecking(false)
  }, [])
  if (checking) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Checking session…</div>
  if (!user) return <Login onLogin={setUser} />
  return <Routes>
    <Route element={<Layout user={user} onLogout={() => { localStorage.removeItem('yottaflex_token'); setUser(null) }} />}>
      <Route index element={user.role === 'CUSTOMER' ? <CustomerPortal /> : <Dashboard />} />
      <Route path="applicants" element={<Applicants />} />
      <Route path="products" element={<Products />} />
      <Route path="quotes" element={<Quotes user={user} />} />
      <Route path="underwriting" element={user.role === 'CUSTOMER' ? <Navigate to="/" /> : <Underwriting user={user} />} />
      <Route path="policies" element={<Policies user={user} />} />
      <Route path="endorsements" element={<Endorsements user={user} />} />
      <Route path="renewals" element={<Renewals user={user} />} />
      <Route path="anomalies" element={user.role === 'CUSTOMER' ? <Navigate to="/" /> : <Anomalies user={user} />} />
      <Route path="assistant" element={user.role === 'CUSTOMER' ? <Navigate to="/" /> : <Assistant />} />
      <Route path="documents" element={user.role === 'CUSTOMER' ? <Navigate to="/" /> : <Documents />} />
      <Route path="reports" element={user.role === 'CUSTOMER' ? <Navigate to="/" /> : <Reports />} />
      <Route path="users" element={user.role === 'ADMIN' ? <Users /> : <Navigate to="/" />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Route>
  </Routes>
}
